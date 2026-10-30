from __future__ import annotations

from collections.abc import Generator

from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def postgres_connect_args(url: str) -> dict[str, object]:
    """Return PostgreSQL connection args compatible with Neon poolers.

    Neon’s pooled endpoint rejects libpq startup ``options`` parameters. Keep
    the statement timeout for direct PostgreSQL connections, where that
    startup option is supported.
    """
    args: dict[str, object] = {"connect_timeout": 5}
    host = make_url(url).host or ""
    if "-pooler." not in host.lower():
        args["options"] = "-c statement_timeout=15000"
    return args


def create_database(url: str, *, testing: bool = False) -> tuple[Engine, sessionmaker[Session]]:
    if url.startswith("sqlite") and not testing:
        raise RuntimeError("SQLite cannot be used as an application database")
    normalized = normalize_database_url(url)
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if normalized.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if normalized.endswith(":memory:"):
            from sqlalchemy.pool import StaticPool
            kwargs["poolclass"] = StaticPool
    else:
        kwargs.update(
            pool_size=5,
            max_overflow=2,
            pool_recycle=300,
            connect_args=postgres_connect_args(normalized),
        )
    engine = create_engine(normalized, **kwargs)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory


def get_db(request: Request) -> Generator[Session, None, None]:
    factory = request.app.state.session_factory
    if factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_test_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
