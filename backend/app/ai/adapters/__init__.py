"""
AI Adapter Registry / AI 适配器注册中心

Manages registration and instantiation of all provider adapters.
管理所有供应商适配器的注册和实例化。
"""

from app.ai.adapters.base import BaseAdapter
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


class AdapterRegistry:
    """
    Adapter Registry / 适配器注册中心

    Manages registration and instantiation of all provider adapters.
    管理所有供应商适配器的注册和实例化。
    """

    _adapters: dict[str, type[BaseAdapter]] = {}

    @classmethod
    def register(cls, provider_type: str, adapter_class: type[BaseAdapter]) -> None:
        """
        Register adapter / 注册适配器

        Args:
            provider_type: Provider type (e.g. openai_compatible) / 供应商类型
            adapter_class: Adapter class / 适配器类
        """
        if provider_type in cls._adapters and cls._adapters[provider_type] is adapter_class:
            return  # idempotent: already registered same class, skip
        cls._adapters[provider_type] = adapter_class
        logger.info(_("ai.log.adapter_registered"), extra={"provider_type": provider_type})

    @classmethod
    def get_adapter(cls, provider_type: str) -> type[BaseAdapter] | None:
        """
        Get adapter class / 获取适配器类

        Args:
            provider_type: Provider type / 供应商类型

        Returns:
            Adapter class or None / 适配器类或 None
        """
        return cls._adapters.get(provider_type)

    @classmethod
    def create_adapter(
        cls,
        provider_type: str,
        api_key: str,
        base_url: str | None = None,
        **kwargs
    ) -> BaseAdapter:
        """
        Create adapter instance / 创建适配器实例

        Args:
            provider_type: Provider type / 供应商类型
            api_key: API key / API 密钥
            base_url: API base URL (optional) / API 基础 URL（可选）
            **kwargs: Other configuration / 其他配置

        Returns:
            Adapter instance / 适配器实例

        Raises:
            ValueError: Adapter type not found / 适配器类型不存在
        """
        from app.exceptions import BusinessException

        adapter_class = cls.get_adapter(provider_type)
        if not adapter_class:
            raise BusinessException(message=_("ai.error.adapter_not_found"))

        return adapter_class(api_key=api_key, base_url=base_url, **kwargs)

    @classmethod
    def unregister(cls, provider_type: str) -> bool:
        """
        Unregister adapter / 注销适配器

        Args:
            provider_type: Provider type / 供应商类型

        Returns:
            Whether unregistration succeeded / 是否成功注销
        """
        removed = cls._adapters.pop(provider_type, None)
        if removed:
            logger.info(_("ai.log.adapter_registered"), extra={"provider_type": f"{provider_type} (unregistered)"})
        return removed is not None

    @classmethod
    def list_adapters(cls) -> list[str]:
        """
        List all registered adapter types / 列出所有已注册的适配器类型

        Returns:
            Adapter type list / 适配器类型列表
        """
        return list(cls._adapters.keys())


__all__ = [
    "AdapterRegistry",
]
