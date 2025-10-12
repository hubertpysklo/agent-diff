from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.platform.isolationEngine.session import SessionManager
from src.platform.db.schema import ApiKey, OrganizationMembership, User


def _pbkdf2_hash(secret: str, *, salt_bytes: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", secret.encode(), salt_bytes, 120_000)


def hash_secret(secret: str, *, salt_b64: Optional[str] = None) -> Tuple[str, str]:
    salt_bytes = os.urandom(16) if salt_b64 is None else base64.b64decode(salt_b64)
    dk = _pbkdf2_hash(secret, salt_bytes=salt_bytes)
    return base64.b64encode(dk).decode(), base64.b64encode(salt_bytes).decode()


def verify_secret(secret: str, stored_hash_b64: str, stored_salt_b64: str) -> bool:
    derived_b64, _ = hash_secret(secret, salt_b64=stored_salt_b64)
    return hmac.compare_digest(derived_b64, stored_hash_b64)


class KeyHandler:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def create_api_key(
        self,
        *,
        user_id: int,
        days_valid: int = 90,
        is_platform_admin: bool = False,
        is_organization_admin: bool = False,
    ) -> Dict[str, object]:
        key_uuid = uuid4()
        key_id = key_uuid.hex
        secret = secrets.token_urlsafe(32)
        token = f"ak_{key_id}_{secret}"

        key_hash_b64, key_salt_b64 = hash_secret(secret)
        expires_at = datetime.now() + timedelta(days=days_valid)

        with self.session_manager.with_meta_session() as session:
            session.add(
                ApiKey(
                    id=key_uuid,
                    key_hash=key_hash_b64,
                    key_salt=key_salt_b64,
                    expires_at=expires_at,
                    user_id=user_id,
                    last_used_at=None,
                )
            )

        return {
            "token": token,
            "key_id": key_id,
            "expires_at": expires_at,
            "user_id": user_id,
            "is_platform_admin": is_platform_admin,
            "is_organization_admin": is_organization_admin,
        }


def parse_api_key(header: Optional[str]) -> Optional[Tuple[str, str]]:
    if not header:
        return None
    token = (
        header.split(" ", 1)[1].strip()
        if header.startswith("ApiKey ")
        else header.strip()
    )
    try:
        prefix, key_id, secret = token.split("_", 2)
        if prefix != "ak":
            return None
        return key_id, secret
    except ValueError:
        return None


def validate_api_key(header: Optional[str], session: Session) -> Dict[str, object]:
    parsed = parse_api_key(header)
    if not parsed:
        raise PermissionError("invalid api key format")
    key_id, secret = parsed

    key_uuid = UUID(key_id)
    key: Optional[ApiKey] = (
        session.query(ApiKey).filter(ApiKey.id == key_uuid).one_or_none()
    )
    if (
        not key
        or key.revoked_at
        or (key.expires_at and key.expires_at <= datetime.now())
    ):
        raise PermissionError("invalid or expired api key")

    if not verify_secret(secret, key.key_hash, key.key_salt):
        raise PermissionError("invalid api key")

    user: Optional[User] = (
        session.query(User).filter(User.id == key.user_id).one_or_none()
    )
    if not user:
        raise PermissionError("api key references non-existent user")

    key.last_used_at = datetime.now()
    is_platform_admin = bool(user.is_platform_admin)
    is_organization_admin = bool(user.is_organization_admin)
    org_ids: List[str] = [
        m.organization_id
        for m in session.query(OrganizationMembership).filter_by(user_id=key.user_id)
    ]
    return {
        "user_id": key.user_id,
        "org_ids": org_ids,
        "is_platform_admin": is_platform_admin,
        "is_organization_admin": is_organization_admin,
    }
