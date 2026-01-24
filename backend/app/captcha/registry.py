from __future__ import annotations
from typing import Dict
from app.captcha.provider import ICaptchaProvider, StubImageCaptchaProvider


class CaptchaRegistry:
    _instance: "CaptchaRegistry | None" = None

    def __new__(cls) -> "CaptchaRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._providers: Dict[str, ICaptchaProvider] = {}
        self.register("image", StubImageCaptchaProvider())
        self._initialized = True

    def register(self, code: str, provider: ICaptchaProvider) -> None:
        self._providers[code] = provider

    def get(self, code: str) -> ICaptchaProvider | None:
        return self._providers.get(code)

    def get_default(self) -> ICaptchaProvider | None:
        return self.get("image")


registry = CaptchaRegistry()


__all__ = ["CaptchaRegistry", "registry"]
