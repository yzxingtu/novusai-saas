"""Auth logging and dev-bootstrap policy domain."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import AuthenticationException, NotFoundException

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService

logger = LogManager.get_logger("auth")


class AuthLoggingBootstrapDomain:
    """Stable domain for auth logging and dev bootstrap policy checks."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

    @staticmethod
    def mask_identifier(identifier: str | None) -> str:
        if not identifier:
            return ""
        value = identifier.strip()
        if len(value) <= 2:
            return "*" * len(value)
        if len(value) <= 6:
            return f"{value[:1]}***{value[-1:]}"
        return f"{value[:2]}***{value[-2:]}"

    @staticmethod
    def format_auth_fields(**fields: Any) -> str:
        parts: list[str] = []
        for key, value in fields.items():
            if value is None or value == "":
                continue
            normalized = str(value).replace("\r", r"\r").replace("\n", r"\n")
            parts.append(f"{key}={normalized}")
        return " | ".join(parts)

    def log_auth_info(self, event: str, **fields: Any) -> None:
        details = self.format_auth_fields(**fields)
        logger.info(f"{event} | {details}" if details else event)

    def log_auth_warning(self, event: str, **fields: Any) -> None:
        details = self.format_auth_fields(**fields)
        logger.warning(f"{event} | {details}" if details else event)

    @staticmethod
    def utc_now_aware() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def normalize_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def normalize_request_host(host: str | None) -> str:
        if not host:
            return ""
        normalized = host.strip().lower()
        if normalized.startswith("[") and normalized.endswith("]"):
            normalized = normalized[1:-1]
        return normalized

    @classmethod
    def host_matches_rule(cls, host: str, rule: str) -> bool:
        normalized_rule = cls.normalize_request_host(rule)
        if not host or not normalized_rule:
            return False
        if normalized_rule.startswith("."):
            return host.endswith(normalized_rule)
        return host == normalized_rule

    def assert_dev_bootstrap_enabled(
        self,
        scope: str,
        request_host: str | None,
    ) -> str:
        app_env = settings.APP_ENV.strip().lower()
        normalized_host = self.normalize_request_host(request_host)
        if app_env != "development":
            self.log_auth_warning(
                f"{scope}.dev_bootstrap.denied",
                reason="app_env_not_development",
                app_env=app_env,
            )
            raise NotFoundException()
        if not settings.DEV_BOOTSTRAP_AUTH_ENABLED:
            self.log_auth_warning(
                f"{scope}.dev_bootstrap.denied",
                reason="flag_disabled",
                request_host=normalized_host,
            )
            raise NotFoundException()
        if not any(
            self.host_matches_rule(normalized_host, rule)
            for rule in settings.dev_bootstrap_allowed_hosts_list
        ):
            self.log_auth_warning(
                f"{scope}.dev_bootstrap.denied",
                reason="host_not_allowed",
                request_host=normalized_host,
            )
            raise NotFoundException()
        return normalized_host

    def assert_dev_bootstrap_secret(
        self,
        *,
        scope: str,
        provided_secret: str,
        expected_secret: str,
        request_host: str,
    ) -> None:
        if expected_secret and secrets.compare_digest(provided_secret, expected_secret):
            return
        self.log_auth_warning(
            f"{scope}.dev_bootstrap.failed",
            reason="secret_mismatch",
            request_host=request_host,
        )
        raise AuthenticationException(message=_("auth.credentials_invalid"))
