"""
Least-privilege RBAC.

Identity comes from (in order):
  1. Session token in `Authorization: Bearer nsa.<...>` issued by POST /auth/login
     (see auth/accounts.py; revoked by POST /auth/logout)
  2. Supabase JWT in `Authorization: Bearer <jwt>` (verified with SUPABASE_JWT_SECRET)
  3. `X-User-Id` header - AUTH_MODE=demo only (tests, curl, scripts)

There is no silent default user: a request without credentials is 401 so the
UI can send the person to the login page.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from app.auth.accounts import decode_token, is_session_token
from app.config import get_repo
from app.contracts.schemas import Role, UserRecord

PERMISSIONS: dict[str, set[Role]] = {
    "view_case": {Role.OPERATIONS_STAFF, Role.SUPERVISOR, Role.ADMIN, Role.AUDITOR},
    "view_document": {Role.OPERATIONS_STAFF, Role.SUPERVISOR, Role.ADMIN, Role.AUDITOR},
    "compare": {Role.OPERATIONS_STAFF, Role.SUPERVISOR, Role.ADMIN},
    "edit_extraction": {Role.OPERATIONS_STAFF, Role.SUPERVISOR, Role.ADMIN},
    "generate_draft": {Role.OPERATIONS_STAFF, Role.SUPERVISOR, Role.ADMIN},
    "approve_send": {Role.SUPERVISOR, Role.ADMIN},
    "share_internal": {Role.OPERATIONS_STAFF, Role.SUPERVISOR, Role.ADMIN},
    "notify_external": {Role.SUPERVISOR, Role.ADMIN},
    "assign": {Role.OPERATIONS_STAFF, Role.SUPERVISOR, Role.ADMIN},
    "view_policy": {Role.OPERATIONS_STAFF, Role.SUPERVISOR, Role.ADMIN},
    "edit_policy": {Role.ADMIN},
    "view_audit": {Role.SUPERVISOR, Role.ADMIN, Role.AUDITOR},
    "export_data": {Role.SUPERVISOR, Role.ADMIN, Role.AUDITOR},
    "batch": {Role.SUPERVISOR, Role.ADMIN},
    "ingest": {Role.ADMIN, Role.SUPERVISOR, Role.OPERATIONS_STAFF},
}

AUTH_MODE = os.environ.get("AUTH_MODE", "demo")


def has_permission(user: UserRecord, perm: str) -> bool:
    return any(r in PERMISSIONS.get(perm, set()) for r in user.roles)


def _from_session(token: str) -> Optional[UserRecord]:
    payload = decode_token(token)
    if not payload:
        return None
    repo = get_repo()
    if repo.is_session_revoked(payload.get("sid", "")):
        return None
    return repo.get_user(payload.get("sub", ""))


def _from_jwt(token: str) -> Optional[UserRecord]:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        return None
    try:
        import jwt  # PyJWT

        claims = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except Exception:
        return None
    repo = get_repo()
    uid = claims.get("sub")
    user = repo.get_user(uid) if uid else None
    if user:
        return user
    # user exists in auth but not in app users table -> minimal viewer
    return UserRecord(id=uid or "unknown", email=claims.get("email", ""), display_name=claims.get("email", "user"), roles=[Role.AUDITOR])


def current_user(request: Request, authorization: Optional[str] = Header(default=None), x_user_id: Optional[str] = Header(default=None)) -> UserRecord:
    repo = get_repo()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        user = _from_session(token) if is_session_token(token) else _from_jwt(token)
        if user:
            return user
        raise HTTPException(401, detail={"error": "session expired or invalid - please log in again", "category": "AUTH_ERROR"})
    if AUTH_MODE == "demo" and x_user_id:
        user = repo.get_user(x_user_id)
        if user:
            return user
        raise HTTPException(401, detail={"error": f"unknown demo user '{x_user_id}'", "category": "AUTH_ERROR"})
    raise HTTPException(401, detail={"error": "authentication required - log in at /auth/login", "category": "AUTH_ERROR"})


def require(perm: str):
    def _dep(user: UserRecord = Depends(current_user)) -> UserRecord:
        if not has_permission(user, perm):
            raise HTTPException(403, detail={"error": f"role(s) {[r.value for r in user.roles]} lack permission '{perm}'", "category": "AUTH_ERROR"})
        return user

    return _dep
