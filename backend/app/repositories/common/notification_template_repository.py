"""
通知模板 Repository / Notification Template Repository

提供通知模板的数据访问层。
Provides notification template data access layer.
"""

from app.core.base_repository import BaseRepository
from app.models.common.notification_template import NotificationTemplate


class NotificationTemplateRepository(BaseRepository[NotificationTemplate]):
    """通知模板仓库（全局，无企业过滤）"""

    model = NotificationTemplate


__all__ = ["NotificationTemplateRepository"]
