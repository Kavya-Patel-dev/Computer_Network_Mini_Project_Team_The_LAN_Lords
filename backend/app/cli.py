from __future__ import annotations

import argparse
import getpass
import os
from uuid import uuid4

from sqlalchemy import select

from .db import create_database
from .models import User
from .security import hash_password


def create_admin(email: str, name: str) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL to the Neon PostgreSQL connection string first.")
    if database_url.startswith("sqlite"):
        raise SystemExit("Admin bootstrap requires Neon/PostgreSQL; SQLite is test-only.")
    password = getpass.getpass("Admin password (minimum 12 chars, number and symbol): ")
    confirm = getpass.getpass("Confirm admin password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    if len(password) < 12 or not any(c.isdigit() for c in password) or not any(not c.isalnum() for c in password):
        raise SystemExit("Use at least 12 characters, including a number and a symbol.")
    engine, factory = create_database(database_url)
    try:
        with factory.begin() as db:
            if db.scalar(select(User.id).where(User.role == "admin")):
                raise SystemExit("An administrator already exists; bootstrap is one-time only.")
            if db.scalar(select(User.id).where(User.email == email.lower())):
                raise SystemExit("That email already exists.")
            db.add(User(id=str(uuid4()), name=name.strip(), email=email.strip().lower(),
                        password_hash=hash_password(password), role="admin", status="active"))
    finally:
        engine.dispose()
    print("Initial admin created. The password was not stored in plaintext or printed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend administration tasks")
    subparsers = parser.add_subparsers(dest="command", required=True)
    admin = subparsers.add_parser("create-admin", help="Create the first administrator")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name)


if __name__ == "__main__":
    main()
