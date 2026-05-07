"""
AI 操作审计日志模型 / AI Action Audit Log Model

记录 AI 工具调用与业务操作的审计日志，用于安全追溯、合规审计和操作分析。
Records audit logs for AI tool invocations and business operations for tracing, compliance, and analysis.
"""

from sqlalchemy import JSON, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.agent import ActionStatusEnum


class AIActionLog(TenantModel):
    """
    AI 操作审计日志 / AI action audit log.

    记录每次 AI 工具或 API Action 的详细信息，包括：
    - 操作者（operator_id 关联 tenant_admins）
    - 操作类型和安全等级
    - 请求和响应数据（JSON）
    - 执行状态和耗时
    """

    __tablename__ = "ai_action_logs"

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "agent_id": "agent_id",
        "conversation_id": "conversation_id",
        "execution_decision_id": "execution_decision_id",
        "trace_id": "trace_id",
        "tool_call_id": "tool_call_id",
        "operator_id": "operator_id",
        "operator_type": "operator_type",
        "skill_id": "skill_id",
        "action_name": "action_name",
        "action_type": "action_type",
        "action_level": "action_level",
        "status": "status",
        "created_at": "created_at",
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "duration_ms": "duration_ms",
    }

    # 智能体 ID
    agent_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment=_("ai_action_log.field.agent_id"),
    )

    # 对话 ID
    conversation_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("ai_action_log.field.conversation_id"),
    )

    execution_decision_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Linked execution decision ID / 关联执行决策 ID",
    )

    trace_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Trace ID / 链路追踪 ID",
    )

    tool_call_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="LLM tool_call_id / LLM 工具调用 ID",
    )

    # 来源 Skill ID（可为 NULL，向后兼容旧数据）
    skill_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("ai_action_log.field.skill_id"),
    )

    # 操作者 ID（关联 admins / tenant_admins / tenant_users）
    operator_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("ai_action_log.field.operator_id"),
    )

    # 操作者类型快照（platform_admin / tenant_admin / tenant_user）
    operator_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="操作者类型快照 / Operator type snapshot",
    )

    # 智能体名称快照
    agent_name_snapshot: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="智能体名称快照 / Agent name snapshot",
    )

    # 智能体头像快照
    agent_avatar_snapshot: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="智能体头像快照 / Agent avatar snapshot",
    )

    # 操作者用户名快照
    operator_name_snapshot: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="操作者用户名快照 / Operator username snapshot",
    )

    # 操作者昵称快照
    operator_nickname_snapshot: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="操作者昵称快照 / Operator nickname snapshot",
    )

    # 操作者头像快照
    operator_avatar_snapshot: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="操作者头像快照 / Operator avatar snapshot",
    )

    # 操作者扩展身份快照（组织/显示角色/状态等）
    operator_snapshot: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="操作者扩展身份快照 / Operator extended identity snapshot",
    )

    # 中文: 操作名称示例使用业务动作，避免把已移除的搜索工具展示为能力。
    # EN: Use business-action examples so retired search tools are not shown as capabilities.
    action_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=_("ai_action_log.field.action_name"),
    )

    # 操作类型（对应 ActionTypeEnum: query/action/confirm）
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=_("ai_action_log.field.action_type"),
    )

    # 安全等级（对应 ActionLevelEnum: read/safe_write/dangerous）
    action_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=_("ai_action_log.field.action_level"),
    )

    # 请求数据（JSON 格式，如 SQL 语句、API 参数等）
    request_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment=_("ai_action_log.field.request_data"),
    )

    # 响应数据（JSON 格式，如查询结果摘要、操作结果等）
    response_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment=_("ai_action_log.field.response_data"),
    )

    # 执行状态（success/failed/rejected/pending_confirm）
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ActionStatusEnum.SUCCESS.value,
        index=True,
        comment=_("ai_action_log.field.status"),
    )

    # 错误信息 / Error message
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("ai_action_log.field.error_message"),
    )

    # 执行耗时（毫秒） / Duration in ms
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("ai_action_log.field.duration_ms"),
    )

    # ==================== 索引 ==================== / Indexes

    __table_args__ = (
        # 操作类型 + 创建时间复合索引（用于按类型查询审计记录） / type + created_at
        Index("idx_ai_action_logs_type_created", "action_type", "created_at"),
        # 企业 + 创建时间复合索引（用于按企业查询最近记录） / tenant + created_at
        Index("idx_ai_action_logs_tenant_created", "tenant_id", "created_at"),
        # 操作者 + 创建时间复合索引（用于按操作者追溯记录） / operator + created_at
        Index("idx_ai_action_logs_operator_created", "operator_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AIActionLog(id={self.id}, tenant_id={self.tenant_id}, "
            f"action_name={self.action_name}, status={self.status})>"
        )


__all__ = ["AIActionLog"]
