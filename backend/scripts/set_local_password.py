#!/usr/bin/env python3
"""Rotate one local-auth password without exposing it on the command line or logs.

Examples:
    python backend/scripts/set_local_password.py --user u_admin_1
    python backend/scripts/set_local_password.py --user admin@example.com --lock-others
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(BACKEND))

from app.auth.accounts import hash_password, password_problem  # noqa: E402
from app.config import get_repo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, help="Existing application user id or email")
    parser.add_argument(
        "--lock-others",
        action="store_true",
        help="Replace every other local password with an unknown random value, effectively disabling their local login",
    )
    args = parser.parse_args()

    if os.environ.get("REPO_BACKEND", "memory").strip().lower() != "supabase":
        raise SystemExit("Refusing to rotate production credentials unless REPO_BACKEND=supabase")

    repo = get_repo()
    target = repo.get_user(args.user) or repo.get_user_by_email(args.user)
    if target is None:
        raise SystemExit("User not found")

    password = getpass.getpass("New password (12+ characters): ")
    confirm = getpass.getpass("Confirm new password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    if len(password) < 12 or password_problem(password):
        raise SystemExit("Production local password must be at least 12 characters")

    repo.set_password_hash(target.id, hash_password(password))

    locked = 0
    if args.lock_others:
        for user in repo.list_users():
            if user.id == target.id:
                continue
            repo.set_password_hash(user.id, hash_password(secrets.token_urlsafe(48)))
            locked += 1

    print(f"Updated local credential for {target.id}; other local logins locked: {locked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
