"""
Least-privilege RBAC.

Identity comes from (in order):
  1. Supabase JWT in `Authorization: Bearer <jwt>` (verified with SUPABASE_JWT_SECRET)
  2. `X-User-Id` header (demo/dev mode, AUTH_MODE=demo)
  3. DEMO_USER_ID fallback (AUTH_MODE=demo only)
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from app.config import DEMO_USER_ID, get_repo
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
    "edit_policy": {Role.ADMIN},
    "view_audit": {Role.SUPERVISOR, Role.ADMIN, Role.AUDITOR},
    "export_data": {Role.SUPERVISOR, Role.ADMIN, Role.AUDITOR},
    "batch": {Role.SUPERVISOR, Role.ADMIN},
    "ingest": {Role.ADMIN, Role.SUPERVISOR, Role.OPERATIONS_STAFF},
}

AUTH_MODE = os.environ.get("AUTH_MODE", "demo")


def has_permission(user: UserRecord, perm: str) -> bool:
    return any(r in PERMISSIONS.get(perm, set()) for r in user.roles)


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
        user = _from_jwt(authorization.split(" ", 1)[1])
        if user:
            return user
        if AUTH_MODE != "demo":
            raise HTTPException(401, detail={"error": "invalid token", "category": "AUTH_ERROR"})
    if AUTH_MODE == "demo":
        uid = x_user_id or DEMO_USER_ID
        user = repo.get_user(uid)
        if user:
            return user
        raise HTTPException(401, detail={"error": f"unknown demo user '{uid}'", "category": "AUTH_ERROR"})
    raise HTTPException(401, detail={"error": "authentication required", "category": "AUTH_ERROR"})


def require(perm: str):
    def _dep(user: UserRecord = Depends(current_user)) -> UserRecord:
        if not has_permission(user, perm):
            raise HTTPException(403, detail={"error": f"role(s) {[r.value for r in user.roles]} lack permission '{perm}'", "category": "AUTH_ERROR"})
        return user

    return _dep
