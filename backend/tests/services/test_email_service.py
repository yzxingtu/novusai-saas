"""EmailService 单元测试 / Test.

覆盖：send() 方法的真实验证逻辑 — 开关/配置/收件人/格式/附件大小检查。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.common.email_service import (
    EmailAttachment,
    EmailMessage,
    EmailService,
    SmtpConfig,
    _is_valid_email,
)


def _smtp_config(**overrides) -> SmtpConfig:
    defaults = {
        "host": "smtp.example.com", "port": 587, "encryption": "tls",
        "username": "user", "password": "pass",
        "from_address": "noreply@example.com", "from_name": "Test",
        "enabled": True,
    }
    defaults.update(overrides)
    return SmtpConfig(**defaults)


def _service(mock_db, config: SmtpConfig | None = None) -> EmailService:
    svc = EmailService.__new__(EmailService)
    svc._db = mock_db
    svc._config_service = AsyncMock()
    svc._load_smtp_config = AsyncMock(return_value=config or _smtp_config())
    return svc


# ── 邮箱格式校验（纯函数，无 mock）──

class TestEmailValidation:

    def test_valid_email(self):
        assert _is_valid_email("user@example.com") is True

    def test_valid_email_with_dots(self):
        assert _is_valid_email("first.last@sub.example.co.uk") is True

    def test_invalid_no_at(self):
        assert _is_valid_email("userexample.com") is False

    def test_invalid_no_domain(self):
        assert _is_valid_email("user@") is False

    def test_invalid_empty(self):
        assert _is_valid_email("") is False


# ── send() 验证逻辑（真实业务分支）──

class TestSendDisabled:

    @pytest.mark.asyncio
    async def test_email_disabled_returns_failure(self, mock_db):
        svc = _service(mock_db, _smtp_config(enabled=False))
        msg = EmailMessage(to=["a@b.com"], subject="Hi", html_body="<p>Hi</p>")

        result = await svc.send(msg)

        assert result.success is False
        assert result.message == "email_disabled"


class TestSendMissingConfig:

    @pytest.mark.asyncio
    async def test_missing_host_returns_config_incomplete(self, mock_db):
        svc = _service(mock_db, _smtp_config(host=""))
        msg = EmailMessage(to=["a@b.com"], subject="Hi", html_body="<p>Hi</p>")

        result = await svc.send(msg)

        assert result.success is False
        assert result.message == "config_incomplete"
        assert "smtp_host" in (result.error or "")

    @pytest.mark.asyncio
    async def test_missing_from_address(self, mock_db):
        svc = _service(mock_db, _smtp_config(from_address=""))
        msg = EmailMessage(to=["a@b.com"], subject="Hi", html_body="<p>Hi</p>")

        result = await svc.send(msg)

        assert result.success is False
        assert result.message == "config_incomplete"


class TestSendRecipientValidation:

    @pytest.mark.asyncio
    async def test_no_recipients(self, mock_db):
        svc = _service(mock_db)
        msg = EmailMessage(to=[], subject="Hi", html_body="<p>Hi</p>")

        result = await svc.send(msg)

        assert result.success is False
        assert result.message == "no_recipients"

    @pytest.mark.asyncio
    async def test_too_many_recipients(self, mock_db):
        svc = _service(mock_db)
        msg = EmailMessage(
            to=[f"user{i}@example.com" for i in range(60)],
            subject="Hi", html_body="<p>Hi</p>",
        )

        result = await svc.send(msg)

        assert result.success is False
        assert result.message == "too_many_recipients"

    @pytest.mark.asyncio
    async def test_invalid_email_format(self, mock_db):
        svc = _service(mock_db)
        msg = EmailMessage(to=["not-an-email"], subject="Hi", html_body="<p>Hi</p>")

        result = await svc.send(msg)

        assert result.success is False
        assert result.message == "invalid_email"


class TestSendAttachment:

    @pytest.mark.asyncio
    async def test_attachment_too_large(self, mock_db):
        svc = _service(mock_db)
        huge = EmailAttachment(filename="big.zip", content=b"x" * (11 * 1024 * 1024))
        msg = EmailMessage(
            to=["a@b.com"], subject="Hi", html_body="<p>Hi</p>",
            attachments=[huge],
        )

        result = await svc.send(msg)

        assert result.success is False
        assert result.message == "attachment_too_large"


class TestSendSuccess:

    @pytest.mark.asyncio
    async def test_successful_send(self, mock_db):
        svc = _service(mock_db)
        svc._build_mime_message = MagicMock(return_value=MagicMock())
        svc._smtp_send = MagicMock()

        msg = EmailMessage(to=["user@example.com"], subject="Hi", html_body="<p>Hi</p>")

        result = await svc.send(msg)

        assert result.success is True
        assert "user@example.com" in result.recipients
        svc._smtp_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_smtp_exception_returns_failure(self, mock_db):
        svc = _service(mock_db)
        svc._build_mime_message = MagicMock(return_value=MagicMock())
        svc._smtp_send = MagicMock(side_effect=ConnectionRefusedError("refused"))

        msg = EmailMessage(to=["user@example.com"], subject="Hi", html_body="<p>Hi</p>")

        result = await svc.send(msg)

        assert result.success is False
        assert result.message == "send_failed"
