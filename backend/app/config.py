from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    database_url: str | None = None
    session_secret: str | None = None
    frontend_origins: tuple[str, ...] = ("http://localhost:5173",)
    session_cookie: str = "lanlords_session"
    csrf_cookie: str = "lanlords_csrf"
    session_ttl_seconds: int = 60 * 60 * 12
    secure_cookies: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        # Keep local secrets beside the backend package; real process variables
        # (deployment secrets) take precedence over the local file.
        load_dotenv(dotenv_path=_ENV_FILE, override=False)
        raw_origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173")
        return cls(
            app_env=os.getenv("APP_ENV", "development").lower(),
            database_url=os.getenv("DATABASE_URL") or None,
            session_secret=os.getenv("SESSION_SECRET") or None,
            frontend_origins=tuple(x.strip() for x in raw_origins.split(",") if x.strip()),
            session_cookie=os.getenv("SESSION_COOKIE_NAME", "lanlords_session"),
            csrf_cookie=os.getenv("CSRF_COOKIE_NAME", "lanlords_csrf"),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "43200")),
            secure_cookies=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        )

    def validate(self, *, testing: bool = False) -> None:
        if self.app_env == "production":
            if not self.database_url:
                raise RuntimeError("DATABASE_URL is required in production")
            if not self.session_secret or len(self.session_secret) < 32:
                raise RuntimeError("SESSION_SECRET must contain at least 32 characters in production")
            if not self.secure_cookies:
                raise RuntimeError("COOKIE_SECURE=true is required in production")
        if self.database_url and self.database_url.startswith("sqlite") and not testing:
            raise RuntimeError("SQLite is permitted only for isolated tests; configure Neon PostgreSQL")
        if self.session_ttl_seconds < 300:
            raise RuntimeError("SESSION_TTL_SECONDS must be at least 300")
