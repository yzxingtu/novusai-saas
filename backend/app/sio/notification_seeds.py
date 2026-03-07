"""
通知模板种子数据

系统启动时幂等插入/更新预置通知模板。
每个模板包含可读的中文标题和正文（支持 {variable} 占位符）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.models.common.notification_template import NotificationTemplate

logger = LogManager.get_logger("app")

# 所有预置模板定义
# title_template / body_template 支持 {variable} 占位符，由 NotificationService._render_template 渲染
SEED_TEMPLATES: list[dict] = [
    # ===== system (9) =====
    {
        "code": "system.announcement",
        "category": "system",
        "title_template": "系统公告",
        "body_template": "{content}",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "system.maintenance",
        "category": "system",
        "title_template": "系统维护通知",
        "body_template": "系统将于 {start_time} 开始维护，预计持续 {duration}，维护期间服务可能不可用。",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    {
        "code": "system.version_update",
        "category": "system",
        "title_template": "系统已更新到 {version}",
        "body_template": "系统已更新到版本 {version}，请查看更新日志了解新功能。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "system.security_alert",
        "category": "system",
        "title_template": "安全警告",
        "body_template": "{message}",
        "channels": ["ws", "inbox", "email"],
        "priority": "urgent",
    },
    {
        "code": "system.welcome",
        "category": "system",
        "title_template": "欢迎使用平台",
        "body_template": "您的账号已创建成功，欢迎使用！如需帮助请联系管理员。",
        "channels": ["inbox"],
        "priority": "normal",
    },
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
        "title_template": "租户创建成功",
        "body_template": "租户 {tenant_name} 已创建成功，管理员 {admin_name} 可前往登录。",
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
    # ===== ai (10) =====
    {
        "code": "ai.chat_complete",
        "category": "ai",
        "title_template": "AI 对话已完成",
        "body_template": "您的 AI 对话已完成处理。",
        "channels": ["ws"],
        "priority": "normal",
    },
    {
        "code": "ai.image_ready",
        "category": "ai",
        "title_template": "AI 图片已生成",
        "body_template": "您请求的 AI 图片已生成完成，可前往查看。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
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
        "code": "ai.kb_index_progress",
        "category": "ai",
        "title_template": "知识库索引进度更新",
        "body_template": "知识库 {kb_name} 索引进度：{progress}%",
        "channels": ["ws"],
        "priority": "normal",
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
        "code": "ai.quota_warning",
        "category": "ai",
        "title_template": "AI 配额即将用尽",
        "body_template": "模型 {model_name} 的 Token 配额已使用 {usage_percent}%，请注意用量。",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    {
        "code": "ai.quota_exhausted",
        "category": "ai",
        "title_template": "AI 配额已用尽",
        "body_template": "模型 {model_name} 的 Token 配额已用尽，后续请求将被拒绝。请联系管理员调整配额。",
        "channels": ["ws", "inbox", "email"],
        "priority": "urgent",
    },
    {
        "code": "ai.chat_reply",
        "category": "ai",
        "title_template": "AI 助手已回复您的消息",
        "body_template": "AI 助手已完成回复，点击查看对话详情。",
        "channels": ["ws"],
        "priority": "normal",
    },
    # ===== task (5) =====
    {
        "code": "task.completed",
        "category": "task",
        "title_template": "任务已完成：{task_name}",
        "body_template": "任务 {task_name} 已成功完成。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "task.failed",
        "category": "task",
        "title_template": "任务执行失败：{task_name}",
        "body_template": "任务 {task_name} 执行失败，错误信息：{error}",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    {
        "code": "task.export_ready",
        "category": "task",
        "title_template": "数据导出已完成",
        "body_template": "您请求的数据导出已完成，文件 {filename} 已准备就绪。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "task.import_complete",
        "category": "task",
        "title_template": "数据导入已完成",
        "body_template": "数据导入已完成，共导入 {count} 条记录。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "task.import_failed",
        "category": "task",
        "title_template": "数据导入失败",
        "body_template": "数据导入失败，错误信息：{error}",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    # ===== biz (8) =====
    {
        "code": "biz.tenant_created",
        "category": "biz",
        "title_template": "新租户已创建：{tenant_name}",
        "body_template": "新租户 {tenant_name} 已创建成功。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.tenant_expired",
        "category": "biz",
        "title_template": "租户套餐即将到期：{tenant_name}",
        "body_template": "租户 {tenant_name} 的套餐将在 {days_remaining} 天后到期，请及时续费。",
        "channels": ["ws", "inbox", "email"],
        "priority": "high",
    },
    {
        "code": "biz.plan_changed",
        "category": "biz",
        "title_template": "套餐已变更",
        "body_template": "租户 {tenant_name} 的套餐已从 {old_plan} 变更为 {new_plan}。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.plugin_installed",
        "category": "biz",
        "title_template": "插件已安装：{plugin_name}",
        "body_template": "插件 {plugin_name} (v{version}) 已安装成功。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.plugin_update_available",
        "category": "biz",
        "title_template": "插件有新版本：{plugin_name}",
        "body_template": "插件 {plugin_name} 有新版本 {new_version} 可用，当前版本 {current_version}。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "biz.domain_ssl_expiring",
        "category": "biz",
        "title_template": "域名 SSL 证书即将到期：{domain}",
        "body_template": "域名 {domain} 的 SSL 证书将在 {days_remaining} 天后到期，请及时处理。",
        "channels": ["ws", "inbox", "email"],
        "priority": "high",
    },
    {
        "code": "biz.storage_warning",
        "category": "biz",
        "title_template": "存储空间不足警告",
        "body_template": "租户 {tenant_name} 的存储空间已使用 {usage_percent}%，请清理或扩容。",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    {
        "code": "biz.sub_admin_created",
        "category": "biz",
        "title_template": "新管理员已创建：{admin_name}",
        "body_template": "子管理员 {admin_name} 已创建成功，角色：{role_name}。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    # ===== approval (3) =====
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
    # ===== audit (4) =====
    {
        "code": "audit.suspicious_login",
        "category": "audit",
        "title_template": "异常登录检测",
        "body_template": "检测到异常登录行为，IP 地址：{ip}，位置：{location}。如非本人操作，请立即修改密码。",
        "channels": ["ws", "inbox", "email"],
        "priority": "urgent",
    },
    {
        "code": "audit.permission_changed",
        "category": "audit",
        "title_template": "权限变更通知",
        "body_template": "用户 {user_name} 的权限已变更，操作人：{operator}。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "audit.role_changed",
        "category": "audit",
        "title_template": "角色变更通知",
        "body_template": "用户 {user_name} 的角色已从 {old_role} 变更为 {new_role}。",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "audit.account_locked",
        "category": "audit",
        "title_template": "账号已锁定",
        "body_template": "用户 {user_name} 的账号因多次登录失败已被锁定，请联系管理员解锁。",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
]


async def seed_notification_templates(db: AsyncSession) -> dict[str, int]:
    """
    幂等插入/更新通知模板种子数据

    - 不存在 → 插入
    - 已存在但标题/正文仍为旧 i18n key 格式 → 更新为可读文本

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
            # 更新旧的 i18n key 格式为可读文本
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
        "Notification templates seeded: created=%d updated=%d existing=%d",
        created, updated, existing,
    )
    return {"created": created, "updated": updated, "existing": existing}


__all__ = ["seed_notification_templates"]
