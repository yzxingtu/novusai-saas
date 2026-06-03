"""Token session and password-policy domain for AuthService."""

from time import time
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.i18n import _
from app.core.redis import get_redis_client
from app.core.security import (
    ACTIVE_TOKENS_PREFIX,
    _decode_token_no_blacklist,
    revoke_token,
)
from app.exceptions import BusinessException

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService


class AuthSessionPasswordDomain:
    """Stable auth sub-domain: token-session lifecycle and password policy."""

    def __init__(self, service: "AuthService") -> None:
        self._service = service

    async def record_active_tokens(
        self,
        user_type: str,
        user_id: str,
        access_jti: str,
        refresh_jti: str,
    ) -> None:
        try:
            client = get_redis_client()
            key = f"{ACTIVE_TOKENS_PREFIX}{user_type}:{user_id}"
            await client.hset(key, access_jti, refresh_jti)
            ttl_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
            await client.expire(key, ttl_days * 24 * 3600)
        except Exception:
            pass

    async def revoke_on_logout(
        self,
        access_token: str,
        user_type: str,
        user_id: str,
    ) -> None:
        payload = _decode_token_no_blacklist(access_token)
        if not payload or not payload.get("jti"):
            self._service._log_auth_warning(
                "auth.logout.skipped",
                user_type=user_type,
                user_id=user_id,
                reason="missing_jti",
            )
            return
        access_jti = payload["jti"]
        exp = payload.get("exp")
        access_ttl = max(1, int(exp - time())) if exp else 86400

        try:
            client = get_redis_client()
            key = f"{ACTIVE_TOKENS_PREFIX}{user_type}:{user_id}"
            refresh_jti = await client.hget(key, access_jti)
            await revoke_token(access_jti, access_ttl)
            if refresh_jti:
                refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
                await revoke_token(refresh_jti, refresh_ttl)
            await client.hdel(key, access_jti)
            self._service._log_auth_info(
                "auth.logout.success",
                user_type=user_type,
                user_id=user_id,
                revoked_refresh=bool(refresh_jti),
            )
        except Exception as exc:
            self._service._log_auth_warning(
                "auth.logout.failed",
                user_type=user_type,
                user_id=user_id,
                reason="token_revoke_error",
                error_type=type(exc).__name__,
            )

    async def force_logout(
        self,
        user_type: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> None:
        from app.core.sio_bridge import emit_force_logout
        from app.sio.presence import PresenceManager

        user_id_str = str(user_id)
        key = f"{ACTIVE_TOKENS_PREFIX}{user_type}:{user_id_str}"
        revoked_sessions = 0
        try:
            client = get_redis_client()
            pairs = await client.hgetall(key)
            if pairs:
                revoked_sessions = len(pairs)
                for access_jti, refresh_jti in pairs.items():
                    access_ttl = 86400
                    refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
                    await revoke_token(access_jti, access_ttl)
                    if refresh_jti:
                        await revoke_token(refresh_jti, refresh_ttl)
                await client.delete(key)
        except Exception as exc:
            self._service._log_auth_warning(
                "auth.force_logout.revoke_failed",
                user_type=user_type,
                user_id=user_id,
                tenant_id=tenant_id,
                reason="token_revoke_error",
                error_type=type(exc).__name__,
            )

        try:
            await PresenceManager.set_offline(user_type, user_id, tenant_id=tenant_id)
        except Exception as exc:
            self._service._log_auth_warning(
                "auth.force_logout.presence_cleanup_failed",
                user_type=user_type,
                user_id=user_id,
                tenant_id=tenant_id,
                error_type=type(exc).__name__,
            )

        try:
            await emit_force_logout(user_id, user_type)
        except Exception as exc:
            self._service._log_auth_warning(
                "auth.force_logout.emit_failed",
                user_type=user_type,
                user_id=user_id,
                tenant_id=tenant_id,
                error_type=type(exc).__name__,
            )
            raise

        self._service._log_auth_info(
            "auth.force_logout.success",
            user_type=user_type,
            user_id=user_id,
            tenant_id=tenant_id,
            revoked_sessions=revoked_sessions,
        )

    async def validate_password_policy(
        self,
        password: str,
        tenant_id: int | None = None,
    ) -> None:
        if tenant_id:
            min_length = await self._service._config_service.get_tenant_config(
                tenant_id, "tenant_password_min_length", default=None
            )
            complexity = await self._service._config_service.get_tenant_config(
                tenant_id, "tenant_password_complexity", default=None
            )
        else:
            min_length = None
            complexity = None

        if not min_length:
            min_length = await self._service._config_service.get_platform_config(
                "password_min_length", default=8
            )
        if not complexity:
            complexity = await self._service._config_service.get_platform_config(
                "password_complexity", default="medium"
            )

        if len(password) < min_length:
            raise BusinessException(
                message=_("auth.password_too_short", min_length=min_length)
            )

        if complexity == "low":
            return
        if complexity == "medium":
            has_letter = any(char.isalpha() for char in password)
            has_digit = any(char.isdigit() for char in password)
            if not (has_letter and has_digit):
                raise BusinessException(message=_("auth.password_complexity_medium"))
            return
        if complexity == "high":
            has_letter = any(char.isalpha() for char in password)
            has_digit = any(char.isdigit() for char in password)
            has_special = any(not char.isalnum() for char in password)
            if not (has_letter and has_digit and has_special):
                raise BusinessException(message=_("auth.password_complexity_high"))
