"""
Captcha Module
验证码模块

Provides captcha generation and verification:
提供验证码生成与验证功能：
- provider: Captcha provider interface / 验证码提供者接口
- providers: Built-in captcha implementations / 内置验证码实现
- registry: Provider registry (singleton) / 提供者注册中心（单例）
- service: Captcha business service / 验证码业务服务
"""

from app.captcha.provider import (
    CaptchaChallenge,
    CaptchaProviderMetadata,
    CaptchaVerificationResult,
    ICaptchaProvider,
)
from app.captcha.registry import CaptchaRegistry, registry
from app.captcha.service import CaptchaService

__all__ = [
    "ICaptchaProvider",
    "CaptchaChallenge",
    "CaptchaProviderMetadata",
    "CaptchaVerificationResult",
    "registry",
    "CaptchaRegistry",
    "CaptchaService",
]
