"""
邮件模板引擎 / Email Template Engine

基于 Jinja2 的邮件模板系统，支持：
Jinja2-based email template system, supports:
- HTML 模板渲染 + 纯文本自动回退
- 基础布局模板（品牌一致性）
- i18n 多语言支持
- 5 个内置场景模板
"""

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.logging import LogManager

logger = LogManager.get_logger("email")


def _default_platform_name() -> str:
    """从配置定义获取站点名称默认值，避免硬编码 / Get default site name from config definition."""
    try:
        from app.configs.definitions.platform.general import SITE_NAME
        return SITE_NAME.default_value or "NovusAI SaaS"
    except Exception:
        return "NovusAI SaaS"

# 模板目录
TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "email"

# Jinja2 环境（单例）
_env: Environment | None = None


def _get_env() -> Environment:
    """获取 Jinja2 环境（懒加载单例） / Get Jinja2 environment (lazy singleton)."""
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env


def _strip_html(html: str) -> str:
    """将 HTML 转为纯文本（简易实现） / Strip HTML to plain text (simple impl)."""
    # 移除 style/script 标签及内容
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # <br> / <p> / <div> / <tr> → 换行
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(p|div|tr|li|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    # <td> → 空格
    text = re.sub(r"</?td[^>]*>", " ", text, flags=re.IGNORECASE)
    # 移除所有剩余标签
    text = re.sub(r"<[^>]+>", "", text)
    # HTML 实体
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    # 合并连续空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def render_email(
    template_name: str,
    context: dict[str, Any] | None = None,
    lang: str = "zh-CN",
) -> tuple[str, str]:
    """
    渲染邮件模板 / Render email template.

    Args:
        template_name: 模板名称（不含扩展名），如 "task_failure"
        context: 模板变量
        lang: 语言代码（zh-CN / en-US）

    Returns:
        (html_body, text_body) 元组
    """
    env = _get_env()
    ctx = dict(context or {})
    ctx["lang"] = lang

    # 注入 i18n 翻译函数
    ctx["t"] = _get_translations(lang)

    # 尝试加载语言专属模板，回退到默认模板
    html_template_name = f"{template_name}.html"
    try:
        template = env.get_template(html_template_name)
    except Exception:
        logger.error("Email template not found: %s", html_template_name)
        raise

    html_body = template.render(**ctx)
    text_body = _strip_html(html_body)

    return html_body, text_body


# ============================================
# 场景快捷函数
# ============================================

def render_test_email(
    admin_name: str = "Admin",
    platform_name: str | None = None,
    lang: str = "zh-CN",
) -> tuple[str, str, str]:
    """
    渲染测试邮件 / Render test email.

    Returns:
        (subject, html_body, text_body)
    """
    platform_name = platform_name or _default_platform_name()
    t = _get_translations(lang)
    subject = t["test_email"]["subject"].format(platform_name=platform_name)
    html, text = render_email("test_email", {
        "admin_name": admin_name,
        "platform_name": platform_name,
    }, lang=lang)
    return subject, html, text


def render_task_failure_email(
    task_name: str,
    task_id: str,
    error: str,
    platform_name: str | None = None,
    lang: str = "zh-CN",
) -> tuple[str, str, str]:
    """
    渲染任务失败通知邮件 / Render task failure notification email.

    Returns:
        (subject, html_body, text_body)
    """
    platform_name = platform_name or _default_platform_name()
    t = _get_translations(lang)
    subject = t["task_failure"]["subject"].format(task_name=task_name)
    html, text = render_email("task_failure", {
        "task_name": task_name,
        "task_id": task_id,
        "error": error,
        "platform_name": platform_name,
    }, lang=lang)
    return subject, html, text


def render_password_reset_email(
    user_name: str,
    reset_url: str,
    expire_minutes: int = 30,
    platform_name: str | None = None,
    lang: str = "zh-CN",
) -> tuple[str, str, str]:
    """
    渲染密码重置邮件 / Render password reset email.

    Returns:
        (subject, html_body, text_body)
    """
    platform_name = platform_name or _default_platform_name()
    t = _get_translations(lang)
    subject = t["password_reset"]["subject"].format(platform_name=platform_name)
    html, text = render_email("password_reset", {
        "user_name": user_name,
        "reset_url": reset_url,
        "expire_minutes": expire_minutes,
        "platform_name": platform_name,
    }, lang=lang)
    return subject, html, text


def render_welcome_email(
    tenant_name: str,
    admin_name: str,
    login_url: str,
    platform_name: str | None = None,
    lang: str = "zh-CN",
) -> tuple[str, str, str]:
    """
    渲染欢迎邮件 / Render welcome email.

    Returns:
        (subject, html_body, text_body)
    """
    platform_name = platform_name or _default_platform_name()
    t = _get_translations(lang)
    subject = t["welcome"]["subject"].format(platform_name=platform_name)
    html, text = render_email("welcome", {
        "tenant_name": tenant_name,
        "admin_name": admin_name,
        "login_url": login_url,
        "platform_name": platform_name,
    }, lang=lang)
    return subject, html, text


def render_ssl_expiry_email(
    domain: str,
    expires_at: str,
    days_remaining: int,
    platform_name: str | None = None,
    lang: str = "zh-CN",
) -> tuple[str, str, str]:
    """
    渲染 SSL 证书到期通知邮件 / Render SSL expiry notification email.

    Returns:
        (subject, html_body, text_body)
    """
    platform_name = platform_name or _default_platform_name()
    t = _get_translations(lang)
    subject = t["ssl_expiry"]["subject"].format(domain=domain)
    html, text = render_email("ssl_expiry", {
        "domain": domain,
        "expires_at": expires_at,
        "days_remaining": days_remaining,
        "platform_name": platform_name,
    }, lang=lang)
    return subject, html, text


def render_manual_email(
    subject: str,
    content: str,
    lang: str = "zh-CN",
) -> tuple[str, str]:
    """
    渲染手动发送邮件（管理员后台手动发送）/ Render manual send email (admin UI).

    将用户输入的内容包裹在品牌 HTML 模板中，确保统一风格。
    content 允许包含 HTML 标签（模板中使用 | safe 渲染）。

    Args:
        subject: 邮件主题（同时作为模板 header 标题）
        content: 邮件正文内容（支持 HTML）
        lang: 语言

    Returns:
        (html_body, text_body)
    """
    return render_email("manual_send", {
        "subject": subject,
        "content": content,
        "platform_name": _default_platform_name(),
    }, lang=lang)


def render_notification_html(
    title: str,
    body: str | None = None,
    priority: str = "normal",
    link: str | None = None,
    lang: str = "zh-CN",
) -> tuple[str, str]:
    """
    渲染通知邮件 HTML（通用模板）/ Render notification email HTML (generic template).

    所有通知系统触发的邮件都使用此模板，确保统一的品牌风格。

    Args:
        title: 通知标题
        body: 通知正文
        priority: 优先级 (low/normal/high/urgent)
        link: 点击查看详情的链接
        lang: 语言

    Returns:
        (html_body, text_body)
    """
    return render_email("notification", {
        "title": title,
        "body": body,
        "priority": priority,
        "link": link,
        "platform_name": _default_platform_name(),
    }, lang=lang)


# ============================================
# i18n 翻译字典
# ============================================

_TRANSLATIONS: dict[str, dict[str, Any]] = {
    "zh-CN": {
        "common": {
            "greeting": "您好",
            "regards": "此致",
            "team": "{platform_name} 团队",
            "auto_email_notice": "这是一封系统自动发送的邮件，请勿直接回复。",
            "copyright": "© {year} {platform_name}. All rights reserved.",
        },
        "test_email": {
            "subject": "[{platform_name}] 测试邮件",
            "title": "邮件配置测试",
            "body": "恭喜！您的邮件服务已配置成功。",
            "detail": "如果您收到了这封邮件，说明 SMTP 配置正确，邮件发送功能正常工作。",
        },
        "task_failure": {
            "subject": "[任务失败] {task_name}",
            "title": "定时任务执行失败",
            "task_name_label": "任务名称",
            "task_id_label": "任务 ID",
            "error_label": "错误详情",
            "action_hint": "请登录管理后台查看任务日志，排查失败原因。",
        },
        "password_reset": {
            "subject": "[{platform_name}] 密码重置",
            "title": "密码重置请求",
            "body": "我们收到了您的密码重置请求。请点击下方按钮重置密码：",
            "button": "重置密码",
            "expire_notice": "此链接将在 {expire_minutes} 分钟后失效。",
            "ignore_notice": "如果您未请求重置密码，请忽略此邮件。",
            "admin_reset_notice": "您的密码已被平台管理员重置，请使用新密码登录后及时修改。",
        },
        "welcome": {
            "subject": "欢迎加入 {platform_name}",
            "title": "欢迎加入！",
            "body": "您的企业已创建成功，以下是您的登录信息：",
            "tenant_label": "企业名称",
            "button": "登录管理后台",
            "support_notice": "如需帮助，请联系平台支持团队。",
        },
        "ssl_expiry": {
            "subject": "[SSL 证书即将到期] {domain}",
            "title": "SSL 证书到期提醒",
            "body": "以下域名的 SSL 证书即将到期，请及时续期：",
            "domain_label": "域名",
            "expires_label": "到期时间",
            "days_label": "剩余天数",
            "action_hint": "请登录管理后台手动续期或确认自动续期已启用。",
        },
    },
    "en-US": {
        "common": {
            "greeting": "Hello",
            "regards": "Best regards",
            "team": "The {platform_name} Team",
            "auto_email_notice": "This is an automated email. Please do not reply directly.",
            "copyright": "© {year} {platform_name}. All rights reserved.",
        },
        "test_email": {
            "subject": "[{platform_name}] Test Email",
            "title": "Email Configuration Test",
            "body": "Congratulations! Your email service is configured successfully.",
            "detail": "If you received this email, your SMTP configuration is correct and the email service is working properly.",
        },
        "task_failure": {
            "subject": "[Task Failed] {task_name}",
            "title": "Scheduled Task Failed",
            "task_name_label": "Task Name",
            "task_id_label": "Task ID",
            "error_label": "Error Details",
            "action_hint": "Please check the task logs in the admin panel to investigate.",
        },
        "password_reset": {
            "subject": "[{platform_name}] Password Reset",
            "title": "Password Reset Request",
            "body": "We received a request to reset your password. Click the button below to proceed:",
            "button": "Reset Password",
            "expire_notice": "This link will expire in {expire_minutes} minutes.",
            "ignore_notice": "If you did not request a password reset, please ignore this email.",
            "admin_reset_notice": "Your password has been reset by the platform administrator. Please log in with the new password and change it promptly.",
        },
        "welcome": {
            "subject": "Welcome to {platform_name}",
            "title": "Welcome!",
            "body": "Your tenant has been created successfully. Here are your login details:",
            "tenant_label": "Tenant Name",
            "button": "Login to Admin Panel",
            "support_notice": "If you need help, please contact our support team.",
        },
        "ssl_expiry": {
            "subject": "[SSL Certificate Expiring] {domain}",
            "title": "SSL Certificate Expiry Notice",
            "body": "The SSL certificate for the following domain is about to expire. Please renew it promptly:",
            "domain_label": "Domain",
            "expires_label": "Expiry Date",
            "days_label": "Days Remaining",
            "action_hint": "Please log in to the admin panel to renew manually or ensure auto-renewal is enabled.",
        },
        "notification": {
            "urgent_notice": "This notification is marked as urgent, please handle it immediately.",
            "high_notice": "This notification has a high priority, please pay attention to it as soon as possible.",
            "view_detail": "View Details",
        },
    },
}


def _get_translations(lang: str) -> dict[str, Any]:
    """获取指定语言的翻译字典，回退到 zh-CN / Get translations for lang, fallback to zh-CN."""
    return _TRANSLATIONS.get(lang, _TRANSLATIONS["zh-CN"])


__all__ = [
    "render_email",
    "render_manual_email",
    "render_test_email",
    "render_task_failure_email",
    "render_password_reset_email",
    "render_welcome_email",
    "render_ssl_expiry_email",
]
