"""
通知模板 Repository

提供通知模板的数据访问层。
"""

from app.core.base_repository import BaseRepository
from app.models.common.notification_template import NotificationTemplate


class NotificationTemplateRepository(BaseRepository[NotificationTemplate]):
    """通知模板仓库（全局，无租户过滤）"""

    model = NotificationTemplate


__all__ = ["NotificationTemplateRepository"]
