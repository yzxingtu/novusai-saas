"""
通知模板种子数据

系统启动时幂等插入 32 个预置通知模板。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.models.common.notification_template import NotificationTemplate

logger = LogManager.get_logger("app")

# 所有预置模板定义
SEED_TEMPLATES: list[dict] = [
    # ===== system (5) =====
    {"code": "system.announcement", "category": "system", "title_template": "notification.system.announcement.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "system.maintenance", "category": "system", "title_template": "notification.system.maintenance.title", "channels": ["ws", "inbox"], "priority": "high"},
    {"code": "system.version_update", "category": "system", "title_template": "notification.system.version_update.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "system.security_alert", "category": "system", "title_template": "notification.system.security_alert.title", "channels": ["ws", "inbox", "email"], "priority": "urgent"},
    {"code": "system.welcome", "category": "system", "title_template": "notification.system.welcome.title", "channels": ["inbox"], "priority": "normal"},
    # ===== ai (10) =====
    {"code": "ai.chat_complete", "category": "ai", "title_template": "notification.ai.chat_complete.title", "channels": ["ws"], "priority": "normal"},
    {"code": "ai.image_ready", "category": "ai", "title_template": "notification.ai.image_ready.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "ai.batch_progress", "category": "ai", "title_template": "notification.ai.batch_progress.title", "channels": ["ws"], "priority": "normal"},
    {"code": "ai.batch_complete", "category": "ai", "title_template": "notification.ai.batch_complete.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "ai.batch_failed", "category": "ai", "title_template": "notification.ai.batch_failed.title", "channels": ["ws", "inbox"], "priority": "high"},
    {"code": "ai.kb_index_progress", "category": "ai", "title_template": "notification.ai.kb_index_progress.title", "channels": ["ws"], "priority": "normal"},
    {"code": "ai.kb_index_complete", "category": "ai", "title_template": "notification.ai.kb_index_complete.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "ai.kb_index_failed", "category": "ai", "title_template": "notification.ai.kb_index_failed.title", "channels": ["ws", "inbox"], "priority": "high"},
    {"code": "ai.quota_warning", "category": "ai", "title_template": "notification.ai.quota_warning.title", "channels": ["ws", "inbox"], "priority": "high"},
    {"code": "ai.quota_exhausted", "category": "ai", "title_template": "notification.ai.quota_exhausted.title", "channels": ["ws", "inbox", "email"], "priority": "urgent"},
    # ===== task (5) =====
    {"code": "task.completed", "category": "task", "title_template": "notification.task.completed.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "task.failed", "category": "task", "title_template": "notification.task.failed.title", "channels": ["ws", "inbox"], "priority": "high"},
    {"code": "task.export_ready", "category": "task", "title_template": "notification.task.export_ready.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "task.import_complete", "category": "task", "title_template": "notification.task.import_complete.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "task.import_failed", "category": "task", "title_template": "notification.task.import_failed.title", "channels": ["ws", "inbox"], "priority": "high"},
    # ===== biz (8) =====
    {"code": "biz.tenant_created", "category": "biz", "title_template": "notification.biz.tenant_created.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "biz.tenant_expired", "category": "biz", "title_template": "notification.biz.tenant_expired.title", "channels": ["ws", "inbox", "email"], "priority": "high"},
    {"code": "biz.plan_changed", "category": "biz", "title_template": "notification.biz.plan_changed.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "biz.plugin_installed", "category": "biz", "title_template": "notification.biz.plugin_installed.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "biz.plugin_update_available", "category": "biz", "title_template": "notification.biz.plugin_update_available.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "biz.domain_ssl_expiring", "category": "biz", "title_template": "notification.biz.domain_ssl_expiring.title", "channels": ["ws", "inbox", "email"], "priority": "high"},
    {"code": "biz.storage_warning", "category": "biz", "title_template": "notification.biz.storage_warning.title", "channels": ["ws", "inbox"], "priority": "high"},
    {"code": "biz.sub_admin_created", "category": "biz", "title_template": "notification.biz.sub_admin_created.title", "channels": ["ws", "inbox"], "priority": "normal"},
    # ===== audit (4) =====
    {"code": "audit.suspicious_login", "category": "audit", "title_template": "notification.audit.suspicious_login.title", "channels": ["ws", "inbox", "email"], "priority": "urgent"},
    {"code": "audit.permission_changed", "category": "audit", "title_template": "notification.audit.permission_changed.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "audit.role_changed", "category": "audit", "title_template": "notification.audit.role_changed.title", "channels": ["ws", "inbox"], "priority": "normal"},
    {"code": "audit.account_locked", "category": "audit", "title_template": "notification.audit.account_locked.title", "channels": ["ws", "inbox"], "priority": "high"},
]


async def seed_notification_templates(db: AsyncSession) -> dict[str, int]:
    """
    幂等插入通知模板种子数据（单次查询 + 批量插入）

    Returns:
        {"created": N, "existing": M}
    """
    # 一次性查询所有已有 code，避免 N+1
    all_codes = [t["code"] for t in SEED_TEMPLATES]
    result = await db.execute(
        select(NotificationTemplate.code).where(
            NotificationTemplate.code.in_(all_codes),
        )
    )
    existing_codes = {row[0] for row in result.all()}

    created = 0
    existing = len(existing_codes)

    for tpl_data in SEED_TEMPLATES:
        if tpl_data["code"] in existing_codes:
            continue

        tpl = NotificationTemplate(
            code=tpl_data["code"],
            category=tpl_data["category"],
            title_template=tpl_data["title_template"],
            channels=tpl_data["channels"],
            priority=tpl_data["priority"],
            is_system=True,
        )
        db.add(tpl)
        created += 1

    if created > 0:
        await db.commit()

    logger.info(
        "Notification templates seeded: created=%d existing=%d",
        created, existing,
    )
    return {"created": created, "existing": existing}


__all__ = ["seed_notification_templates"]
