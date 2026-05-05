"""Interaction-mode and trust-policy runtime helpers for AgentChatService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.enums.agent import ActionLevelEnum
from app.schemas.ai.invalid_ai_runtime_input import is_invalid_ai_runtime_tool_name

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.ai.agent_chat import InteractionMode


_LEGACY_INTERACTION_MODE_KEYS = {
    "downgraded_from",
    "downgrade_reason",
    "interaction_mode",
    "interaction_mode_downgrade_reason",
    "interaction_mode_effective",
    "interaction_mode_requested",
}


async def resolve_runtime_trust_policy_ref(
    *,
    db: AsyncSession,
    tenant_id: int,
    conversation_id: int | None,
    agent_id: int,
    operator_id: int | None,
    operator_type: str | None,
    explicit_ref: dict[str, Any] | None = None,
    logger: Any,
    trust_policy_service_cls: type | None = None,
) -> dict[str, Any] | None:
    if explicit_ref:
        return explicit_ref
    try:
        if trust_policy_service_cls is None:
            from app.services.ai.execution_trust_policy_service import (
                ExecutionTrustPolicyService,
            )

            trust_policy_service_cls = ExecutionTrustPolicyService

        return await trust_policy_service_cls(
            db,
            tenant_id,
        ).resolve_runtime_policy(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
        )
    except Exception as exc:
        logger.warning(
            "Resolve execution trust policy degraded: tenant={} agent={} conversation={} operator={} type={} err={}",
            tenant_id,
            agent_id,
            conversation_id,
            operator_id,
            operator_type,
            str(exc),
        )
        return None


def build_trust_policy_ref_from_interaction_updates(
    interaction_updates: list[dict[str, Any]] | None,
    trust_policy_service_cls: type | None = None,
) -> dict[str, Any] | None:
    if not interaction_updates:
        return None

    if trust_policy_service_cls is None:
        from app.services.ai.execution_trust_policy_service import (
            ExecutionTrustPolicyService,
        )

        trust_policy_service_cls = ExecutionTrustPolicyService

    allowed_tool_names: set[str] = set()
    tool_families: set[str] = set()
    risk_cap = ActionLevelEnum.READ.value

    for update in interaction_updates:
        if not isinstance(update, dict):
            continue
        if bool(update.get("rejected")):
            continue
        if str(update.get("kind") or "") not in {
            "pending_confirmation",
            "pending_consent",
        }:
            continue
        tool_name = str(update.get("tool_name") or "").strip()
        if not tool_name or is_invalid_ai_runtime_tool_name(tool_name):
            continue
        tool_family = trust_policy_service_cls.tool_family_for_name(tool_name)
        tool_risk = trust_policy_service_cls.tool_risk_level(
            tool_name=tool_name,
            tool_family=tool_family,
        )
        allowed_tool_names.add(tool_name)
        if tool_family and tool_family != "none":
            tool_families.add(tool_family)
        if trust_policy_service_cls._risk_rank(
            tool_risk
        ) > trust_policy_service_cls._risk_rank(risk_cap):
            risk_cap = tool_risk

    if not allowed_tool_names:
        return None

    return {
        "policy_ids": [],
        "allowed_tool_names": sorted(allowed_tool_names),
        "tool_families": sorted(tool_families),
        "risk_level_cap": risk_cap,
    }


def build_trusted_auto_bootstrap_policy_ref() -> dict[str, Any]:
    return {
        "policy_ids": [],
        "allowed_tool_names": [],
        "tool_families": ["weather"],
        "risk_level_cap": ActionLevelEnum.READ.value,
    }


def strip_legacy_interaction_mode_fields(payload: Any) -> Any:
    if isinstance(payload, list):
        return [strip_legacy_interaction_mode_fields(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if str(key or "") in _LEGACY_INTERACTION_MODE_KEYS:
            continue
        cleaned[key] = strip_legacy_interaction_mode_fields(value)
    return cleaned


def normalize_requested_interaction_mode(
    requested_mode: str | None,
) -> InteractionMode:
    del requested_mode
    return "trusted_auto"


async def resolve_interaction_mode(
    *,
    db: AsyncSession,
    tenant_id: int,
    requested_mode: str | None,
    conversation_id: int | None,
    agent_id: int,
    operator_id: int | None,
    operator_type: str | None,
    explicit_trust_policy_ref: dict[str, Any] | None = None,
    interaction_updates: list[dict[str, Any]] | None = None,
    logger: Any,
    trust_policy_service_cls: type | None = None,
) -> tuple[InteractionMode, dict[str, Any] | None, str | None]:
    resolved_ref = await resolve_runtime_trust_policy_ref(
        db=db,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        agent_id=agent_id,
        operator_id=operator_id,
        operator_type=operator_type,
        explicit_ref=explicit_trust_policy_ref,
        logger=logger,
        trust_policy_service_cls=trust_policy_service_cls,
    )
    if resolved_ref:
        return "trusted_auto", resolved_ref, None
    interaction_ref = build_trust_policy_ref_from_interaction_updates(
        interaction_updates,
        trust_policy_service_cls=trust_policy_service_cls,
    )
    if interaction_ref:
        return "trusted_auto", interaction_ref, None
    return "trusted_auto", build_trusted_auto_bootstrap_policy_ref(), None


async def grant_trusted_auto_policies(
    *,
    db: AsyncSession,
    tenant_id: int,
    conversation_id: int,
    agent_id: int,
    operator_id: int | None,
    operator_type: str | None,
    interaction_updates: list[dict[str, Any]] | None,
    interaction_mode: str,
    trust_policy_service_cls: type | None = None,
) -> None:
    if interaction_mode != "trusted_auto" or not interaction_updates:
        return

    if trust_policy_service_cls is None:
        from app.services.ai.execution_trust_policy_service import (
            ExecutionTrustPolicyService,
        )

        trust_policy_service_cls = ExecutionTrustPolicyService

    service = trust_policy_service_cls(db, tenant_id)
    for update in interaction_updates:
        if str(update.get("kind") or "") not in {
            "pending_consent",
            "pending_confirmation",
        }:
            continue
        if bool(update.get("rejected")):
            continue
        tool_name = str(update.get("tool_name") or "").strip()
        if not tool_name or is_invalid_ai_runtime_tool_name(tool_name):
            continue
        await service.grant_conversation_tool_trust(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            tool_name=tool_name,
            granted_by=operator_id,
            grant_reason="interaction_mode:trusted_auto",
        )
