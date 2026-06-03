"""Tenant rich-text AI operation stream router / 企业端富文本 AI 操作流路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.shared._rich_text_ai_operations import stream_rich_text_operation
from app.api.shared.rich_text_ai_schemas import (
    AIWritingHistoryTurn,
    PlainTextInputAiPolicyEnvelope,
)
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.agent import MemoryChannelEnum, MemorySceneEnum
from app.enums.common import UserRoleEnum
from app.exceptions import AuthorizationException, BusinessException
from app.rbac.decorators import auth_only
from app.rbac.services.permission_service import PermissionService
from app.services.ai.account_ai_access_service import AccountAIAccessService
from app.services.ai.agent_service import AgentService
from app.services.ai.plain_text_input_ai_policy_service import (
    PlainTextInputAiPolicyService,
    is_plain_text_input_surface,
)
from app.services.tenant.quota_service import QuotaService

router = APIRouter(
    prefix="/ai/rich-text/operations",
    tags=[_("menu.tags.ai_writing")],
    include_in_schema=False,
)


class AIWritingRequest(BaseModel):
    """Internal rich-text AI payload schema / 内部富文本 AI 载荷 schema。"""

    model_config = ConfigDict(extra="forbid")

    selected_text: str = Field(default="", max_length=10000)
    before_text: str = Field(default="", max_length=5000)
    after_text: str = Field(default="", max_length=5000)
    context_title: str = Field(default="", max_length=200)
    document_title: str = Field(default="", max_length=200)
    document_id: int | None = Field(default=None, ge=1)
    document_type: str = Field(default="novusdoc", max_length=100)
    surface: str = Field(default="rich_text", max_length=100)
    instruction: str = Field(default="", max_length=2000)
    format_instruction: str = Field(default="", max_length=1000)
    target_lang: str = Field(default="", max_length=50)
    history: list[AIWritingHistoryTurn] | None = Field(default=None, max_length=10)
    plain_input_policy: PlainTextInputAiPolicyEnvelope | None = None


async def _ensure_tenant_agent_access(
    db: AsyncSession,
    *,
    tenant_id: int,
    agent_id: int,
    user_id: int,
    role_id: int | None,
) -> None:
    agent_service = AgentService(db, tenant_id)
    has_access = await agent_service.check_user_access(
        agent_id=agent_id,
        user_id=user_id,
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=role_id,
    )
    if not has_access:
        raise AuthorizationException(message=_("agent.access.error.no_permission"))


async def _ensure_tenant_rich_text_ai_access(
    db: AsyncSession,
    tenant_admin: ActiveTenantAdmin,
) -> None:
    """中文: 在企业端富文本 AI 操作进入智能体运行时前先失败关闭。

    EN: Fail closed before tenant rich-text AI operations reach the agent runtime.
    """

    await AccountAIAccessService(db).require_tenant_admin_ai_access(tenant_admin)
    api_check = await QuotaService.check_api_quota_for_tenant_id(
        db,
        tenant_admin.tenant_id,
    )
    if not api_check.allowed:
        raise BusinessException(
            message=api_check.message or _("quota.api_calls_exceeded"),
            code=ErrorCode.CONFLICT,
        )


@router.post("/{action}", summary="Stream rich-text AI operation")
@auth_only
async def stream_operation(
    request: Request,
    action: str,
    data: AIWritingRequest,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """Stream an editor-domain rich-text AI operation through AgentChat.

    / 通过 AgentChat 流式执行编辑器域富文本 AI 操作。
    """

    del request
    await _ensure_tenant_rich_text_ai_access(db, tenant_admin)
    if is_plain_text_input_surface(data.surface, data.document_type):
        await PlainTextInputAiPolicyService(db).require_tenant_enabled(
            tenant_admin,
            action=action,
            field_policy=data.plain_input_policy,
        )
    user_perms = await PermissionService(db).get_tenant_admin_permissions(tenant_admin)

    async def ensure_agent_access(agent_id: int) -> None:
        await _ensure_tenant_agent_access(
            db,
            tenant_id=tenant_admin.tenant_id,
            agent_id=agent_id,
            user_id=tenant_admin.id,
            role_id=tenant_admin.role_id,
        )

    return await stream_rich_text_operation(
        db=db,
        action=action,
        data=data,
        execution_tenant_id=tenant_admin.tenant_id,
        assignment_tenant_id=tenant_admin.tenant_id,
        user_id=tenant_admin.id,
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=tenant_admin.role_id,
        permissions=user_perms,
        memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
        memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
        ensure_agent_access=ensure_agent_access,
    )


__all__ = ["AIWritingRequest", "router"]
