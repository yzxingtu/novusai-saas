"""
通知模板种子数据 / Notification Template Seed Data.

Idempotently inserts/updates preset notification templates on system startup.
Each template contains readable Chinese titles and bodies (supports {variable} placeholders).
系统启动时幂等插入/更新预置通知模板。
每个模板包含可读的中文标题和正文（支持 {variable} 占位符）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.models.common.notification_template import NotificationTemplate

logger = LogManager.get_logger("app")

# All preset template definitions / 所有预置模板定义
# title_template / body_template support {variable} placeholders, rendered by NotificationService._render_template
# title_template / body_template 支持 {variable} 占位符，由 NotificationService._render_template 渲染
SEED_TEMPLATES: list[dict] = [
    # ===== system (4) / 系统类 4 条 =====
    {
        "code": "system.password_reset",
        "category": "system",
        "title_template": "密码已重置",
        "body_template": "您的密码已被管理员重置，请登录后及时修改密码。",
        "channels": ["email"],
        "priority": "high",
    },
    {
        "code": "system.tenant_welcome",
        "category": "system",
        "title_template": "企业创建成功",
        "body_template": "企业 {tenant_name} 已创建成功，管理员 {admin_name} 可前往登录。",
        "channels": ["inbox", "email"],
        "priority": "normal",
    },
    {
        "code": "system.task_failure",
        "category": "system",
        "title_template": "定时任务执行失败：{task_name}",
        "body_template": "任务 {task_name} 执行失败，错误信息：{error}",
        "channels": ["inbox", "email"],
        "priority": "high",
    },
    {
        "code": "system.ssl_expiry",
        "category": "system",
        "title_template": "SSL 证书即将到期：{domain}",
        "body_template": "域名 {domain} 的 SSL 证书将在 {days_remaining} 天后到期，请及时续期。",
        "channels": ["inbox", "email"],
        "priority": "high",
    },
    # ===== ai (6) / AI 类 6 条 =====
    {
        "code": "ai.batch_progress",
        "category": "ai",
        "title_template": "批处理进度更新",
        "body_template": "批处理任务进度：{progress}%（{completed}/{total}）",
        "channels": ["ws"],
        "priority": "normal",
    },
    {
        "code": "ai.batch_complete",
        "category": "ai",
        "title_template": "批处理已完成",
        "body_template": "批处理任务已完成，共处理 {total} 条数据。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "ai.batch_failed",
        "category": "ai",
        "title_template": "批处理执行失败",
        "body_template": "批处理任务执行失败，错误信息：{error}",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    {
        "code": "ai.kb_index_complete",
        "category": "ai",
        "title_template": "知识库索引完成",
        "body_template": "知识库 {kb_name} 索引已完成，共处理 {doc_count} 个文档。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "ai.kb_index_failed",
        "category": "ai",
        "title_template": "知识库索引失败",
        "body_template": "知识库 {kb_name} 索引失败，错误信息：{error}",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    {
        "code": "ai.soft_quota_exceeded",
        "category": "ai",
        "title_template": "AI 配额已超限提醒",
        "body_template": "您的 AI 使用量已达 {current} Token，已超过软限制 {limit}（周期：{period}），请关注用量并及时续费或升级套餐。",
        "channels": ["ws", "inbox", "email", "webhook"],
        "priority": "high",
    },
    # ===== task (1) / 任务类 1 条 =====
    {
        "code": "task.failed",
        "category": "task",
        "title_template": "任务执行失败：{task_name}",
        "body_template": "任务 {task_name} 执行失败，错误信息：{error}",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    # ===== biz (7) / 业务类 7 条 =====
    {
        "code": "biz.plugin_installed",
        "category": "biz",
        "title_template": "插件已安装：{plugin_name}",
        "body_template": "插件 {plugin_name} (v{version}) 已安装成功。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.plugin_enabled",
        "category": "biz",
        "title_template": "插件已启用：{plugin_name}",
        "body_template": "插件 {plugin_name} 已启用成功。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.plugin_disabled",
        "category": "biz",
        "title_template": "插件已禁用：{plugin_name}",
        "body_template": "插件 {plugin_name} 已禁用。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.plugin_uninstalled",
        "category": "biz",
        "title_template": "插件已卸载：{plugin_name}",
        "body_template": "插件 {plugin_name} (v{version}) 已卸载。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.user_registration_pending",
        "category": "biz",
        "title_template": "新用户注册待审批：{username}",
        "body_template": "用户 {username}（{email}）已提交注册申请，请前往用户管理页面审批。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.user_approved",
        "category": "biz",
        "title_template": "注册审批已通过",
        "body_template": "您在 {tenant_name} 的注册申请已通过审批，现在可以正常使用系统了。",
        "channels": ["ws", "inbox", "email"],
        "priority": "normal",
    },
    {
        "code": "biz.user_rejected",
        "category": "biz",
        "title_template": "注册审批已拒绝",
        "body_template": "您在 {tenant_name} 的注册申请已被拒绝，如有疑问请联系管理员。",
        "channels": ["ws", "inbox", "email"],
        "priority": "normal",
    },
]


async def seed_notification_templates(db: AsyncSession) -> dict[str, int]:
    """
    Idempotently insert/update notification template seed data.
    幂等插入/更新通知模板种子数据。

    - Not exists → insert / 不存在 → 插入
    - Exists but title/body still in old i18n key format → update to readable text /
      已存在但标题/正文仍为旧 i18n key 格式 → 更新为可读文本

    Returns:
        {"created": N, "existing": M, "updated": U}
    """
    all_codes = [t["code"] for t in SEED_TEMPLATES]
    result = await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.code.in_(all_codes),
        )
    )
    existing_map = {t.code: t for t in result.scalars().all()}

    created = 0
    updated = 0
    existing = 0
    seed_map = {t["code"]: t for t in SEED_TEMPLATES}

    for code, tpl_data in seed_map.items():
        if code in existing_map:
            existing += 1
            tpl = existing_map[code]
            # Update old i18n key format to readable text / 更新旧的 i18n key 格式为可读文本
            need_update = False
            if tpl.title_template and tpl.title_template.startswith("notification."):
                tpl.title_template = tpl_data["title_template"]
                need_update = True
            if not tpl.body_template and tpl_data.get("body_template"):
                tpl.body_template = tpl_data["body_template"]
                need_update = True
            if need_update:
                updated += 1
        else:
            tpl = NotificationTemplate(
                code=tpl_data["code"],
                category=tpl_data["category"],
                title_template=tpl_data["title_template"],
                body_template=tpl_data.get("body_template"),
                channels=tpl_data["channels"],
                priority=tpl_data["priority"],
                is_system=True,
            )
            db.add(tpl)
            created += 1

    if created > 0 or updated > 0:
        await db.commit()

    logger.info(
        "Notification templates seeded: created={} updated={} existing={}",
        created,
        updated,
        existing,
    )
    return {"created": created, "updated": updated, "existing": existing}


__all__ = ["seed_notification_templates"]
