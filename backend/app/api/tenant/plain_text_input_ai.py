"""Tenant plain input AI policy route / 企业端普通输入框 AI 策略路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.ai.plain_text_input_ai_policy_service import (
    PlainTextInputAiPolicyService,
)

router = APIRouter(
    prefix="/ai/plain-text-input",
    tags=[_("menu.tags.ai_writing")],
    include_in_schema=False,
)


@router.get("/policy", summary="Get plain input AI policy")
@auth_only
async def get_plain_text_input_ai_policy(
    request: Request,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """中文: 返回企业端普通输入框选区 AI 的生效策略。

    EN: Return the effective selected-text AI policy for tenant-admin plain
    input controls.
    """

    del request
    policy = await PlainTextInputAiPolicyService(db).get_tenant_policy(tenant_admin)
    return success(data=policy, message=_("common.success"))


__all__ = ["router"]
