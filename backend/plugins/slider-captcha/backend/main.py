"""Slider captcha plugin entrypoint. / 滑动拼图验证码插件入口。"""

from app.plugins.base import PluginBase

from . import captcha_provider
from .captcha_provider import SliderCaptchaProvider


class SliderCaptchaPlugin(PluginBase):
    """Slider captcha plugin. / 滑动拼图验证码插件。"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Slider captcha plugin installed")

    async def on_enable(self, ctx) -> None:
        ctx.get_logger().info("Slider captcha plugin enabled")

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("Slider captcha plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("Slider captcha plugin uninstalled")


__all__ = ["SliderCaptchaPlugin", "SliderCaptchaProvider", "captcha_provider"]
