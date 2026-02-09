"""
AI 适配器注册中心

管理所有供应商适配器的注册和实例化
"""

from typing import Type

from app.ai.adapters.base import BaseAdapter
from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import ProviderTypeEnum

logger = LogManager.get_logger("ai")


class AdapterRegistry:
    """
    适配器注册中心
    
    管理所有供应商适配器的注册和实例化
    """
    
    _adapters: dict[str, Type[BaseAdapter]] = {}
    
    @classmethod
    def register(cls, provider_type: str, adapter_class: Type[BaseAdapter]) -> None:
        """
        注册适配器
        
        Args:
            provider_type: 供应商类型（如 openai_compatible）
            adapter_class: 适配器类
        """
        cls._adapters[provider_type] = adapter_class
        logger.info(_("ai.log.adapter_registered"), extra={"provider_type": provider_type})
    
    @classmethod
    def get_adapter(cls, provider_type: str) -> Type[BaseAdapter] | None:
        """
        获取适配器类
        
        Args:
            provider_type: 供应商类型
            
        Returns:
            适配器类或 None
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
        创建适配器实例
        
        Args:
            provider_type: 供应商类型
            api_key: API 密钥
            base_url: API 基础 URL（可选）
            **kwargs: 其他配置
            
        Returns:
            适配器实例
            
        Raises:
            ValueError: 适配器类型不存在
        """
        from app.exceptions import BusinessException

        adapter_class = cls.get_adapter(provider_type)
        if not adapter_class:
            raise BusinessException(message=_("ai.error.adapter_not_found"))
        
        return adapter_class(api_key=api_key, base_url=base_url, **kwargs)
    
    @classmethod
    def list_adapters(cls) -> list[str]:
        """
        列出所有已注册的适配器类型
        
        Returns:
            适配器类型列表
        """
        return list(cls._adapters.keys())


# 内置适配器注册
def _register_builtin_adapters() -> None:
    """注册内置适配器"""
    # OpenAI 兼容适配器
    AdapterRegistry.register(
        ProviderTypeEnum.OPENAI_COMPATIBLE.value,
        OpenAIAdapter
    )
    
    logger.info(_("ai.log.builtin_adapters_registered"), extra={"count": len(AdapterRegistry.list_adapters())})


# 启动时自动注册内置适配器
_register_builtin_adapters()


__all__ = [
    "AdapterRegistry",
]
