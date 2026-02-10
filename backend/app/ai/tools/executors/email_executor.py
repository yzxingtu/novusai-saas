"""
邮件工具执行器

通过 SMTP 发送邮件，复用项目 SMTP 配置（从环境变量读取）
"""

import time
from typing import Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.security import EmailRateLimitError, EmailRateLimiter
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.email")


class EmailToolExecutor(BaseToolExecutor):
    """
    邮件工具执行器

    通过项目 SMTP 配置发送邮件，支持:
    - 主题/正文模板（含占位符替换）
    - 收件人从参数或 config 中获取
    - SMTP 配置从环境变量读取
    - 租户级频率限制和收件人数量限制
    """

    def __init__(self, tenant_id: int = 0):
        """
        Args:
            tenant_id: 租户 ID（用于频率限制）
        """
        self.tenant_id = tenant_id

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        发送邮件

        config 格式:
            subject_template: 邮件主题模板（含 {param} 占位符）
            body_template: 邮件正文模板（含 {param} 占位符）
            to_field: 收件人参数名（从 arguments 中取值）
            default_to: 默认收件人（to_field 不存在时使用）
        """
        import os

        start = time.perf_counter()
        config = definition.config

        # SMTP 配置从环境变量读取
        smtp_host = os.environ.get("SMTP_HOST", "")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASSWORD", "")
        smtp_from = os.environ.get("SMTP_FROM", smtp_user)
        smtp_tls = os.environ.get("SMTP_TLS", "true").lower() == "true"

        if not smtp_host or not smtp_user:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.email_smtp_not_configured"),
            )

        # 收件人
        to_field = config.get("to_field", "to")
        to_email = arguments.get(to_field) or config.get("default_to", "")
        if not to_email:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.email_no_recipient"),
            )

        # 安全检查：收件人数量限制
        recipients = [r.strip() for r in to_email.split(",") if r.strip()]
        try:
            EmailRateLimiter.validate_recipients(recipients)
        except Exception as sec_err:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=str(sec_err),
            )

        # 安全检查：租户级频率限制
        if self.tenant_id > 0:
            try:
                await EmailRateLimiter.check_rate(self.tenant_id)
            except EmailRateLimitError as rate_err:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=str(rate_err),
                )

        # 构建主题和正文
        subject_template = config.get("subject_template", "")
        body_template = config.get("body_template", "")

        try:
            subject = subject_template.format(**arguments) if subject_template else ""
            body = body_template.format(**arguments) if body_template else ""
        except (KeyError, IndexError) as e:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.email_template_param_error", detail=str(e)),
            )

        if not subject:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.email_subject_empty"),
            )

        # 发送邮件（在线程中运行同步 SMTP 操作，避免阻塞事件循环）
        try:
            import asyncio
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "plain", "utf-8"))

            def _send_email() -> None:
                if smtp_tls:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                    server.starttls()
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)

                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
                server.quit()

            await asyncio.to_thread(_send_email)

            duration_ms = int((time.perf_counter() - start) * 1000)

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=_("tool.success.email_sent", to=to_email),
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Email tool error: %s: %s",
                definition.name,
                str(exc),
                exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验邮件工具参数"""
        config = definition.config
        if not config.get("subject_template"):
            return False

        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False

        return True


__all__ = ["EmailToolExecutor"]
