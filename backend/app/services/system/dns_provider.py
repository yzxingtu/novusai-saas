"""
DNS Provider 抽象层 / DNS Provider Abstraction Layer

为 ACME DNS-01 验证提供 TXT 记录设置/清理能力。
Provides TXT record set/cleanup for ACME DNS-01 validation.
支持多种 DNS 提供商（Cloudflare、阿里云 DNS 等），通过平台配置动态选择。

使用方式（由 Celery SSL 任务调用）：
    provider = await get_dns_provider(db)
    await provider.set_txt_record("_acme-challenge.example.com", "token_value")
    # ... ACME 验证完成后 ...
    await provider.delete_txt_record("_acme-challenge.example.com", "token_value")
"""

import abc

from app.core.logging import LogManager

logger = LogManager.get_logger("ssl")


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
                "Cloudflare TXT record set: %s = %s", record_name, record_value,
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
                        "Cloudflare TXT record deleted: %s (id=%s)",
                        record_name, record["id"],
                    )


class AliyunDnsProvider(DnsProvider):
    """
    阿里云 DNS 提供商（预留接口） / Aliyun DNS provider (reserved).

    需要配置：Requires dns_aliyun_access_key_id, dns_aliyun_access_key_secret, dns_aliyun_domain.
    """

    def __init__(self, access_key_id: str, access_key_secret: str, domain: str):
        self._access_key_id = access_key_id
        self._access_key_secret = access_key_secret
        self._domain = domain

    async def set_txt_record(self, record_name: str, record_value: str) -> None:
        raise NotImplementedError("Aliyun DNS provider not yet implemented")

    async def delete_txt_record(self, record_name: str, record_value: str) -> None:
        raise NotImplementedError("Aliyun DNS provider not yet implemented")


class ManualDnsProvider(DnsProvider):
    """
    手动 DNS 提供商（开发/测试用） / Manual DNS provider (dev/test).

    不实际设置 DNS 记录，仅记录日志。No real DNS changes, log only. For DEBUG or when auto DNS is not needed.
    """

    async def set_txt_record(self, record_name: str, record_value: str) -> None:
        logger.warning(
            "Manual DNS mode: Please set TXT record %s = %s",
            record_name, record_value,
        )

    async def delete_txt_record(self, record_name: str, record_value: str) -> None:
        logger.warning(
            "Manual DNS mode: Please delete TXT record %s = %s",
            record_name, record_value,
        )


# ==================== 工厂函数 ====================

_DNS_PROVIDERS = {
    "cloudflare": "cloudflare",
    "aliyun": "aliyun",
    "manual": "manual",
}


async def get_dns_provider(db) -> DnsProvider:
    """
    从平台配置动态构建 DNS 提供商实例 / Build DnsProvider from platform config.

    读取 ConfigService 中的 dns_provider 配置项，根据类型创建对应的 DnsProvider 实例。

    Args:
        db: AsyncSession

    Returns:
        DnsProvider 实例 / DnsProvider instance

    Raises:
        RuntimeError: 配置缺失或提供商类型不支持 / Missing config or unsupported provider
    """
    from app.configs.service import ConfigService
    from app.core.config import settings

    config_svc = ConfigService(db)

    provider_type = await config_svc.get_platform_config(
        "dns_provider", default="manual",
    )

    if provider_type == "cloudflare":
        api_token = await config_svc.get_platform_config("dns_cloudflare_api_token", default="")
        zone_id = await config_svc.get_platform_config("dns_cloudflare_zone_id", default="")
        if not api_token or not zone_id:
            raise RuntimeError(
                "Cloudflare DNS provider requires dns_cloudflare_api_token and dns_cloudflare_zone_id"
            )
        return CloudflareDnsProvider(api_token=api_token, zone_id=zone_id)

    if provider_type == "aliyun":
        access_key_id = await config_svc.get_platform_config("dns_aliyun_access_key_id", default="")
        access_key_secret = await config_svc.get_platform_config("dns_aliyun_access_key_secret", default="")
        domain = await config_svc.get_platform_config("dns_aliyun_domain", default="")
        if not access_key_id or not access_key_secret:
            raise RuntimeError(
                "Aliyun DNS provider requires dns_aliyun_access_key_id and dns_aliyun_access_key_secret"
            )
        return AliyunDnsProvider(access_key_id, access_key_secret, domain)

    if provider_type == "manual" or settings.DEBUG:
        return ManualDnsProvider()

    raise RuntimeError(f"Unsupported DNS provider: {provider_type}")


__all__ = [
    "DnsProvider",
    "CloudflareDnsProvider",
    "AliyunDnsProvider",
    "ManualDnsProvider",
    "get_dns_provider",
]
