"""
邮件日志仓储

提供邮件日志的数据访问操作
"""

from app.core.base_repository import BaseRepository
from app.models.system.email_log import EmailLog


class EmailLogRepository(BaseRepository[EmailLog]):
    """邮件日志仓储"""

    model = EmailLog

    _scope_fields = {
        "admin": {
            "id", "to_address", "subject", "status",
            "triggered_by", "tenant_id", "created_at", "sent_at",
        },
    }

    async def get_by_status(self, status: str, limit: int = 50) -> list[EmailLog]:
        from sqlalchemy import select
        stmt = (
            select(EmailLog)
            .where(EmailLog.status == status, EmailLog.is_deleted.is_(False))
            .order_by(EmailLog.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
