"""
邮件工具执行器

调用已有的 EmailService 发送邮件，支持域名白名单、收件人数量限制。
"""

from __future__ import annotations

import re
import time
from typing import Any, TYPE_CHECKING

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.email")

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _parse_email_list(raw: str) -> list[str]:
    """解析逗号分隔的邮箱列表"""
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def _validate_emails(
    addresses: list[str],
    allowed_domains: list[str],
) -> str | None:
    """校验邮箱格式和域名白名单，返回错误消息或 None"""
    for addr in addresses:
        if not _EMAIL_REGEX.match(addr):
            return f"Invalid email address: {addr}"
        if allowed_domains:
            domain = addr.split("@")[1].lower()
            if domain not in [d.lower() for d in allowed_domains]:
                return f"Domain '{domain}' not in allowed list: {', '.join(allowed_domains)}"
    return None


class EmailToolExecutor(BaseToolExecutor):
    """
    邮件工具执行器

    从 ToolDefinition.config 中读取：
    - _email_subject_prefix: 主题前缀
    - _email_allowed_domains: 允许的收件域名列表
    - _email_max_recipients: 最大收件人数
    - _email_require_confirmation: 是否需要用户确认（由 consent 机制处理）
    - _email_allow_cc: 是否允许抄送
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """执行邮件发送"""
        start = time.perf_counter()
        cfg = definition.config or {}

        to_raw = arguments.get("to", "")
        subject = arguments.get("subject", "")
        body = arguments.get("body", "")
        cc_raw = arguments.get("cc", "")

        to_list = _parse_email_list(to_raw)
        cc_list = _parse_email_list(cc_raw) if cfg.get("_email_allow_cc") else []

        if not to_list:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error="No recipients specified",
            )

        if not subject:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error="Email subject is required",
            )

        # 收件人数量限制
        max_recipients = cfg.get("_email_max_recipients", 5)
        all_recipients = to_list + cc_list
        if len(all_recipients) > max_recipients:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Too many recipients ({len(all_recipients)}), maximum is {max_recipients}",
            )

        # 域名白名单校验
        allowed_domains = cfg.get("_email_allowed_domains", [])
        err = _validate_emails(all_recipients, allowed_domains)
        if err:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=err,
            )

        # 添加主题前缀
        prefix = cfg.get("_email_subject_prefix", "")
        if prefix and not subject.startswith(prefix):
            subject = f"{prefix} {subject}"

        try:
            if not context or not context.db:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error="Database session not available for email sending",
                )

            from app.services.common.email_service import EmailService, EmailMessage
            service = EmailService(context.db)
            message = EmailMessage(
                to=to_list,
                subject=subject,
                html_body=body,
                cc=cc_list,
            )
            result = await service.send(message)

            duration_ms = int((time.perf_counter() - start) * 1000)

            if result.success:
                output = (
                    f"Email sent successfully to {', '.join(to_list)}"
                    + (f" (cc: {', '.join(cc_list)})" if cc_list else "")
                )
                logger.info(
                    "Email tool sent: to=%s subject=%s skill=%s",
                    ", ".join(to_list), subject, definition.source_skill_name,
                )
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=True,
                    output=output,
                    duration_ms=duration_ms,
                )
            else:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=f"Email send failed: {result.error or result.message}",
                    duration_ms=duration_ms,
                )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error("Email tool error: %s", str(exc), exc_info=True)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Email send failed: {str(exc)}",
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验邮件参数"""
        return bool(arguments.get("to") and arguments.get("subject"))


__all__ = ["EmailToolExecutor"]
