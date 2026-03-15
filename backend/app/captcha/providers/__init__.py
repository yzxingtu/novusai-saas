"""
Captcha Providers / 验证码提供者实现

Built-in captcha provider implementations.
内置验证码提供者实现。
"""

from app.captcha.providers.image import ImageCaptchaProvider

__all__ = ["ImageCaptchaProvider"]
