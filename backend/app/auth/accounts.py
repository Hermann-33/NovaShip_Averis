"""
Local accounts: password hashing + signed session tokens.

Standard library only (PBKDF2-HMAC-SHA256 + HMAC-signed tokens) so the offline
demo needs no extra dependency. Production deployments can keep using Supabase
JWTs (see rbac._from_jwt) - both are accepted by `current_user`.

Token format:  nsa.<base64url(payload json)>.<base64url(hmac-sha256)>
Payload:       {"sub": user_id, "sid": session_id, "iat": epoch, "exp": epoch}
Logout revokes the `sid` (repository keeps the revocation list).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Optional

SESSION_SECRET = os.environ.get("SESSION_SECRET") or "novaship-dev-session-secret-change-me"
SESSION_TTL_S = int(os.environ.get("SESSION_TTL_HOURS", "12")) * 3600
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "novaship123")
REGISTER_ALLOWED_ROLES = [r.strip().upper() for r in os.environ.get("REGISTER_ALLOWED_ROLES", "OPERATIONS_STAFF").split(",") if r.strip()]
MIN_PASSWORD_LENGTH = 8

_PBKDF2_ROUNDS = 120_000


# ---------------------------------------------------------------- passwords
def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        algo, rounds, salt_hex, digest_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def password_problem(password: str) -> Optional[str]:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"password must be at least {MIN_PASSWORD_LENGTH} characters"
    return None


# ---------------------------------------------------------------- tokens
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    return _b64e(hmac.new(SESSION_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())


def issue_token(user_id: str) -> tuple[str, dict[str, Any]]:
    now = int(time.time())
    payload = {"sub": user_id, "sid": secrets.token_hex(12), "iat": now, "exp": now + SESSION_TTL_S}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"nsa.{body}.{_sign(body)}", payload


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Return the payload if the signature is valid and the token is not expired, else None."""
    try:
        prefix, body, sig = token.split(".", 2)
    except ValueError:
        return None
    if prefix != "nsa" or not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        payload = json.loads(_b64d(body))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
        return None
    return payload


def is_session_token(token: str) -> bool:
    return token.startswith("nsa.")
