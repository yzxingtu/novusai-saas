"""
DNS Provider 抽象层 / DNS Provider Abstraction Layer

为 ACME DNS-01 验证提供 TXT 记录设置/清理能力。
Provides TXT record set/cleanup for ACME DNS-01 validation.

当前产品化自动签发仅支持 Cloudflare。
At the moment, production-ready automated issuance only supports Cloudflare.
"""

import abc
from typing import Any

from app.configs.service import ConfigService
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException

logger = LogManager.get_logger("ssl")

_SUPPORTED_AUTOMATION_DNS_PROVIDERS = {"cloudflare"}
_LEGACY_UNSUPPORTED_DNS_PROVIDERS = {"aliyun", "dnspod"}


class DnsProvider(abc.ABC):
    """DNS 提供商抽象基类 / DNS provider abstract base class."""

    @abc.abstractmethod
    async def set_txt_record(self, record_name: str, record_value: str) -> None:
        """
        设置 DNS TXT 记录（用于 ACME DNS-01 验证） / Set DNS TXT record for ACME DNS-01.

        Args:
            record_name: 完整记录名（如 _acme-challenge.app.example.com） / Full record name
            record_value: TXT 记录值（ACME 验证 token） / TXT value (ACME token)
        """

    @abc.abstractmethod
    async def delete_txt_record(self, record_name: str, record_value: str) -> None:
        """
        清理 DNS TXT 记录（验证完成后调用） / Remove DNS TXT record after validation.

        Args:
            record_name: 完整记录名 / Full record name
            record_value: TXT 记录值 / TXT value
        """


class CloudflareDnsProvider(DnsProvider):
    """
    Cloudflare DNS 提供商 / Cloudflare DNS provider.

    通过 Cloudflare API v4 管理 DNS TXT 记录。Manages TXT records via Cloudflare API v4.
    需要配置：Requires dns_cloudflare_api_token and dns_cloudflare_zone_id.
    """

    def __init__(self, api_token: str, zone_id: str):
        self._api_token = api_token
        self._zone_id = zone_id
        self._base_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"

    async def set_txt_record(self, record_name: str, record_value: str) -> None:
        import httpx

        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

        # 先删除同名旧记录（避免重复）
        await self.delete_txt_record(record_name, record_value)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._base_url,
                headers=headers,
                json={
                    "type": "TXT",
                    "name": record_name,
                    "content": record_value,
                    "ttl": 60,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                errors = data.get("errors", [])
                raise RuntimeError(f"Cloudflare API error: {errors}")

            logger.info(
                "Cloudflare TXT record set: {} = {}", record_name, record_value,
            )

    async def delete_txt_record(self, record_name: str, record_value: str) -> None:
        import httpx

        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            # 查找匹配的 TXT 记录
            resp = await client.get(
                self._base_url,
                headers=headers,
                params={"type": "TXT", "name": record_name},
            )
            resp.raise_for_status()
            data = resp.json()

            for record in data.get("result", []):
                if record.get("content") == record_value:
                    del_resp = await client.delete(
                        f"{self._base_url}/{record['id']}",
                        headers=headers,
                    )
                    del_resp.raise_for_status()
                    logger.info(
                        "Cloudflare TXT record deleted: {} (id={})",
                        record_name, record["id"],
                    )

class ManualDnsProvider(DnsProvider):
    """
    手动 DNS 提供商（开发/测试用） / Manual DNS provider (dev/test).

    不实际设置 DNS 记录，仅记录日志。No real DNS changes, log only. For DEBUG or when auto DNS is not needed.
    """

    async def set_txt_record(self, record_name: str, record_value: str) -> None:
        logger.warning(
            "Manual DNS mode: Please set TXT record {} = {}",
            record_name, record_value,
        )

    async def delete_txt_record(self, record_name: str, record_value: str) -> None:
        logger.warning(
            "Manual DNS mode: Please delete TXT record {} = {}",
            record_name, record_value,
        )


# ==================== 配置审计与校验 / Config audit & validation ====================


def _build_issue(code: str, message: str, severity: str = "error") -> dict[str, str]:
    """构建 DNS 配置诊断项 / Build a DNS config diagnostic issue."""
    return {
        "code": code,
        "message": message,
        "severity": severity,
    }


async def audit_dns_provider_config(db) -> dict[str, Any]:
    """
    审计当前 DNS provider 配置是否可用于自动化签发 / Audit whether the current DNS provider config is ready for automated issuance.

    Returns:
        {
            "provider_type": str,
            "ready": bool,
            "supported": bool,
            "summary": str,
            "issues": [{"code": str, "message": str, "severity": str}, ...],
        }
    """
    config_svc = ConfigService(db)
    default_provider = "manual" if settings.DEBUG else "cloudflare"
    provider_type = str(
        await config_svc.get_platform_config("dns_provider", default=default_provider) or default_provider
    ).strip().lower()
    issues: list[dict[str, str]] = []

    if provider_type in _LEGACY_UNSUPPORTED_DNS_PROVIDERS:
        issues.append(
            _build_issue(
                "legacy_unsupported_provider",
                _("ssl_certificate.dns_provider_legacy_unsupported", provider=provider_type),
            )
        )
    elif provider_type == "cloudflare":
        api_token = str(
            await config_svc.get_platform_config("dns_cloudflare_api_token", default="") or ""
        ).strip()
        zone_id = str(
            await config_svc.get_platform_config("dns_cloudflare_zone_id", default="") or ""
        ).strip()
        if not api_token or not zone_id:
            issues.append(
                _build_issue(
                    "cloudflare_missing_credentials",
                    _("ssl_certificate.cloudflare_dns_not_configured"),
                )
            )
    elif provider_type == "manual":
        issues.append(
            _build_issue(
                "manual_mode_not_supported",
                _("ssl_certificate.manual_dns_not_supported"),
                severity="warning",
            )
        )
    else:
        issues.append(
            _build_issue(
                "unknown_provider",
                _("ssl_certificate.dns_provider_invalid", provider=provider_type or "-"),
            )
        )

    ready = provider_type in _SUPPORTED_AUTOMATION_DNS_PROVIDERS and not issues
    summary = (
        issues[0]["message"]
        if issues
        else _("ssl_certificate.dns_provider_ready", provider="Cloudflare")
    )
    return {
        "provider_type": provider_type,
        "ready": ready,
        "supported": provider_type in _SUPPORTED_AUTOMATION_DNS_PROVIDERS,
        "summary": summary,
        "issues": issues,
    }


async def ensure_dns_provider_ready(
    db,
    *,
    allow_manual: bool = False,
) -> str:
    """确保当前 DNS provider 可用于目标流程 / Ensure current DNS provider is ready for the target flow."""
    audit = await audit_dns_provider_config(db)
    provider_type = audit["provider_type"]

    if provider_type == "manual" and allow_manual:
        return provider_type

    if not audit["ready"]:
        raise BusinessException(
            message=audit["summary"],
            code=ErrorCode.CONFIG_VALIDATION_FAILED,
        )
    return provider_type


async def validate_platform_ssl_config_patch(
    configs: dict[str, Any],
) -> None:
    """校验平台 SSL 配置补丁 / Validate a platform SSL config patch before saving."""
    raw_provider = configs.get("dns_provider")
    if raw_provider is None:
        return

    provider_type = str(raw_provider or "").strip().lower()
    configs["dns_provider"] = provider_type

    if provider_type in _LEGACY_UNSUPPORTED_DNS_PROVIDERS:
        raise BusinessException(
            message=_("ssl_certificate.dns_provider_legacy_unsupported", provider=provider_type),
            code=ErrorCode.CONFIG_VALIDATION_FAILED,
        )

    if provider_type == "manual":
        if settings.DEBUG:
            return
        raise BusinessException(
            message=_("ssl_certificate.manual_dns_not_supported"),
            code=ErrorCode.CONFIG_VALIDATION_FAILED,
        )

    if provider_type != "cloudflare":
        raise BusinessException(
            message=_("ssl_certificate.dns_provider_invalid", provider=provider_type or "-"),
            code=ErrorCode.CONFIG_VALIDATION_FAILED,
        )


# ==================== 工厂函数 / Factory ====================


async def get_dns_provider(db) -> DnsProvider:
    """
    从平台配置动态构建 DNS 提供商实例 / Build DnsProvider from platform config.

    读取 ConfigService 中的 dns_provider 配置项，根据类型创建对应的 DnsProvider 实例。

    Args:
        db: AsyncSession

    Returns:
        DnsProvider 实例 / DnsProvider instance

    Raises:
        BusinessException: 配置缺失或当前 provider 不可用于自动化签发 / Missing config or provider not ready
    """
    config_svc = ConfigService(db)
    provider_type = await ensure_dns_provider_ready(db)

    if provider_type == "cloudflare":
        api_token = await config_svc.get_platform_config("dns_cloudflare_api_token", default="")
        zone_id = await config_svc.get_platform_config("dns_cloudflare_zone_id", default="")
        return CloudflareDnsProvider(api_token=api_token, zone_id=zone_id)

    if provider_type == "manual":
        return ManualDnsProvider()

    raise RuntimeError(f"Unsupported DNS provider: {provider_type}")


__all__ = [
    "DnsProvider",
    "CloudflareDnsProvider",
    "ManualDnsProvider",
    "audit_dns_provider_config",
    "ensure_dns_provider_ready",
    "get_dns_provider",
    "validate_platform_ssl_config_patch",
]
