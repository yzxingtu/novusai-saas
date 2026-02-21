"""
通知模板模型

系统预置 + 租户自定义的通知模板。
每种通知类型对应一个模板，定义标题/正文模板、投递渠道、优先级。
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NotificationTemplate(BaseModel):
    """
    通知模板

    - code: 模板编码，如 'ai.batch_complete'
    - category: 分类（system/ai/task/biz/audit）
    - title_template: 标题模板，支持 {variable} 占位符
    - body_template: 正文模板（Markdown）
    - channels: 投递渠道列表 ['ws', 'inbox', 'email']
    - priority: 优先级 low/normal/high/urgent
    - is_system: 是否系统内置（不可删除）
    - tenant_id: NULL=系统级，有值=租户自定义
    """

    __tablename__ = "notification_templates"

    code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="模板编码",
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="分类: system/ai/task/biz/audit",
    )
    title_template: Mapped[str] = mapped_column(
        Text, nullable=False, comment="标题模板",
    )
    body_template: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="正文模板（Markdown）",
    )
    channels: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(20)),
        nullable=True,
        default=["ws", "inbox"],
        comment="投递渠道",
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal",
        comment="优先级: low/normal/high/urgent",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否系统内置",
    )
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True, comment="租户 ID（NULL=系统级）",
    )

    def __repr__(self) -> str:
        return f"<NotificationTemplate(id={self.id}, code={self.code})>"


__all__ = ["NotificationTemplate"]
