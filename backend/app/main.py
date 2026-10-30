from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from .config import Settings
from .db import create_database, get_db
from .models import AuditLog, Notification, Plan, ShareLink, SimulationRun, User, UserSession, utcnow
from .schemas import (
    AdminUserUpdate, LoginRequest, PasswordUpdate, PlanCreate, PlanUpdate, ProfileUpdate,
    ReviewRequest, SimulationRequest, UserCreate,
)
from .security import (
    add_audit, current_session, digest_token, hash_password, issue_session,
    require_admin, require_csrf, require_user, verify_password,
)
from .services import ROUTING_DEVICE_TYPES, model_sha256, prepare_model_runtime, run_simulation

API_PREFIX = "/api/v1"
SCENARIOS = {"normal", "link_failure", "link_failures", "router_failure", "traffic_spike", "bandwidth_drop"}
_DUMMY_PASSWORD_HASH = hash_password("invalid-login-placeholder-!7")


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _user_out(user: User) -> dict:
    return {
        "id": user.id, "name": user.name, "email": user.email,
        "role": user.role, "status": user.status,
        "created_at": user.created_at.isoformat(),
        "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
    }


def _front_type(node: dict) -> str:
    return str(node.get("type", ""))


def _front_is_router(node: dict) -> bool:
    role = node.get("simulationRole")
    if role in {"router", "host"}:
        return role == "router"
    return _front_type(node) in ROUTING_DEVICE_TYPES


def _plan_out(plan: Plan, db: Session) -> dict:
    owner = plan.owner or db.get(User, plan.owner_id)
    nodes = plan.topology.get("nodes", []) if isinstance(plan.topology, dict) else []
    router_count = sum(_front_is_router(n) for n in nodes if isinstance(n, dict))
    return {
        "id": plan.id, "name": plan.name, "description": plan.description,
        "status": plan.status, "version": plan.version,
        "owner": owner.name if owner else "Unknown",
        "ownerEmail": owner.email if owner else "",
        "submitted_at": plan.submitted_at.isoformat() if plan.submitted_at else None,
        "updated_at": plan.updated_at.isoformat(),
        "routerCount": router_count, "hostCount": len(nodes) - router_count,
        "topology": plan.topology, "trafficPreset": plan.traffic_preset,
        "flows": plan.flows, "selectedScenarios": plan.selected_scenarios,
        "review": plan.review, "versions": plan.versions,
    }


def _run_summary(run: SimulationRun, db: Session) -> dict:
    plan = run.plan or db.get(Plan, run.plan_id)
    owner = db.get(User, run.owner_id)
    scenarios = run.result.get("scenarios", {})
    normal = scenarios.get("normal") or next(iter(scenarios.values()), {})
    static_loss = (normal.get("metrics", {}).get("static", {}).get("mean_packet_loss"))
    ai_loss = (normal.get("metrics", {}).get("ai", {}).get("mean_packet_loss"))
    if static_loss is None or ai_loss is None:
        verdict_type, verdict_text = "equal", "No comparable packet-loss metrics were returned."
        verdict_badge = "Metrics unavailable"
    elif ai_loss < static_loss:
        verdict_type, verdict_text = "better", f"AI reduced packet loss by {static_loss - ai_loss:.4f} (fraction)."
        verdict_badge = (f"AI reduced loss by {(static_loss - ai_loss) / static_loss * 100:.1f}%"
                         if static_loss > 0 else "AI loss below static")
    elif ai_loss > static_loss:
        verdict_type, verdict_text = "worse", f"AI increased packet loss by {ai_loss - static_loss:.4f} (fraction)."
        verdict_badge = f"AI loss higher by {(ai_loss - static_loss) * 100:.3f} points"
    else:
        verdict_type, verdict_text = "equal", "AI and static Dijkstra had equal packet loss."
        verdict_badge = "Equal packet loss"
    return {
        "id": run.id, "runId": run.id, "planId": run.plan_id,
        "planName": plan.name if plan else "Deleted plan", "version": plan.version if plan else "",
        "owner": owner.name if owner else "Unknown", "date": run.created_at.isoformat(),
        "runDate": run.created_at.isoformat(), "status": run.status,
        "trafficPreset": run.request.get("traffic_preset", "manual"),
        "selectedScenarios": list(scenarios), "scenariosCount": len(scenarios), "scenarios": scenarios,
        "lossStatic": None if static_loss is None else f"{static_loss * 100:.3f}%",
        "lossAi": None if ai_loss is None else f"{ai_loss * 100:.3f}%",
        "verdictType": verdict_type, "verdictBadge": verdict_badge, "verdictText": verdict_text,
        "modelSha256": run.model_sha256,
    }


def create_app(settings: Settings | None = None, *, testing: bool = False) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate(testing=testing)
    session_secret = settings.session_secret or secrets.token_urlsafe(48)
    engine = None
    factory = None
    if settings.database_url:
        engine, factory = create_database(settings.database_url, testing=testing)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    app = FastAPI(
        title="LAN Lords Routing API", version="1.0.0",
        description="Authenticated plan, routing simulation, result, and admin API.",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.testing = testing
    app.state.session_secret = session_secret
    app.state.engine = engine
    app.state.session_factory = factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.frontend_origins), allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, _exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"detail": "Database operation unavailable"})

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    def ready(request: Request):
        engine_ = request.app.state.engine
        if engine_ is None:
            raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
        try:
            with engine_.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="Database is not ready") from None
        try:
            digest = model_sha256()
        except Exception:
            raise HTTPException(status_code=503, detail="Frozen routing model is not ready") from None
        return {"status": "ready", "database": "connected", "model_sha256": digest}

    @app.get(f"{API_PREFIX}/admin/model", tags=["admin"])
    def model_metadata(_admin: User = Depends(require_admin)):
        try:
            digest = model_sha256()
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="Frozen routing checkpoint is unavailable") from None
        except Exception:
            raise HTTPException(status_code=503, detail="Frozen routing checkpoint integrity check failed") from None
        return {
            "status": "verified", "artifact": "AI/runs/day5/final_routing_model.pt",
            "sha256": digest, "candidate_paths_per_flow": 4,
            "inference": "GATv2 + dueling Double DQN with safety fallback; no GRU",
        }

    @app.post(f"{API_PREFIX}/auth/register", status_code=201, tags=["auth"])
    def register(data: UserCreate, request: Request, response: Response, db: Session = Depends(get_db)):
        if not any(ch.isdigit() for ch in data.password) or not any(not ch.isalnum() for ch in data.password):
            raise HTTPException(status_code=422, detail="Password must include a number and a special character")
        normalized_email = str(data.email).strip().lower()
        if db.scalar(select(User.id).where(User.email == normalized_email)):
            raise HTTPException(status_code=409, detail="An account with that email already exists")
        user = User(id=str(uuid4()), name=data.name.strip(), email=normalized_email,
                    password_hash=hash_password(data.password), role="user", status="active")
        db.add(user)
        add_audit(db, None, "auth.register", "user", user.id)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="An account with that email already exists") from None
        _, token, csrf = issue_session(db, user, request.app.state.settings.session_ttl_seconds,
                                       request.app.state.session_secret)
        _set_auth_cookies(request, response, token, csrf)
        return {"user": _user_out(user), "email_verification": "not_configured"}

    @app.post(f"{API_PREFIX}/auth/login", tags=["auth"])
    def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
        email = str(data.email).strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            verify_password(data.password, _DUMMY_PASSWORD_HASH)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        locked_until = _utc(user.locked_until)
        if locked_until and locked_until > utcnow():
            raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Try again later.")
        if user.status != "active" or not verify_password(data.password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.failed_login_count = 0
                user.locked_until = utcnow() + timedelta(minutes=15)
            add_audit(db, user.id, "auth.login", "user", user.id, "Denied")
            db.commit()
            raise HTTPException(status_code=401, detail="Invalid email or password")
        user.failed_login_count = 0
        user.locked_until = None
        add_audit(db, user.id, "auth.login", "user", user.id)
        db.commit()
        _, token, csrf = issue_session(db, user, request.app.state.settings.session_ttl_seconds,
                                       request.app.state.session_secret)
        _set_auth_cookies(request, response, token, csrf)
        return {"user": _user_out(user)}

    @app.get(f"{API_PREFIX}/auth/me", tags=["auth"])
    def auth_me(user: User = Depends(require_user)):
        return {"user": _user_out(user)}

    @app.post(f"{API_PREFIX}/auth/logout", tags=["auth"])
    def logout(request: Request, response: Response, session_info=Depends(current_session),
               _csrf: User = Depends(require_csrf), db: Session = Depends(get_db)):
        user, session = session_info
        db.delete(session)
        add_audit(db, user.id, "auth.logout", "user", user.id)
        db.commit()
        _clear_auth_cookies(request, response)
        return {"ok": True}

    @app.get(f"{API_PREFIX}/users/me", tags=["users"])
    def get_profile(user: User = Depends(require_user)):
        return _user_out(user)

    @app.patch(f"{API_PREFIX}/users/me", tags=["users"])
    def update_profile(data: ProfileUpdate, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        user.name = data.name.strip()
        add_audit(db, user.id, "user.profile.update", "user", user.id)
        db.commit()
        return _user_out(user)

    @app.post(f"{API_PREFIX}/users/me/password", tags=["users"])
    def update_password(data: PasswordUpdate, request: Request, user: User = Depends(require_csrf),
                        session_info=Depends(current_session), db: Session = Depends(get_db)):
        if not verify_password(data.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if not any(ch.isdigit() for ch in data.new_password) or not any(not ch.isalnum() for ch in data.new_password):
            raise HTTPException(status_code=422, detail="New password must include a number and a special character")
        user.password_hash = hash_password(data.new_password)
        current = session_info[1]
        db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.id != current.id).delete(synchronize_session=False)
        add_audit(db, user.id, "user.password.update", "user", user.id)
        db.commit()
        return {"ok": True}

    @app.get(f"{API_PREFIX}/users/me/sessions", tags=["users"])
    def list_my_sessions(session_info: tuple[User, UserSession] = Depends(current_session), db: Session = Depends(get_db)):
        user, current = session_info
        rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id)
                          .order_by(UserSession.last_seen_at.desc())).all()
        return {"items": [{"id": row.id, "created_at": _utc(row.created_at).isoformat(),
                            "last_seen_at": _utc(row.last_seen_at).isoformat(), "current": row.id == current.id}
                           for row in rows]}

    @app.post(f"{API_PREFIX}/users/me/sessions/revoke-others", tags=["users"])
    def revoke_other_sessions(user: User = Depends(require_csrf),
                              session_info: tuple[User, UserSession] = Depends(current_session),
                              db: Session = Depends(get_db)):
        _, current = session_info
        deleted = db.query(UserSession).filter(UserSession.user_id == user.id,
                                               UserSession.id != current.id).delete(synchronize_session=False)
        add_audit(db, user.id, "user.sessions.revoke_others", "user", user.id,
                  details={"revoked_sessions": deleted})
        db.commit()
        return {"revoked_sessions": deleted}

    @app.get(f"{API_PREFIX}/dashboard/user", tags=["dashboard"])
    def user_dashboard(user: User = Depends(require_user), db: Session = Depends(get_db)):
        plans = list(db.scalars(select(Plan).where(Plan.owner_id == user.id).order_by(Plan.updated_at.desc()).limit(10)))
        counts = {status: db.scalar(select(func.count()).select_from(Plan).where(Plan.owner_id == user.id, Plan.status == status)) or 0
                  for status in ("Draft", "Pending Review", "Changes Requested", "Approved", "Rejected")}
        runs = list(db.scalars(select(SimulationRun).where(SimulationRun.owner_id == user.id).order_by(SimulationRun.created_at.desc()).limit(5)))
        return {"user": _user_out(user), "plan_counts": counts,
                "plan_count": sum(counts.values()), "run_count": db.scalar(select(func.count()).select_from(SimulationRun).where(SimulationRun.owner_id == user.id)) or 0,
                "plans": [_plan_out(p, db) for p in plans], "recent_runs": [_run_summary(r, db) for r in runs]}

    @app.get(f"{API_PREFIX}/dashboard/admin", tags=["admin"])
    def admin_dashboard(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
        return {
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "active_users": db.scalar(select(func.count()).select_from(User).where(User.status == "active")) or 0,
            "plans": db.scalar(select(func.count()).select_from(Plan)) or 0,
            "pending_reviews": db.scalar(select(func.count()).select_from(Plan).where(Plan.status == "Pending Review")) or 0,
            "runs": db.scalar(select(func.count()).select_from(SimulationRun)) or 0,
        }

    @app.get(f"{API_PREFIX}/dashboard/admin/analytics", tags=["admin"])
    def admin_analytics(days: int = Query(30, ge=7, le=90), _admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)):
        cutoff = utcnow() - timedelta(days=days)
        reviewed = []
        by_day: dict[str, dict[str, Any]] = {}
        tags: dict[str, int] = {}
        review_minutes: list[float] = []
        for plan in db.scalars(select(Plan).where(Plan.review.is_not(None))).all():
            review = plan.review or {}
            try:
                reviewed_at = datetime.fromisoformat(review.get("date", ""))
            except (TypeError, ValueError):
                continue
            reviewed_at = _utc(reviewed_at)
            if reviewed_at is None or reviewed_at < cutoff:
                continue
            decision = review.get("decision")
            if decision not in {"approved", "changes_requested", "rejected"}:
                continue
            label = reviewed_at.strftime("%b %d")
            bucket = by_day.setdefault(reviewed_at.date().isoformat(), {"week": label, "approved": 0, "changes": 0, "rejected": 0})
            bucket[{"approved": "approved", "changes_requested": "changes", "rejected": "rejected"}[decision]] += 1
            reviewed.append((plan, review, reviewed_at))
            for tag in review.get("tags", []):
                if isinstance(tag, str):
                    tags[tag] = tags.get(tag, 0) + 1
            submitted_at = _utc(plan.submitted_at)
            if submitted_at is not None and reviewed_at >= submitted_at:
                review_minutes.append((reviewed_at - submitted_at).total_seconds() / 60.0)

        submitters: dict[str, dict[str, Any]] = {}
        for plan in db.scalars(select(Plan).where(Plan.created_at >= cutoff).order_by(Plan.created_at.desc())).all():
            owner = db.get(User, plan.owner_id)
            if owner is None:
                continue
            row = submitters.setdefault(owner.id, {"name": owner.name, "role": owner.role, "plans": 0, "approvals": 0})
            row["plans"] += 1
            if (plan.review or {}).get("decision") == "approved":
                row["approvals"] += 1
        decisions = [row for _, row in sorted(by_day.items())]
        top_tags = sorted(({"tag": tag, "count": count} for tag, count in tags.items()), key=lambda row: row["count"], reverse=True)[:8]
        top_submitters = sorted(submitters.values(), key=lambda row: row["plans"], reverse=True)[:10]
        decision_count = len(reviewed)
        rejected_count = sum(1 for _, review, _ in reviewed if review.get("decision") == "rejected")
        return {
            "days": days,
            "pending_reviews": db.scalar(select(func.count()).select_from(Plan).where(Plan.status == "Pending Review")) or 0,
            "approved_count": sum(1 for _, review, _ in reviewed if review.get("decision") == "approved"),
            "average_review_minutes": sum(review_minutes) / len(review_minutes) if review_minutes else None,
            "rejection_rate_percent": 100.0 * rejected_count / decision_count if decision_count else None,
            "decisions": decisions, "feedback_tags": top_tags, "top_submitters": top_submitters,
            "review_time_samples": [{"day": reviewed_at.strftime("%b %d"), "avgMin": minutes}
                                     for plan, review, reviewed_at in reviewed
                                     if (submitted := _utc(plan.submitted_at)) is not None
                                     for minutes in [(reviewed_at - submitted).total_seconds() / 60.0]
                                     if minutes >= 0],
        }

    @app.get(f"{API_PREFIX}/records", tags=["plans"])
    def list_records(request: Request, status: str | None = None, search: str | None = None,
                     offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                     user: User = Depends(require_user), db: Session = Depends(get_db)):
        stmt = select(Plan).options(joinedload(Plan.owner)).order_by(Plan.updated_at.desc())
        if user.role != "admin":
            stmt = stmt.where(Plan.owner_id == user.id)
        if status:
            stmt = stmt.where(Plan.status == status)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(Plan.name.ilike(term), Plan.description.ilike(term)))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(stmt.offset(offset).limit(limit)).unique().all()
        return {"items": [_plan_out(p, db) for p in rows], "total": total, "offset": offset, "limit": limit}

    @app.post(f"{API_PREFIX}/records", status_code=201, tags=["plans"])
    def create_record(data: PlanCreate, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        _validate_scenario_values(data.selected_scenarios)
        plan = Plan(id=str(uuid4()), owner_id=user.id, name=data.name.strip(), description=data.description,
                    topology=data.topology, traffic_preset=data.traffic_preset, flows=data.flows,
                    selected_scenarios=data.selected_scenarios, status="Draft")
        plan.versions = [_version_entry(plan, user.name, "Created draft")]
        db.add(plan)
        add_audit(db, user.id, "plan.create", "plan", plan.id)
        db.commit()
        db.refresh(plan)
        return _plan_out(plan, db)

    @app.get(f"{API_PREFIX}/records/{{record_id}}", tags=["plans"])
    def get_record(record_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
        plan = _owned_plan(db, record_id, user)
        return _plan_out(plan, db)

    @app.patch(f"{API_PREFIX}/records/{{record_id}}", tags=["plans"])
    def update_record(record_id: str, data: PlanUpdate, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        plan = _owned_plan(db, record_id, user, owner_only=True)
        if plan.status not in {"Draft", "Changes Requested"}:
            raise HTTPException(status_code=409, detail="Only draft or returned plans can be edited")
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return _plan_out(plan, db)
        for key, value in changes.items():
            setattr(plan, key, value)
        plan.updated_at = utcnow()
        plan.versions = [*(plan.versions or []), _version_entry(plan, user.name, "Plan updated")]
        add_audit(db, user.id, "plan.update", "plan", plan.id, details={"fields": sorted(changes)})
        db.commit()
        db.refresh(plan)
        return _plan_out(plan, db)

    @app.delete(f"{API_PREFIX}/records/{{record_id}}", status_code=204, tags=["plans"])
    def delete_record(record_id: str, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        plan = _owned_plan(db, record_id, user, owner_only=True)
        if plan.status not in {"Draft", "Rejected"}:
            raise HTTPException(status_code=409, detail="Only draft or rejected plans can be deleted")
        plan_id = plan.id
        db.delete(plan)
        add_audit(db, user.id, "plan.delete", "plan", plan_id)
        db.commit()
        return Response(status_code=204)

    @app.post(f"{API_PREFIX}/records/{{record_id}}/submit", tags=["plans"])
    def submit_record(record_id: str, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        plan = _owned_plan(db, record_id, user, owner_only=True)
        if plan.status not in {"Draft", "Changes Requested"}:
            raise HTTPException(status_code=409, detail="Plan is not eligible for submission")
        _validate_model_inputs(plan.topology, plan.flows, plan.traffic_preset)
        plan.status, plan.submitted_at, plan.updated_at = "Pending Review", utcnow(), utcnow()
        plan.versions = [*(plan.versions or []), _version_entry(plan, user.name, "Submitted for admin review")]
        admins = db.scalars(select(User).where(User.role == "admin", User.status == "active")).all()
        for admin in admins:
            db.add(Notification(id=str(uuid4()), user_id=admin.id, type="review_pending",
                                title="Plan submitted for review", message=plan.name,
                                link_to=f"/admin/review/{plan.id}"))
        add_audit(db, user.id, "plan.submit", "plan", plan.id)
        db.commit()
        return _plan_out(plan, db)

    @app.post(f"{API_PREFIX}/records/{{record_id}}/withdraw", tags=["plans"])
    def withdraw_record(record_id: str, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        plan = _owned_plan(db, record_id, user, owner_only=True)
        if plan.status != "Pending Review":
            raise HTTPException(status_code=409, detail="Only a pending review can be withdrawn")
        plan.status = "Draft"
        plan.submitted_at = None
        plan.updated_at = utcnow()
        plan.versions = [*(plan.versions or []), _version_entry(plan, user.name, "Withdrawn from admin review")]
        admins = db.scalars(select(User).where(User.role == "admin", User.status == "active")).all()
        for admin in admins:
            db.add(Notification(id=str(uuid4()), user_id=admin.id, type="review_withdrawn",
                                title="Review withdrawn", message=plan.name,
                                link_to=f"/admin/review/{plan.id}"))
        add_audit(db, user.id, "plan.withdraw", "plan", plan.id)
        db.commit()
        return _plan_out(plan, db)

    @app.post(f"{API_PREFIX}/records/{{record_id}}/review", tags=["admin"])
    def review_record(record_id: str, data: ReviewRequest, admin: User = Depends(require_csrf), db: Session = Depends(get_db)):
        if admin.role != "admin":
            raise HTTPException(status_code=403, detail="Administrator access required")
        plan = db.scalar(select(Plan).options(joinedload(Plan.owner)).where(Plan.id == record_id))
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan not found")
        if plan.owner_id == admin.id:
            raise HTTPException(status_code=403, detail="Administrators cannot review their own plans")
        if plan.status not in {"Pending Review", "Changes Requested"}:
            raise HTTPException(status_code=409, detail="Plan is not in the review queue")
        status = {"approved": "Approved", "changes_requested": "Changes Requested", "rejected": "Rejected"}[data.decision]
        plan.status = status
        plan.review = {"decision": data.decision, "admin": admin.name, "date": utcnow().isoformat(),
                       "comment": data.comment, "tags": data.tags, "pins": []}
        plan.updated_at = utcnow()
        plan.versions = [*(plan.versions or []), _version_entry(plan, admin.name, data.comment, data.decision)]
        db.add(Notification(id=str(uuid4()), user_id=plan.owner_id,
                            type={"approved": "plan_approved", "rejected": "plan_rejected", "changes_requested": "changes_requested"}[data.decision],
                            title=f"Plan {status.lower()}", message=data.comment, link_to=f"/plans/{plan.id}"))
        add_audit(db, admin.id, "plan.review", "plan", plan.id,
                  details={"decision": data.decision, "tags": data.tags})
        db.commit()
        return _plan_out(plan, db)

    @app.post(f"{API_PREFIX}/records/{{record_id}}/runs", status_code=201, tags=["ai"])
    async def execute_simulation(record_id: str, data: SimulationRequest, request: Request,
                                 user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        plan = _owned_plan(db, record_id, user, owner_only=True)
        if plan.status != "Approved":
            raise HTTPException(status_code=409, detail="Only approved plans can be simulated")
        scenarios = data.scenarios or plan.selected_scenarios or ["normal"]
        _validate_scenario_values(scenarios)
        try:
            digest = model_sha256()
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="Frozen routing model is unavailable") from None
        except Exception:
            raise HTTPException(status_code=503, detail="Frozen routing model failed integrity verification") from None
        try:
            prepare_model_runtime()
        except Exception:
            raise HTTPException(status_code=503, detail="Frozen routing model dependencies are unavailable") from None
        from starlette.concurrency import run_in_threadpool
        result_scenarios = {}
        traffic: str | list[dict] = plan.flows if plan.traffic_preset == "manual" else plan.traffic_preset
        try:
            for index, scenario in enumerate(scenarios):
                result_scenarios[scenario] = await run_in_threadpool(
                    run_simulation, plan.topology, traffic, scenario, data.seed + index, data.max_steps
                )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except Exception:
            raise HTTPException(status_code=503, detail="Routing simulation failed; no result was saved") from None
        run = SimulationRun(id=str(uuid4()), plan_id=plan.id, owner_id=user.id, status="completed",
                            model_sha256=digest,
                            request={"scenarios": scenarios, "seed": data.seed, "max_steps": data.max_steps,
                                     "traffic_preset": plan.traffic_preset},
                            result={"scenarios": result_scenarios})
        db.add(run)
        add_audit(db, user.id, "simulation.run", "simulation_run", run.id,
                  details={"scenario_count": len(scenarios), "max_steps": data.max_steps})
        db.add(Notification(id=str(uuid4()), user_id=user.id, type="simulation_completed",
                            title="Simulation completed", message=plan.name,
                            link_to=f"/results/{run.id}"))
        db.commit()
        db.refresh(run)
        return _run_summary(run, db)

    @app.get(f"{API_PREFIX}/results", tags=["results"])
    def list_results(plan_id: str | None = None, user: User = Depends(require_user), db: Session = Depends(get_db),
                     offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        stmt = select(SimulationRun).options(joinedload(SimulationRun.plan)).order_by(SimulationRun.created_at.desc())
        if user.role != "admin":
            stmt = stmt.where(SimulationRun.owner_id == user.id)
        if plan_id:
            stmt = stmt.where(SimulationRun.plan_id == plan_id)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(stmt.offset(offset).limit(limit)).unique().all()
        return {"items": [_run_summary(r, db) for r in rows], "total": total, "offset": offset, "limit": limit}

    @app.get(f"{API_PREFIX}/results/{{run_id}}", tags=["results"])
    def get_result(run_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
        run = db.scalar(select(SimulationRun).options(joinedload(SimulationRun.plan)).where(SimulationRun.id == run_id))
        if run is None or (user.role != "admin" and run.owner_id != user.id):
            raise HTTPException(status_code=404, detail="Simulation result not found")
        return _run_summary(run, db)

    @app.post(f"{API_PREFIX}/results/{{run_id}}/share", status_code=201, tags=["shares"])
    def create_share(run_id: str, request: Request, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        run = db.get(SimulationRun, run_id)
        if run is None or run.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Simulation result not found")
        token = secrets.token_urlsafe(32)
        share = ShareLink(id=str(uuid4()), token_hash=digest_token(token, request.app.state.session_secret), run_id=run_id,
                          owner_id=user.id, expires_at=utcnow() + timedelta(days=14))
        db.add(share)
        db.commit()
        return {"id": share.id, "token": token, "run_id": run_id,
                "expires_at": share.expires_at.isoformat(), "status": "active"}

    @app.get(f"{API_PREFIX}/shares", tags=["shares"])
    def list_shares(user: User = Depends(require_user), db: Session = Depends(get_db)):
        rows = db.scalars(
            select(ShareLink).where(ShareLink.owner_id == user.id)
            .order_by(ShareLink.created_at.desc()).limit(100)
        ).all()
        now = utcnow()
        result = []
        for share in rows:
            run = db.get(SimulationRun, share.run_id)
            plan = db.get(Plan, run.plan_id) if run else None
            expires_at = _utc(share.expires_at)
            status = "revoked" if share.revoked_at else "expired" if expires_at <= now else "active"
            result.append({
                "id": share.id, "run_id": share.run_id,
                "plan_name": plan.name if plan else "Deleted plan",
                "created_at": _utc(share.created_at).isoformat(),
                "expires_at": expires_at.isoformat(), "views": share.view_count,
                "status": status,
            })
        return {"items": result}

    @app.get(f"{API_PREFIX}/shares/{{token}}", tags=["shares"])
    def get_shared_result(token: str, request: Request, db: Session = Depends(get_db)):
        share = db.scalar(select(ShareLink).where(ShareLink.token_hash == digest_token(token, request.app.state.session_secret)))
        if share is None or share.revoked_at is not None or _utc(share.expires_at) <= utcnow():
            raise HTTPException(status_code=404, detail="Shared result not found or expired")
        share.view_count += 1
        run = db.scalar(select(SimulationRun).options(joinedload(SimulationRun.plan)).where(SimulationRun.id == share.run_id))
        db.commit()
        if run is None:
            raise HTTPException(status_code=404, detail="Shared result not found")
        return _run_summary(run, db)

    @app.delete(f"{API_PREFIX}/shares/{{token}}", tags=["shares"])
    def revoke_share(token: str, request: Request, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        share = db.scalar(select(ShareLink).where(ShareLink.token_hash == digest_token(token, request.app.state.session_secret), ShareLink.owner_id == user.id))
        if share is None:
            raise HTTPException(status_code=404, detail="Share link not found")
        share.revoked_at = utcnow()
        db.commit()
        return {"ok": True}

    @app.delete(f"{API_PREFIX}/shares/id/{{share_id}}", tags=["shares"])
    def revoke_share_by_id(share_id: str, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        share = db.scalar(select(ShareLink).where(ShareLink.id == share_id, ShareLink.owner_id == user.id))
        if share is None:
            raise HTTPException(status_code=404, detail="Share link not found")
        share.revoked_at = utcnow()
        db.commit()
        return {"ok": True}

    @app.get(f"{API_PREFIX}/notifications", tags=["notifications"])
    def list_notifications(user: User = Depends(require_user), db: Session = Depends(get_db),
                           offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                          .order_by(Notification.created_at.desc()).offset(offset).limit(limit)).all()
        return {"items": [_notification_out(n) for n in rows],
                "unread_count": db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))) or 0}

    @app.post(f"{API_PREFIX}/notifications/read-all", tags=["notifications"])
    def read_all_notifications(user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        rows = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))).all()
        for row in rows:
            row.read = True
        db.commit()
        return {"updated": len(rows)}

    @app.post(f"{API_PREFIX}/notifications/{{notification_id}}/read", tags=["notifications"])
    def read_notification(notification_id: str, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
        item = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
        if item is None:
            raise HTTPException(status_code=404, detail="Notification not found")
        item.read = True
        db.commit()
        return _notification_out(item)

    @app.get(f"{API_PREFIX}/admin/users", tags=["admin"])
    def list_users(q: str | None = None, user: User = Depends(require_admin), db: Session = Depends(get_db),
                   offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        stmt = select(User).order_by(User.created_at.desc())
        if q:
            term = f"%{q.strip()}%"
            stmt = stmt.where(or_(User.name.ilike(term), User.email.ilike(term)))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(stmt.offset(offset).limit(limit)).all()
        result = []
        for row in rows:
            plans_count = db.scalar(select(func.count()).select_from(Plan).where(Plan.owner_id == row.id)) or 0
            item = _user_out(row)
            item.update({"plansCount": plans_count, "sessionsCount": db.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == row.id)) or 0})
            result.append(item)
        return {"items": result, "total": total, "offset": offset, "limit": limit}

    @app.get(f"{API_PREFIX}/admin/users/{{user_id}}", tags=["admin"])
    def get_admin_user(user_id: str, _admin: User = Depends(require_admin), db: Session = Depends(get_db)):
        row = db.get(User, user_id)
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        item = _user_out(row)
        item.update({"plansCount": db.scalar(select(func.count()).select_from(Plan).where(Plan.owner_id == row.id)) or 0,
                     "sessionsCount": db.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == row.id)) or 0})
        return {"user": item, "plans": [_plan_out(p, db) for p in db.scalars(select(Plan).where(Plan.owner_id == row.id).order_by(Plan.updated_at.desc()).limit(100)).all()]}

    @app.patch(f"{API_PREFIX}/admin/users/{{user_id}}", tags=["admin"])
    def update_admin_user(user_id: str, data: AdminUserUpdate, admin: User = Depends(require_csrf), db: Session = Depends(get_db)):
        if admin.role != "admin":
            raise HTTPException(status_code=403, detail="Administrator access required")
        target = db.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")
        if target.id == admin.id and (data.status is not None or data.role is not None):
            raise HTTPException(status_code=409, detail="Administrators cannot change their own role or status")
        would_remove_active_admin = (
            target.role == "admin" and target.status == "active"
            and (data.role == "user" or data.status == "deactivated")
        )
        if would_remove_active_admin:
            active_admins = db.scalar(
                select(func.count()).select_from(User).where(User.role == "admin", User.status == "active")
            ) or 0
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="The last active administrator cannot be demoted or deactivated")
        if data.status is not None:
            target.status = data.status
            if data.status == "deactivated":
                db.query(UserSession).filter(UserSession.user_id == target.id).delete(synchronize_session=False)
        if data.role is not None:
            target.role = data.role
        add_audit(db, admin.id, "admin.user.update", "user", target.id,
                  details={"status": data.status, "role": data.role})
        db.commit()
        return _user_out(target)

    @app.post(f"{API_PREFIX}/admin/users/{{user_id}}/sessions/revoke", tags=["admin"])
    def revoke_user_sessions(user_id: str, admin: User = Depends(require_csrf), db: Session = Depends(get_db)):
        if admin.role != "admin":
            raise HTTPException(status_code=403, detail="Administrator access required")
        target = db.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")
        deleted = db.query(UserSession).filter(UserSession.user_id == target.id).delete(synchronize_session=False)
        add_audit(db, admin.id, "admin.user.sessions.revoke", "user", target.id,
                  details={"revoked_sessions": deleted})
        db.commit()
        return {"revoked_sessions": deleted}

    @app.get(f"{API_PREFIX}/admin/audit", tags=["admin"])
    def list_audit(user_id: str | None = None, _admin: User = Depends(require_admin), db: Session = Depends(get_db),
                   offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if user_id:
            stmt = stmt.where(or_(AuditLog.actor_id == user_id, AuditLog.target_id == user_id))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(stmt.offset(offset).limit(limit)).all()
        users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([a.actor_id for a in rows if a.actor_id]))).all()}
        items = [{"id": a.id, "time": a.created_at.isoformat(),
                            "actor": users[a.actor_id].name if a.actor_id in users else "System",
                            "role": users[a.actor_id].role if a.actor_id in users else "user",
                            "action": a.action, "target": f"{a.target_type}:{a.target_id or ''}",
                            "result": a.result, "details": a.details} for a in rows]
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    return app


def _set_auth_cookies(request: Request, response: Response, token: str, csrf: str) -> None:
    settings = request.app.state.settings
    age = settings.session_ttl_seconds
    response.set_cookie(settings.session_cookie, token, max_age=age, httponly=True,
                        secure=settings.secure_cookies, samesite="strict", path="/")
    response.set_cookie(settings.csrf_cookie, csrf, max_age=age, httponly=False,
                        secure=settings.secure_cookies, samesite="strict", path="/")


def _clear_auth_cookies(request: Request, response: Response) -> None:
    settings = request.app.state.settings
    response.delete_cookie(settings.session_cookie, path="/", secure=settings.secure_cookies, httponly=True, samesite="strict")
    response.delete_cookie(settings.csrf_cookie, path="/", secure=settings.secure_cookies, httponly=False, samesite="strict")


def _owned_plan(db: Session, record_id: str, user: User, *, owner_only: bool = False) -> Plan:
    plan = db.scalar(select(Plan).options(joinedload(Plan.owner)).where(Plan.id == record_id))
    if plan is None or (user.role != "admin" and plan.owner_id != user.id) or (owner_only and plan.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


def _version_entry(plan: Plan, author: str, summary: str, decision: str | None = None) -> dict:
    current_version = len(plan.versions or []) + 1
    return {"version": f"v{current_version}", "date": utcnow().isoformat(), "author": author,
            "status": plan.status, "decision": decision, "summary": summary}


def _validate_scenario_values(scenarios: list[str]) -> None:
    if not scenarios or len(scenarios) > 5 or len(set(scenarios)) != len(scenarios) or not set(scenarios) <= SCENARIOS:
        raise HTTPException(status_code=422, detail="Select one to five unique supported scenarios")


def _validate_model_inputs(topology: dict, flows: list[dict], preset: str) -> None:
    from .services import frontend_flows_to_model, frontend_topology_to_model
    api = __import__("backend.app.services", fromlist=["_model_api"])._model_api()
    model_topology = frontend_topology_to_model(topology)
    api.topology_graph(model_topology)
    if preset == "manual":
        if not flows:
            raise HTTPException(status_code=422, detail="Manual traffic requires at least one flow")
        model_flows = frontend_flows_to_model(flows)
        for row in model_flows:
            api._flow_from_json(row)
            if row["source"] not in {n["id"] for n in model_topology["nodes"]} or row["destination"] not in {n["id"] for n in model_topology["nodes"]}:
                raise HTTPException(status_code=422, detail="Flow endpoints must be declared topology nodes")


def _notification_out(n: Notification) -> dict:
    return {"id": n.id, "type": n.type, "title": n.title, "message": n.message,
            "link_to": n.link_to, "read": n.read, "created_at": n.created_at.isoformat()}


app = create_app()
