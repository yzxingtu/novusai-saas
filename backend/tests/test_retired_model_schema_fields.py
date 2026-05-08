"""中文: 测试类型 behavioral / structural。

退役模型和 schema 字段必须 fail closed，不能保留为可写兼容入口。

EN: Test type behavioral / structural.

Retired model and schema fields must fail closed instead of staying as writable
compatibility surfaces.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.enums.base import (
    BaseEnum,
    IntEnum,
    LabeledEnum,
    LabeledIntEnum,
    LabeledStrEnum,
    StrEnum,
)
from app.enums.common import SortOrderEnum, StatusEnum
from app.models.ai.agent_access import AgentAccess
from app.models.ai.agent_conversation import AgentConversation
from app.models.tenant.tenant import Tenant
from app.schemas.ai.agent_chat import AgentChatRequest
from app.schemas.system.admin import (
    AdminResponse,
    AdminUpdateProfileRequest,
    AdminUpdateRequest,
)
from app.schemas.system.admin_org_node import (
    AdminOrgNodeLeaderResponse,
    AdminOrgNodeMemberResponse,
    AdminOrgNodeUpdateMemberRequest,
)
from app.schemas.system.role import (
    AdminRoleMemberResponse,
    AdminRoleUpdateMemberRequest,
)
from app.schemas.system.tenant import (
    TenantCreateRequest,
    TenantResponse,
    TenantUpdateRequest,
)
from app.schemas.tenant.admin import (
    TenantAdminLoginRequest,
    TenantAdminResponse,
    TenantAdminUpdateProfileRequest,
    TenantAdminUpdateRequest,
)
from app.schemas.tenant.tenant_org_node import (
    TenantOrgNodeLeaderResponse,
    TenantOrgNodeMemberResponse,
    TenantOrgNodeUpdateMemberRequest,
)
from app.schemas.tenant.user import (
    TenantUserProfileUpdateRequest,
    TenantUserResponse,
    TenantUserUpdateRequest,
)


def test_structural_enum_short_names_are_real_base_classes() -> None:
    """中文: 测试类型 structural；短枚举名不再是模块级别名。

    EN: Test type structural; short enum names are no longer module-level aliases.
    """
    assert BaseEnum is not LabeledEnum
    assert IntEnum is not LabeledIntEnum
    assert StrEnum is not LabeledStrEnum
    assert issubclass(BaseEnum, LabeledEnum)
    assert issubclass(IntEnum, LabeledIntEnum)
    assert issubclass(StrEnum, LabeledStrEnum)
    assert issubclass(StatusEnum, LabeledIntEnum)
    assert issubclass(SortOrderEnum, LabeledStrEnum)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("plan", "enterprise"),
        ("settings", {"theme": "classic"}),
    ],
)
def test_behavioral_tenant_create_rejects_retired_fields(
    field: str,
    value: object,
) -> None:
    """中文: 测试类型 behavioral；企业创建请求拒绝退役字段。

    EN: Test type behavioral; tenant create rejects retired request fields.
    """
    payload: dict[str, Any] = {
        "name": "Acme",
        "admin_username": "owner",
        "admin_email": "owner@example.com",
        "admin_password": "secret123",
        field: value,
    }

    with pytest.raises(ValidationError, match=field):
        TenantCreateRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("plan", "enterprise"),
        ("settings", {"theme": "classic"}),
    ],
)
def test_behavioral_tenant_update_rejects_retired_fields(
    field: str,
    value: object,
) -> None:
    """中文: 测试类型 behavioral；企业更新请求拒绝退役字段。

    EN: Test type behavioral; tenant update rejects retired request fields.
    """
    with pytest.raises(ValidationError, match=field):
        TenantUpdateRequest.model_validate({"name": "Acme Updated", field: value})


def test_behavioral_tenant_response_does_not_expose_retired_fields() -> None:
    """中文: 测试类型 behavioral；企业响应不暴露退役存储字段。

    EN: Test type behavioral; tenant responses do not expose retired storage fields.
    """
    now = datetime.now(timezone.utc)
    response = TenantResponse.model_validate(
        {
            "id": 1,
            "code": "acme",
            "name": "Acme",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "plan": "enterprise",
            "settings": {"theme": "classic"},
        }
    )

    dumped = response.model_dump()
    assert "plan" not in dumped
    assert "settings" not in dumped


def test_behavioral_tenant_model_rejects_retired_column_writes() -> None:
    """中文: 测试类型 behavioral；Tenant 退役列在模型写入时只读拒绝。

    EN: Test type behavioral; Tenant retired columns are read-only at model writes.
    """
    tenant = Tenant(name="Acme", code="acme")

    with pytest.raises(ValueError, match="plan_id"):
        tenant.plan = "enterprise"
    with pytest.raises(ValueError, match="ConfigService"):
        tenant.settings = {"theme": "classic"}

    tenant.plan = None
    tenant.settings = None
    assert tenant.plan is None
    assert tenant.settings is None


def test_behavioral_agent_conversation_rejects_retired_message_blob_writes() -> None:
    """中文: 测试类型 behavioral；对话消息必须写入独立消息行。

    EN: Test type behavioral; conversation messages must be written as rows.
    """
    conversation = AgentConversation(agent_id=1, tenant_id=1)

    conversation.messages = []
    conversation.messages = None
    with pytest.raises(ValueError, match="message_list"):
        conversation.messages = [{"role": "user", "content": "hello"}]


def test_behavioral_agent_chat_request_rejects_retired_messages_input() -> None:
    """中文: 测试类型 behavioral；对话请求不再接受批量 messages 输入。

    EN: Test type behavioral; chat requests no longer accept batch messages
    input.
    """
    with pytest.raises(ValidationError, match="messages"):
        AgentChatRequest.model_validate({"messages": ["hello"]})

    assert AgentChatRequest.model_validate({"message": "hello"}).message == "hello"


def test_structural_user_agent_chat_route_does_not_forward_retired_messages() -> None:
    """中文: 测试类型 structural；用户端路由不再读取退役 messages 请求字段。

    EN: Test type structural; the user chat route no longer reads the retired
    messages request field.
    """
    backend_root = Path(__file__).resolve().parents[1]
    source = (backend_root / "app/api/user/agent_chat.py").read_text(encoding="utf-8")

    assert "data.messages" not in source


def test_behavioral_agent_access_rejects_retired_access_type_writes() -> None:
    """中文: 测试类型 behavioral；用户发布访问类型不再写入 AgentAccess。

    EN: Test type behavioral; user publication access type is no longer written here.
    """
    access = AgentAccess(agent_id=1, tenant_id=1)

    with pytest.raises(ValueError, match="TenantAgentPublication"):
        access.access_type = "all_users"


def test_behavioral_tenant_admin_login_requires_explicit_tenant_code() -> None:
    """中文: 测试类型 behavioral；企业管理员登录必须显式给出企业编码。

    EN: Test type behavioral; tenant admin login requires an explicit tenant
    code.
    """
    with pytest.raises(ValidationError, match="tenant_code"):
        TenantAdminLoginRequest.model_validate(
            {"username": "owner", "password": "secret123"}
        )

    assert (
        TenantAdminLoginRequest.model_validate(
            {
                "username": "owner",
                "password": "secret123",
                "tenant_code": "acme",
            }
        ).tenant_code
        == "acme"
    )


@pytest.mark.parametrize(
    "schema",
    [
        AdminUpdateRequest,
        AdminUpdateProfileRequest,
        AdminOrgNodeUpdateMemberRequest,
        AdminRoleUpdateMemberRequest,
        TenantAdminUpdateRequest,
        TenantAdminUpdateProfileRequest,
        TenantOrgNodeUpdateMemberRequest,
        TenantUserUpdateRequest,
        TenantUserProfileUpdateRequest,
    ],
)
def test_behavioral_avatar_write_rejects_url_values(schema: type) -> None:
    """中文: 测试类型 behavioral；头像写入只接受附件 ID。

    EN: Test type behavioral; avatar writes accept attachment IDs only.
    """
    with pytest.raises(ValidationError, match="avatar"):
        schema.model_validate({"avatar": "https://cdn.example/avatar.png"})

    assert schema.model_validate({"avatar": 42}).avatar == "42"


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (
            AdminResponse,
            {
                "id": 1,
                "username": "admin",
                "email": "admin@example.com",
                "is_active": True,
                "is_super": False,
            },
        ),
        (
            TenantAdminResponse,
            {
                "id": 2,
                "tenant_id": 10,
                "username": "tenant-admin",
                "email": "ta@example.com",
                "is_active": True,
                "is_owner": False,
            },
        ),
        (
            TenantUserResponse,
            {
                "id": 3,
                "tenant_id": 10,
                "username": "tenant-user",
                "email": "tu@example.com",
                "is_active": True,
            },
        ),
        (
            AdminOrgNodeLeaderResponse,
            {
                "id": 4,
                "username": "leader-admin",
            },
        ),
        (
            AdminOrgNodeMemberResponse,
            {
                "id": 5,
                "username": "org-admin",
                "email": "org-admin@example.com",
            },
        ),
        (
            AdminRoleMemberResponse,
            {
                "id": 6,
                "username": "role-admin",
                "email": "role-admin@example.com",
            },
        ),
        (
            TenantOrgNodeLeaderResponse,
            {
                "id": 7,
                "username": "tenant-leader",
            },
        ),
        (
            TenantOrgNodeMemberResponse,
            {
                "id": 8,
                "username": "tenant-member",
                "email": "tenant-member@example.com",
            },
        ),
    ],
)
def test_behavioral_avatar_response_hides_url_values(
    schema: type,
    payload: dict[str, Any],
) -> None:
    """中文: 测试类型 behavioral；响应不暴露非 ID 形态的头像存量值。

    EN: Test type behavioral; responses do not expose non-ID stored avatars.
    """
    response = schema.model_validate(
        {
            **payload,
            "avatar": "https://cdn.example/avatar.png",
            "created_at": datetime.now(timezone.utc),
        }
    )

    assert response.avatar is None
