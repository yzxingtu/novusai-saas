"""
AI 调用日志模型 / AI Call Log Model

记录所有 AI 调用请求和响应，用于计量计费和监控
Records all AI call requests and responses for metering, billing and monitoring.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, JSON, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.ai import CallStatusEnum, RequestTypeEnum


class AICallLog(TenantModel):
    """
    AI 调用日志模型 / AI call log model.

    记录每次 AI 调用的详细信息，包括：
    - 企业和用户信息
    - 使用的供应商和模型
    - Token 使用量和费用
    - 调用状态和错误信息
    """

    __tablename__ = "ai_call_logs"

    __ai_policy__ = {
        "label": "AI 调用日志",
        "keywords": ["调用日志", "call_log", "AI调用"],
        "allow_read": True,
    }

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "billing_tenant_id": "billing_tenant_id",
        "agent_id": "agent_id",
        "conversation_id": "conversation_id",
        "user_id": "user_id",
        "user_type": "user_type",
        "actor_user_id": "actor_user_id",
        "actor_user_type": "actor_user_type",
        "access_channel": "access_channel",
        "agent_owner_type": "agent_owner_type",
        "agent_distribution_mode": "agent_distribution_mode",
        "provider_id": "provider_id",
        "model_id": "model_id",
        "routed_model_id": "routed_model_id",
        "request_type": "request_type",
        "status": "status",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "latency_ms": "latency_ms",
        "total_tokens": "total_tokens",
        "cost": "cost",
    }

    # 用户信息
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("enum.ai_call_log.user_id")
    )
    user_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment=_("enum.ai_call_log.user_type")
    )
    billing_tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="计费归属企业 ID / Billing tenant ID",
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="调用方用户 ID / Actor user ID",
    )
    actor_user_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="调用方用户类型 / Actor user type",
    )
    access_channel: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="访问渠道 / Access channel",
    )
    agent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联智能体 ID / Related agent ID",
    )
    conversation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联对话 ID / Related conversation ID",
    )

    # 供应商和模型
    provider_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_providers.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment=_("enum.ai_call_log.provider_id")
    )
    model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment=_("enum.ai_call_log.model_id")
    )

    # 请求类型
    request_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=RequestTypeEnum.CHAT.value,
        index=True,
        comment=_("enum.ai_call_log.request_type")
    )

    # Token 使用量
    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_call_log.input_tokens")
    )
    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_call_log.output_tokens")
    )
    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("enum.ai_call_log.total_tokens")
    )

    # 费用（美元）
    cost: Mapped[float | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
        comment=_("enum.ai_call_log.cost")
    )

    # 延迟（毫秒）
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_call_log.latency_ms")
    )

    # 调用状态
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CallStatusEnum.SUCCESS.value,
        index=True,
        comment=_("enum.ai_call_log.status")
    )

    # 错误信息
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("enum.ai_call_log.error_message")
    )

    # 请求哈希（用于缓存命中检测）
    request_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment=_("enum.ai_call_log.request_hash")
    )

    # 请求元数据（JSON 格式）
    # 例如：请求参数、响应摘要等
    request_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment=_("enum.ai_call_log.request_metadata")
    )

    # 路由信息（多模型路由结果）
    routed_model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment=_("enum.ai_call_log.routed_model_id"),
    )
    route_reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment=_("enum.ai_call_log.route_reason"),
    )
    agent_owner_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="智能体归属类型快照 / Agent owner type snapshot",
    )
    agent_owner_tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="智能体归属企业快照 / Agent owner tenant snapshot",
    )
    agent_distribution_mode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="智能体分发模式快照 / Agent distribution mode snapshot",
    )
    tenant_publication_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_agent_publications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="企业用户发布记录 ID / Tenant agent publication ID",
    )
    publication_enabled_snapshot: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="发布启用状态快照 / Publication enabled snapshot",
    )
    publication_access_type_snapshot: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="发布访问类型快照 / Publication access type snapshot",
    )
    # 展示快照（不依赖当前 agents/tenants/models 行，避免改名/删除导致历史不可读）
    agent_id_snapshot: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="调用时智能体 ID 快照（无外键）/ Agent id snapshot at call time (no FK)",
    )
    agent_name_snapshot: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="调用时智能体名称快照 / Agent name snapshot at call time",
    )
    billing_tenant_name_snapshot: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="计费企业名称快照 / Billing tenant name snapshot",
    )
    model_name_snapshot: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="模型名称快照 / Model name snapshot",
    )
    provider_name_snapshot: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="供应商名称快照 / Provider name snapshot",
    )

    # ==================== 索引 ====================

    __table_args__ = (
        # 企业 + 创建时间复合索引（用于按企业查询最近记录）
        Index("idx_ai_call_logs_tenant_created", "tenant_id", "created_at"),
        Index("idx_ai_call_logs_billing_tenant_created", "billing_tenant_id", "created_at"),
        Index("idx_ai_call_logs_agent_created", "agent_id", "created_at"),
        Index("idx_ai_call_logs_conv_created", "conversation_id", "created_at"),
        # 用户 + 状态复合索引（用于用户调用统计）
        Index("idx_ai_call_logs_user_status", "user_id", "status"),
        # 模型 + 时间复合索引（用于模型使用统计）
        Index("idx_ai_call_logs_model_created", "model_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AICallLog(id={self.id}, tenant_id={self.tenant_id}, model_id={self.model_id}, status={self.status})>"


if TYPE_CHECKING:
    pass


__all__ = ["AICallLog"]
