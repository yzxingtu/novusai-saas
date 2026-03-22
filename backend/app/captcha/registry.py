"""
Captcha Registry / 验证码注册中心

Singleton registry for captcha providers. Registers built-in providers on init.
验证码提供者的单例注册中心。初始化时注册内置提供者。
"""

from __future__ import annotations

from app.captcha.provider import CaptchaProviderMetadata, ICaptchaProvider
from app.captcha.providers.image import ImageCaptchaProvider


class CaptchaRegistry:
    """
    Captcha Provider Registry (singleton) / 验证码提供者注册中心（单例）。

    Auto-registers ImageCaptchaProvider as default on first instantiation.
    首次实例化时自动注册 ImageCaptchaProvider 为默认提供者。
    """

    _instance: CaptchaRegistry | None = None

    def __new__(cls) -> CaptchaRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._providers: dict[str, ICaptchaProvider] = {}
        self._metadata: dict[str, CaptchaProviderMetadata] = {}
        self.register("image", ImageCaptchaProvider())
        self._initialized = True

    def register(
        self,
        code: str,
        provider: ICaptchaProvider,
        *,
        metadata: CaptchaProviderMetadata | None = None,
    ) -> None:
        """Register a captcha provider by code / 按代码注册验证码提供者"""
        self._providers[code] = provider
        self._metadata[code] = metadata or CaptchaProviderMetadata()

    def unregister(self, code: str) -> None:
        """Unregister a captcha provider by code / 按代码注销验证码提供者"""
        if code == "image":
            return
        self._providers.pop(code, None)
        self._metadata.pop(code, None)

    def get(self, code: str) -> ICaptchaProvider | None:
        """Get a captcha provider by code / 按代码获取验证码提供者"""
        return self._providers.get(code)

    def get_metadata(self, code: str) -> CaptchaProviderMetadata | None:
        """Get captcha provider metadata by code / 按代码获取验证码提供者元数据"""
        return self._metadata.get(code)

    def get_default(self) -> ICaptchaProvider | None:
        """Get the default captcha provider (image) / 获取默认验证码提供者（图形）"""
        return self.get("image")


# Global singleton instance / 全局单例实例
registry = CaptchaRegistry()


__all__ = ["CaptchaRegistry", "registry"]
