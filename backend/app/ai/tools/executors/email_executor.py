"""
Email Tool Executor. / 邮件工具执行器。

Calls the existing EmailService to send emails, with domain whitelist and recipient count limits.
调用已有的 EmailService 发送邮件，支持域名白名单、收件人数量限制。
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any

from app.configs.service import PLATFORM_TENANT_ID
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager
from app.core.response import build_public_error_text

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.email")

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _parse_email_list(raw: str) -> list[str]:
    """Parse comma-separated email list / 解析逗号分隔的邮箱列表"""
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def _validate_emails(
    addresses: list[str],
    allowed_domains: list[str],
) -> str | None:
    """Validate email format and domain whitelist, return error message or None. / 校验邮箱格式和域名白名单，返回错误消息或 None。"""
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
    Email tool executor.
    邮件工具执行器。

    Reads from ToolDefinition.config:
    从 ToolDefinition.config 中读取：
    - _email_subject_prefix: Subject prefix / 主题前缀
    - _email_allowed_domains: Allowed recipient domain list / 允许的收件域名列表
    - _email_max_recipients: Maximum number of recipients / 最大收件人数
    - _email_require_confirmation: Whether user confirmation is needed (handled by consent mechanism)
      是否需要用户确认（由 consent 机制处理）
    - _email_allow_cc: Whether CC is allowed / 是否允许抄送
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """Execute email sending / 执行邮件发送"""
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

        # Recipient count limit / 收件人数量限制
        max_recipients = cfg.get("_email_max_recipients", 5)
        all_recipients = to_list + cc_list
        if len(all_recipients) > max_recipients:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Too many recipients ({len(all_recipients)}), maximum is {max_recipients}",
            )

        # Domain whitelist validation / 域名白名单校验
        allowed_domains = cfg.get("_email_allowed_domains", [])
        err = _validate_emails(all_recipients, allowed_domains)
        if err:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=err,
            )

        # Add subject prefix / 添加主题前缀
        prefix = cfg.get("_email_subject_prefix", "")
        if prefix and not subject.startswith(prefix):
            subject = f"{prefix} {subject}"

        try:
            tenant_id = (
                (context.tenant_id if context else None)
                or PLATFORM_TENANT_ID
            )

            # Rate limiting (per tenant per hour) / 频控（按企业/小时）
            from app.ai.tools.security import EmailRateLimitError, EmailRateLimiter
            try:
                await EmailRateLimiter.check_rate(tenant_id=tenant_id)
            except EmailRateLimitError as e:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=build_public_error_text(message=str(e)),
                )

            from app.tasks.email import send_email_task
            send_email_task.delay(
                to=to_list,
                subject=subject,
                html_body=body or None,
                cc=cc_list if cc_list else None,
                triggered_by="ai_tool",
                tenant_id=(
                    tenant_id
                    if tenant_id != PLATFORM_TENANT_ID
                    else None
                ),
            )

            duration_ms = int((time.perf_counter() - start) * 1000)
            output = (
                f"Email queued for sending to {', '.join(to_list)}"
                + (f" (cc: {', '.join(cc_list)})" if cc_list else "")
            )
            logger.info(
                "Email tool queued: to={} subject={} skill={}",
                ", ".join(to_list), subject, definition.source_skill_name,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error("Email tool error: {}", str(exc), exc_info=True)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=build_public_error_text(
                    message="Email send failed",
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Validate email parameters / 校验邮件参数"""
        _ = definition
        return bool(arguments.get("to") and arguments.get("subject"))


__all__ = ["EmailToolExecutor"]
