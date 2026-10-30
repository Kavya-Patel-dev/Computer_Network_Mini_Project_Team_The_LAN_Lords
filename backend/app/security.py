from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta, timezone
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuditLog, User, UserSession, utcnow

_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def digest_token(token: str, secret: str | None = None) -> str:
    data = token.encode("utf-8")
    if secret:
        return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return hashlib.sha256(data).hexdigest()


def issue_session(db: Session, user: User, ttl_seconds: int, secret: str) -> tuple[UserSession, str, str]:
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    session = UserSession(
        id=str(uuid4()), user_id=user.id, token_hash=digest_token(token, secret),
        csrf_hash=digest_token(csrf, secret), expires_at=utcnow() + timedelta(seconds=ttl_seconds),
    )
    user.last_active_at = utcnow()
    db.add(session)
    db.commit()
    return session, token, csrf


def current_session(request: Request, db: Session = Depends(get_db)) -> tuple[User, UserSession]:
    settings = request.app.state.settings
    raw = request.cookies.get(settings.session_cookie)
    if not raw:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = db.scalar(select(UserSession).where(UserSession.token_hash == digest_token(raw, request.app.state.session_secret)))
    now = utcnow()
    expires_at = session.expires_at
    # SQLite drops timezone metadata for DateTime(timezone=True); treat its
    # stored UTC value as UTC before comparing it with the aware current time.
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if session is None or expires_at <= now:
        if session is not None:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=401, detail="Session expired")
    user = db.get(User, session.user_id)
    if user is None or user.status != "active":
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Account is unavailable")
    session.last_seen_at = now
    return user, session


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    return current_session(request, db)[0]


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def require_csrf(request: Request, user_and_session: tuple[User, UserSession] = Depends(current_session)) -> User:
    user, session = user_and_session
    settings = request.app.state.settings
    cookie_token = request.cookies.get(settings.csrf_cookie, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if (not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token)
            or not secrets.compare_digest(digest_token(header_token, request.app.state.session_secret), session.csrf_hash)):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    return user


def add_audit(db: Session, actor_id: str | None, action: str, target_type: str,
              target_id: str | None, result: str = "Success", details: dict | None = None) -> None:
    db.add(AuditLog(id=str(uuid4()), actor_id=actor_id, action=action,
                    target_type=target_type, target_id=target_id,
                    result=result, details=details or {}))
