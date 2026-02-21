"""
Webhook API Plugin — ApiPlugin 示例

演示如何创建一个 API 端点插件，注册自定义 FastAPI 路由。

注册端点：
- POST /plugins/webhook-api/receive  — 接收 webhook 回调
- GET  /plugins/webhook-api/status   — 查看接收状态
"""

from __future__ import annotations

from typing import Any

from app.core.logging import LogManager
from app.plugins.context import PluginContext
from app.plugins.extensions.api_plugin import ApiPlugin
from app.core.base_model import utc_now

logger = LogManager.get_logger("app")


class WebhookApiPlugin(ApiPlugin):
    """
    Webhook 接收器插件

    注册两个 API 端点：
    1. POST /receive — 接收外部 webhook 回调，校验 token 后记录
    2. GET  /status  — 返回最近接收的 webhook 统计
    """

    # 内存中存储最近的 webhook 记录（示例用途）
    _received: list[dict[str, Any]] = []
    _max_history: int = 100

    @property
    def name(self) -> str:
        return "webhook-api"

    @property
    def display_name(self) -> str:
        return "Webhook Receiver"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Receives external webhook callbacks and logs them"

    @property
    def author(self) -> str:
        return "NovusAI"

    def get_auth_level(self) -> str:
        """
        Webhook 接收端点通常需要对外公开（由 secret_token 自行鉴权）
        """
        return "public"

    def get_router(self):
        """
        创建并返回 FastAPI 路由器

        Returns:
            包含 /receive 和 /status 端点的 APIRouter
        """
        from fastapi import APIRouter, Header, HTTPException

        router = APIRouter()

        @router.post("/receive", summary="接收 Webhook 回调")
        async def receive_webhook(
            payload: dict[str, Any],
            x_webhook_token: str | None = Header(None),
        ) -> dict[str, str]:
            """
            接收外部系统的 webhook 回调

            通过 X-Webhook-Token header 进行身份校验。
            校验通过后将 payload 记录到内存中。
            """
            # 校验 token（从插件配置中获取）
            expected_token = self._get_config_value("secret_token")
            if expected_token and x_webhook_token != expected_token:
                raise HTTPException(status_code=403, detail="Invalid webhook token")

            # 记录 webhook
            record = {
                "received_at": utc_now().isoformat(),
                "payload": payload,
                "source": payload.get("source", "unknown"),
            }
            self._received.append(record)

            # 保持历史记录在限制内
            if len(self._received) > self._max_history:
                self._received = self._received[-self._max_history:]

            logger.info(
                "[WebhookApi] Received webhook: source=%s",
                record["source"],
            )
            return {"status": "ok"}

        @router.get("/status", summary="查看 Webhook 接收状态")
        async def get_status() -> dict[str, Any]:
            """
            返回 webhook 接收统计信息

            包括总接收数量和最近 5 条记录的摘要。
            """
            recent = self._received[-5:] if self._received else []
            return {
                "total_received": len(self._received),
                "recent": [
                    {
                        "received_at": r["received_at"],
                        "source": r["source"],
                    }
                    for r in reversed(recent)
                ],
            }

        return router

    _runtime_config: dict[str, Any] = {}

    def _get_config_value(self, key: str) -> str | None:
        """从插件运行时配置中获取值"""
        return self._runtime_config.get(key)

    async def on_enable(self, ctx: PluginContext) -> None:
        """插件启用时的回调 — 缓存运行时配置供路由处理器使用"""
        self._received = []
        self._runtime_config = dict(ctx.config) if ctx.config else {}
        if ctx.logger:
            ctx.logger.info("WebhookApiPlugin enabled — routes registered")

    async def on_disable(self, ctx: PluginContext) -> None:
        """插件禁用时的回调"""
        self._received = []
        self._runtime_config = {}
        if ctx.logger:
            ctx.logger.info("WebhookApiPlugin disabled — routes removed")
