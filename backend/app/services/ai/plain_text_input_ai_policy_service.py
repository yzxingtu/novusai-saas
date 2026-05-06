"""中文: 普通输入框选区 AI 策略服务。

EN: Policy service for selected-text AI assistance in plain input controls.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID, ConfigService
from app.core.i18n import _
from app.exceptions import AuthorizationException
from app.models.system.admin import Admin
from app.models.tenant.tenant_admin import TenantAdmin
from app.services.ai.account_ai_access_service import AccountAIAccessService
from app.services.common.user_preference_service import (
    SCOPE_ADMIN,
    SCOPE_TENANT_ADMIN,
    UserPreferenceService,
)

PLAIN_TEXT_INPUT_AI_FEATURE = "plain_text_input_ai"
PLAIN_TEXT_INPUT_SURFACE = "plain_text_input"
PLAIN_TEXT_INPUT_PREFERENCE_KEY = "plain_text_input_ai_enabled"
PLATFORM_ADMIN_ENABLED_KEY = "platform_plain_text_input_ai_admin_enabled"
PLATFORM_ALLOW_TENANT_ENABLE_KEY = "platform_plain_text_input_ai_allow_tenant_enable"
PLATFORM_TENANT_DEFAULT_ENABLED_KEY = (
    "platform_plain_text_input_ai_tenant_default_enabled"
)
TENANT_ENABLED_KEY = "tenant_plain_text_input_ai_enabled"
PLAIN_TEXT_INPUT_ALLOWED_ACTIONS = frozenset(
    {
        "chat",
        "continue",
        "custom",
        "expand",
        "format",
        "insert",
        "optimize",
        "proofread",
        "rewrite",
        "summarize",
        "translate",
    }
)
PLAIN_TEXT_INPUT_DISABLED_FIELD_KINDS = frozenset({"code", "secret", "structured"})


def is_plain_text_input_surface(surface: str | None, document_type: str | None) -> bool:
    normalized_surface = str(surface or "").strip().lower()
    normalized_document_type = str(document_type or "").strip().lower()
    return (
        normalized_surface == PLAIN_TEXT_INPUT_SURFACE
        or normalized_document_type == PLAIN_TEXT_INPUT_SURFACE
    )


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dumped
    return {}


class PlainTextInputAiPolicyService:
    """中文: 聚合账号、平台、企业和个人偏好后的普通输入框 AI 策略。

    EN: Combines account, platform, tenant, and personal preferences for plain
    input AI assistance.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._config_service = ConfigService(db)
        self._preference_service = UserPreferenceService(db)
        self._account_access_service = AccountAIAccessService(db)

    async def get_admin_policy(self, admin: Admin) -> dict[str, Any]:
        ai_profile = (
            await self._account_access_service.get_platform_admin_ai_availability_profile(
                admin
            )
        )
        account_enabled = _as_bool(
            ai_profile.get("effective_ai_enabled"),
            default=False,
        )
        platform_admin_enabled = _as_bool(
            await self._config_service.get_platform_config(
                PLATFORM_ADMIN_ENABLED_KEY,
                default=True,
            )
        )
        platform_allow_tenant_enable = _as_bool(
            await self._config_service.get_platform_config(
                PLATFORM_ALLOW_TENANT_ENABLE_KEY,
                default=True,
            )
        )
        platform_tenant_default_enabled = _as_bool(
            await self._config_service.get_platform_config(
                PLATFORM_TENANT_DEFAULT_ENABLED_KEY,
                default=True,
            )
        )
        personal_enabled = await self._get_personal_enabled(
            scope=SCOPE_ADMIN,
            tenant_id=PLATFORM_TENANT_ID,
            user_id=admin.id,
        )
        enabled = account_enabled and platform_admin_enabled and personal_enabled
        return {
            "account_ai_enabled": account_enabled,
            "ai_unavailable_reason": ai_profile.get("ai_unavailable_reason"),
            "enabled": enabled,
            "personal_enabled": personal_enabled,
            "platform_admin_enabled": platform_admin_enabled,
            "platform_allow_tenant_enable": platform_allow_tenant_enable,
            "platform_tenant_default_enabled": platform_tenant_default_enabled,
            "scope": "admin",
            "surface": PLAIN_TEXT_INPUT_SURFACE,
            "tenant_enabled": True,
        }

    async def get_tenant_policy(self, tenant_admin: TenantAdmin) -> dict[str, Any]:
        ai_profile = (
            await self._account_access_service.get_tenant_admin_ai_availability_profile(
                tenant_admin
            )
        )
        account_enabled = _as_bool(
            ai_profile.get("effective_ai_enabled"),
            default=False,
        )
        platform_allow_tenant_enable = _as_bool(
            await self._config_service.get_platform_config(
                PLATFORM_ALLOW_TENANT_ENABLE_KEY,
                default=True,
            )
        )
        platform_tenant_default_enabled = _as_bool(
            await self._config_service.get_platform_config(
                PLATFORM_TENANT_DEFAULT_ENABLED_KEY,
                default=True,
            )
        )
        tenant_override = await self._config_service.get_tenant_config_override(
            tenant_admin.tenant_id,
            TENANT_ENABLED_KEY,
        )
        tenant_enabled = (
            platform_tenant_default_enabled
            if tenant_override is None
            else _as_bool(tenant_override)
        )
        personal_enabled = await self._get_personal_enabled(
            scope=SCOPE_TENANT_ADMIN,
            tenant_id=tenant_admin.tenant_id,
            user_id=tenant_admin.id,
        )
        enabled = (
            account_enabled
            and platform_allow_tenant_enable
            and tenant_enabled
            and personal_enabled
        )
        return {
            "account_ai_enabled": account_enabled,
            "ai_unavailable_reason": ai_profile.get("ai_unavailable_reason"),
            "enabled": enabled,
            "personal_enabled": personal_enabled,
            "platform_admin_enabled": True,
            "platform_allow_tenant_enable": platform_allow_tenant_enable,
            "platform_tenant_default_enabled": platform_tenant_default_enabled,
            "scope": "tenant",
            "surface": PLAIN_TEXT_INPUT_SURFACE,
            "tenant_enabled": tenant_enabled,
        }

    async def require_admin_enabled(
        self,
        admin: Admin,
        *,
        action: str | None = None,
        field_policy: Any = None,
    ) -> None:
        policy = await self.get_admin_policy(admin)
        if not policy["enabled"]:
            self._raise_policy_disabled(policy)
        self._require_field_policy_allowed(policy, action, field_policy)

    async def require_tenant_enabled(
        self,
        tenant_admin: TenantAdmin,
        *,
        action: str | None = None,
        field_policy: Any = None,
    ) -> None:
        policy = await self.get_tenant_policy(tenant_admin)
        if not policy["enabled"]:
            self._raise_policy_disabled(policy)
        self._require_field_policy_allowed(policy, action, field_policy)

    async def _get_personal_enabled(
        self,
        *,
        scope: str,
        tenant_id: int,
        user_id: int,
    ) -> bool:
        preferences = await self._preference_service.get_effective(
            scope=scope,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return _as_bool(preferences.get(PLAIN_TEXT_INPUT_PREFERENCE_KEY), True)

    def _require_field_policy_allowed(
        self,
        policy: dict[str, Any],
        action: str | None,
        field_policy: Any,
    ) -> None:
        if action is None and field_policy is None:
            return

        raw_policy = _as_mapping(field_policy)
        normalized_action = str(action or "").strip().lower()
        field_kind = str(raw_policy.get("field_kind") or "").strip().lower()
        allowed_actions = [
            str(item or "").strip().lower()
            for item in raw_policy.get("allowed_actions") or []
        ]
        allowed_action_set = {
            item for item in allowed_actions if item in PLAIN_TEXT_INPUT_ALLOWED_ACTIONS
        }

        if (
            not raw_policy
            or not _as_bool(raw_policy.get("enabled"), default=False)
            or field_kind in PLAIN_TEXT_INPUT_DISABLED_FIELD_KINDS
            or normalized_action not in allowed_action_set
        ):
            self._raise_policy_disabled(
                policy,
                field_policy={
                    "action": normalized_action,
                    "allowed_actions": sorted(allowed_action_set),
                    "enabled": raw_policy.get("enabled") if raw_policy else None,
                    "field_kind": field_kind or None,
                },
            )

    @staticmethod
    def _raise_policy_disabled(
        policy: dict[str, Any],
        *,
        field_policy: dict[str, Any] | None = None,
    ) -> None:
        payload_policy = {
            "account_ai_enabled": policy.get("account_ai_enabled"),
            "personal_enabled": policy.get("personal_enabled"),
            "platform_admin_enabled": policy.get("platform_admin_enabled"),
            "platform_allow_tenant_enable": policy.get(
                "platform_allow_tenant_enable"
            ),
            "tenant_enabled": policy.get("tenant_enabled"),
        }
        if field_policy is not None:
            payload_policy["field_policy"] = field_policy
        raise AuthorizationException(
            message=_("ai.error.plain_text_input_ai_disabled"),
            extra={
                "feature": PLAIN_TEXT_INPUT_AI_FEATURE,
                "reason": "plain_text_input_ai_disabled",
                "policy": payload_policy,
            },
        )


__all__ = [
    "PLAIN_TEXT_INPUT_AI_FEATURE",
    "PLAIN_TEXT_INPUT_ALLOWED_ACTIONS",
    "PLAIN_TEXT_INPUT_DISABLED_FIELD_KINDS",
    "PLAIN_TEXT_INPUT_PREFERENCE_KEY",
    "PLAIN_TEXT_INPUT_SURFACE",
    "PLATFORM_ADMIN_ENABLED_KEY",
    "PLATFORM_ALLOW_TENANT_ENABLE_KEY",
    "PLATFORM_TENANT_DEFAULT_ENABLED_KEY",
    "TENANT_ENABLED_KEY",
    "PlainTextInputAiPolicyService",
    "is_plain_text_input_surface",
]
