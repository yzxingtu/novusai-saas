from __future__ import annotations

from pathlib import Path

from loguru import logger as loguru_logger

from app.core.logging import LogManager
from app.services.common.auth_service import AuthService


def _reset_log_manager() -> None:
    LogManager._initialized = False
    LogManager._log_dir = None
    LogManager._loggers = {}
    LogManager._category_loggers = {}
    loguru_logger.remove()


def test_mask_identifier_hides_full_value() -> None:
    assert AuthService._mask_identifier("ab") == "**"
    assert AuthService._mask_identifier("admin") == "a***n"
    assert AuthService._mask_identifier("user@example.com") == "us***om"


def test_auth_log_helper_writes_to_auth_log(tmp_path: Path) -> None:
    _reset_log_manager()
    try:
        LogManager.init(log_dir=str(tmp_path), enable_console=False, enable_file=True)

        AuthService._log_auth_warning(
            "admin.login.failed",
            identifier=AuthService._mask_identifier("user@example.com"),
            reason="user_not_found",
        )

        auth_log = (tmp_path / "auth.log").read_text(encoding="utf-8")
        assert "admin.login.failed" in auth_log
        assert "user_not_found" in auth_log
        assert "us***om" in auth_log
        assert "user@example.com" not in auth_log
    finally:
        _reset_log_manager()
