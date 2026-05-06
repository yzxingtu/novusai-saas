"""
通知模板模型 / Notification Template Model

系统预置 + 企业自定义的通知模板。每种通知类型对应一个模板，定义标题/正文模板、投递渠道、优先级。
System preset + tenant custom notification templates. Each notification type has a template defining title/body, channels, priority.
"""

from sqlalchemy import Boolean, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NotificationTemplate(BaseModel):
    """
    通知模板 / Notification template.

    - code: 模板编码，如 'ai.batch_complete'
    - category: 分类（system/ai/task/biz/audit）
    - title_template: 标题模板，支持 {variable} 占位符
    - body_template: 正文模板（Markdown）
    - channels: 投递渠道列表 ['ws', 'inbox', 'email']
    - priority: 优先级 low/normal/high/urgent
    - scope: platform/tenant/plugin/source
    - source: 模板来源（core/plugin/import 等）
    - plugin_name: 插件模板所属插件
    - is_enabled: 是否启用
    - is_system: 是否系统内置（不可删除）
    - tenant_id: NULL=平台级，有值=企业自定义
    - override_of: 被覆盖的模板 ID
    - locked_fields: 不允许覆盖的字段列表
    """

    __tablename__ = "notification_templates"

    __table_args__ = (
        Index(
            "uq_notification_templates_platform_code",
            "code",
            unique=True,
            postgresql_where=text(
                "is_deleted = false AND scope = 'platform' AND tenant_id IS NULL"
            ),
        ),
        Index(
            "uq_notification_templates_tenant_code",
            "tenant_id",
            "code",
            unique=True,
            postgresql_where=text(
                "is_deleted = false AND scope = 'tenant' AND tenant_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_notification_templates_plugin_code",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false AND scope = 'plugin'"),
        ),
        Index(
            "uq_notification_templates_source_code",
            "source",
            "code",
            unique=True,
            postgresql_where=text(
                "is_deleted = false AND scope = 'source' AND source IS NOT NULL"
            ),
        ),
    )

    __filterable__ = {
        "id": "id",
        "code": "code",
        "category": "category",
        "priority": "priority",
        "scope": "scope",
        "source": "source",
        "plugin_name": "plugin_name",
        "is_enabled": "is_enabled",
        "is_system": "is_system",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id",
        "code",
        "category",
        "priority",
        "scope",
        "source",
        "plugin_name",
        "created_at",
    }

    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="模板编码",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="分类: system/ai/task/biz/audit",
    )
    title_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="标题模板",
    )
    body_template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="正文模板（Markdown）",
    )
    channels: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(20)),
        nullable=True,
        default=["ws", "inbox"],
        comment="投递渠道",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        comment="优先级: low/normal/high/urgent",
    )
    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="platform",
        index=True,
        comment="作用域: platform/tenant/plugin/source",
    )
    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="模板来源: core/plugin/import 等",
    )
    plugin_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="插件名称（插件模板所属）",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        nullable=False,
        comment="是否启用",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否系统内置",
    )
    tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="企业 ID（NULL=系统级）",
    )
    override_of: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="覆盖的模板 ID",
    )
    locked_fields: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
        comment="锁定字段列表",
    )

    def __repr__(self) -> str:
        return f"<NotificationTemplate(id={self.id}, code={self.code})>"


__all__ = ["NotificationTemplate"]
