from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ApiKey, Organization, OrganizationMembership, Role, User

bearer = HTTPBearer(auto_error=False)
_active_organization_id: ContextVar[int | None] = ContextVar("active_organization_id", default=None)


def hash_password(value: str) -> str:
    """PBKDF2-HMAC is dependency-free and adequate for the demo boundary."""
    salt = secrets.token_hex(16)
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(value: str, stored: str) -> bool:
    try:
        scheme, iteration, salt, expected = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), int(iteration)).hex()
        return hmac.compare_digest(actual, expected)
    except ValueError:
        # Retains a narrow compatibility path for a pre-Phase-2 demo database.
        return hmac.compare_digest(hashlib.sha256(value.encode()).hexdigest(), stored)


def _sign(payload: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(user: User, *, organization_id: int | None = None, minutes: int = 60) -> str:
    body = {
        "sub": user.id,
        "email": user.email,
        "role_id": user.role_id,
        "org_id": organization_id or user.organization_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=minutes)).timestamp()),
    }
    raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{raw}.{_sign(raw)}"


def parse_token(token: str) -> dict:
    try:
        raw, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(raw)):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if payload["exp"] < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = parse_token(credentials.credentials)
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User unavailable")
    # Preserve the token-bound workspace for membership-aware role resolution.
    setattr(user, "_active_organization_id", int(payload["org_id"]))
    return user


def active_organization(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    db: Session = Depends(get_db),
) -> Organization:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = parse_token(credentials.credentials)
    requested = int(x_workspace_id) if x_workspace_id and x_workspace_id.isdigit() else int(payload["org_id"])
    member = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == payload["sub"],
            OrganizationMembership.organization_id == requested,
            OrganizationMembership.status == "active",
        )
    )
    if not member:
        raise HTTPException(status_code=403, detail="Workspace access denied")
    org = db.get(Organization, requested)
    if not org:
        raise HTTPException(status_code=404, detail="Workspace not found")
    _active_organization_id.set(requested)
    return org


def current_role(user: User, db: Session, organization_id: int | None = None) -> Role:
    """Resolve a user role from the active organization membership, not a global user field."""
    org_id = organization_id or _active_organization_id.get() or getattr(user, "_active_organization_id", None) or user.organization_id
    membership = db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    if not role:
        raise HTTPException(status_code=403, detail="Role is unavailable for this workspace")
    return role


def require_permission(permission: str):
    def dependency(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        role = current_role(user, db)
        if "*" not in (role.permissions or []) and permission not in (role.permissions or []):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return user

    return dependency


def require_role(*allowed: str):
    def dep(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        role = current_role(user, db)
        if role.name not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return dep


@dataclass(frozen=True)
class ApiKeyPrincipal:
    key_id: int
    organization_id: int
    user_id: int
    scopes: list[str]


def _api_key_signature(key: ApiKey) -> str:
    expiry = key.expires_at.isoformat() if key.expires_at else "never"
    body = f"{key.id}:{key.organization_id}:{expiry}"
    return hmac.new(settings.jwt_secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]


def issue_api_key_value(key: ApiKey) -> str:
    """Return the one-time opaque programmatic key; only its deterministic signature is verifiable."""
    return f"{key.prefix}{key.id}.{_api_key_signature(key)}"


def api_key_principal(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKeyPrincipal:
    if not x_api_key or not x_api_key.startswith("ops_live_") or "." not in x_api_key:
        raise HTTPException(status_code=401, detail="Programmatic API key required")
    raw_id, provided = x_api_key[len("ops_live_"):].split(".", 1)
    if not raw_id.isdigit():
        raise HTTPException(status_code=401, detail="Invalid programmatic API key")
    key = db.get(ApiKey, int(raw_id))
    if not key or key.revoked or key.prefix != "ops_live_":
        raise HTTPException(status_code=401, detail="API key is unavailable")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if key.expires_at and key.expires_at < now:
        raise HTTPException(status_code=401, detail="API key has expired")
    if not hmac.compare_digest(provided, _api_key_signature(key)):
        raise HTTPException(status_code=401, detail="Invalid programmatic API key")
    key.last_used_at = now
    db.commit()
    return ApiKeyPrincipal(key.id, key.organization_id, key.user_id, list(key.scopes or []))


def require_api_key_scope(scope: str):
    def dependency(principal: ApiKeyPrincipal = Depends(api_key_principal)) -> ApiKeyPrincipal:
        if "*" not in principal.scopes and scope not in principal.scopes:
            raise HTTPException(status_code=403, detail=f"API key missing scope: {scope}")
        return principal
    return dependency
