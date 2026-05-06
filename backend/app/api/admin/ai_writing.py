"""Admin rich-text AI operation stream router / 管理端富文本 AI 操作流路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.shared._rich_text_ai_operations import stream_rich_text_operation
from app.api.shared.rich_text_ai_schemas import (
    AIWritingHistoryTurn,
    PlainTextInputAiPolicyEnvelope,
)
from app.configs.service import PLATFORM_TENANT_ID
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.enums.agent import MemoryChannelEnum, MemorySceneEnum
from app.enums.common import UserRoleEnum
from app.rbac.decorators import auth_only
from app.rbac.services.permission_service import PermissionService
from app.services.ai.account_ai_access_service import AccountAIAccessService
from app.services.ai.plain_text_input_ai_policy_service import (
    PlainTextInputAiPolicyService,
    is_plain_text_input_surface,
)

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


@router.post("/{action}", summary="Stream rich-text AI operation")
@auth_only
async def stream_operation(
    request: Request,
    action: str,
    data: AIWritingRequest,
    db: DbSession,
    admin: ActiveAdmin,
):
    """Stream an editor-domain rich-text AI operation through AgentChat.

    / 通过 AgentChat 流式执行编辑器域富文本 AI 操作。
    """

    del request
    await AccountAIAccessService(db).require_platform_admin_ai_access(admin)
    if is_plain_text_input_surface(data.surface, data.document_type):
        await PlainTextInputAiPolicyService(db).require_admin_enabled(
            admin,
            action=action,
            field_policy=data.plain_input_policy,
        )
    user_perms = await PermissionService(db).get_admin_permissions(admin)
    return await stream_rich_text_operation(
        db=db,
        action=action,
        data=data,
        execution_tenant_id=PLATFORM_TENANT_ID,
        assignment_tenant_id=None,
        user_id=admin.id,
        user_role=UserRoleEnum.PLATFORM_ADMIN.value,
        user_role_id=admin.org_node_id,
        permissions=user_perms,
        memory_scene=MemorySceneEnum.ADMIN_CHAT.value,
        memory_channel=MemoryChannelEnum.ADMIN_CHAT.value,
    )


__all__ = ["AIWritingRequest", "router"]
