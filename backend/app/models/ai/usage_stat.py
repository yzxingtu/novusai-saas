"""
AI 使用量统计模型 / AI Usage Statistics Model

按企业/用户/模型维度聚合 Token 使用量和费用统计
Aggregates token usage and cost statistics by tenant/user/model dimensions.
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.ai import RequestTypeEnum


class UsageStat(TenantModel):
    """
    AI 使用量统计模型

    按维度（企业/用户/模型/日期）聚合统计数据：
    - Token 使用量（输入/输出/总计）
    - 调用次数
    - 费用总计
    - 平均延迟
    """

    __tablename__ = "ai_usage_stats"

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "user_id": "user_id",
        "model_id": "model_id",
        "request_type": "request_type",
        "stat_date": "stat_date",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "stat_date": "stat_date",
        "total_tokens": "total_tokens",
        "call_count": "call_count",
        "total_cost": "total_cost",
    }

    # 统计维度
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("enum.ai_usage_stat.user_id")
    )

    model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("enum.ai_usage_stat.model_id")
    )

    request_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=RequestTypeEnum.CHAT.value,
        index=True,
        comment=_("enum.ai_usage_stat.request_type")
    )

    # 统计日期（按天聚合）
    stat_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment=_("enum.ai_usage_stat.stat_date")
    )

    # Token 统计
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.ai_usage_stat.input_tokens")
    )

    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.ai_usage_stat.output_tokens")
    )

    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment=_("enum.ai_usage_stat.total_tokens")
    )

    # 调用统计
    call_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment=_("enum.ai_usage_stat.call_count")
    )

    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.ai_usage_stat.success_count")
    )

    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.ai_usage_stat.failed_count")
    )

    # 费用统计（美元）
    total_cost: Mapped[float] = mapped_column(
        Numeric(10, 6),
        nullable=False,
        default=0,
        comment=_("enum.ai_usage_stat.total_cost")
    )

    # 性能统计
    avg_latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_usage_stat.avg_latency_ms")
    )

    max_latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_usage_stat.max_latency_ms")
    )

    # ==================== 索引和约束 ====================

    __table_args__ = (
        # 唯一约束：同一企业+用户+模型+请求类型+日期只能有一条记录
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "model_id",
            "request_type",
            "stat_date",
            name="uq_ai_usage_stat_dims",
        ),
        # 企业 + 日期复合索引（用于按企业查询某日期的所有统计）
        Index("idx_ai_usage_stats_tenant_date", "tenant_id", "stat_date"),
        # 用户 + 日期复合索引（用于用户级统计）
        Index("idx_ai_usage_stats_user_date", "user_id", "stat_date"),
        # 模型 + 日期复合索引（用于模型使用统计）
        Index("idx_ai_usage_stats_model_date", "model_id", "stat_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<UsageStat(id={self.id}, tenant_id={self.tenant_id}, "
            f"user_id={self.user_id}, model_id={self.model_id}, "
            f"stat_date={self.stat_date}, total_tokens={self.total_tokens})>"
        )

    def increment(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0,
        call_count: int = 1,
        success: bool = True,
        latency_ms: int | None = None
    ):
        """
        增加统计数据

        Args:
            input_tokens: 输入 tokens
            output_tokens: 输出 tokens
            cost: 费用
            call_count: 调用次数
            success: 是否成功
            latency_ms: 延迟（毫秒）
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.call_count += call_count

        if success:
            self.success_count += call_count
        else:
            self.failed_count += call_count

        self.total_cost = float(self.total_cost) + cost

        # 更新延迟统计
        if latency_ms is not None:
            if self.avg_latency_ms is None:
                self.avg_latency_ms = latency_ms
                self.max_latency_ms = latency_ms
            else:
                # 重新计算平均值（使用 round 避免整除截断累积偏差）
                prev_count = self.call_count - call_count
                total_latency = self.avg_latency_ms * prev_count + latency_ms
                self.avg_latency_ms = round(total_latency / self.call_count)
                self.max_latency_ms = max(self.max_latency_ms or 0, latency_ms)


if TYPE_CHECKING:
    pass


__all__ = ["UsageStat"]
