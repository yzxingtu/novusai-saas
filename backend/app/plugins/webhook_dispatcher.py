"""
Plugin Webhook dispatcher.
/ 插件 Webhook 分发器

Receives webhook callbacks from external systems and dispatches to plugin-registered handlers.
This route bypasses auth middleware (external systems have no Token).
/ 接收外部系统的 Webhook 回调，分发到插件注册的 handler。

Path convention / 路径约定: /webhooks/plugins/{plugin_name}/{path}
"""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.rbac.decorators import public

logger = get_logger(__name__)

webhook_router = APIRouter(tags=["Plugin Webhook / 插件 Webhook"])


@webhook_router.api_route(
    "/webhooks/plugins/{plugin_name}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
    include_in_schema=False,
)
@public
async def webhook_dispatcher(
    plugin_name: str,
    path: str,
    request: Request,
):
    """
    Plugin Webhook unified dispatcher (bypasses auth middleware).
    / 插件 Webhook 统一分发器

    Flow: find plugin → match webhook → verify origin → call handler → log
    / 流程：查找插件 → 匹配 → 验证 → 调用 → 日志
    """
    start = time.perf_counter()

    # 1. Find enabled plugin / 查找已启用插件
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        from sqlalchemy import select

        from app.models.system.plugin import Plugin

        result = await db.execute(
            select(Plugin.status, Plugin.config, Plugin.manifest).where(
                Plugin.name == plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        row = result.one_or_none()
        from app.enums.plugin import PluginStatusEnum
        if not row or row[0] != PluginStatusEnum.ENABLED.value:
            return JSONResponse(
                status_code=404,
                content={"error": f"Plugin '{plugin_name}' not found or disabled"},
            )

        plugin_config = row[1] or {}
        manifest_data = row[2] or {}

    # 2. Match webhook definition / 匹配 webhook 定义
    extensions = manifest_data.get("extensions", {})
    webhooks = extensions.get("webhooks", [])
    method = request.method.upper()

    matched_webhook = None
    _webhook_path_params: dict[str, str] = {}
    for wh in webhooks:
        wh_path = wh.get("path", "").strip("/")
        wh_method = wh.get("method", "POST").upper()
        if wh_method != method:
            continue
        from app.plugins.api_dispatcher import _match_route_path
        matched, params = _match_route_path(wh_path, path)
        if matched:
            matched_webhook = wh
            _webhook_path_params = params
            break

    if not matched_webhook:
        return JSONResponse(
            status_code=404,
            content={"error": f"Webhook {method} /{path} not found"},
        )

    # 3. Origin verification / 来源验证
    auth_config = matched_webhook.get("auth", {})
    auth_type = auth_config.get("type", "none")

    if auth_type != "none":
        body = await request.body()
        is_valid = await _verify_webhook_auth(
            auth_type, auth_config, plugin_config, request, body,
        )
        if not is_valid:
            logger.warning(
                "Webhook auth failed: %s/%s (type=%s)",
                plugin_name, path, auth_type,
            )
            return JSONResponse(
                status_code=401,
                content={"error": "Webhook authentication failed"},
            )
    else:
        body = await request.body()

    # 4. Find and call handler / 查找并调用 handler
    from app.plugins.registry import ExtensionRegistry

    registry = ExtensionRegistry.get_instance()
    plugin_webhooks = registry.get_plugin_webhooks(plugin_name)
    full_path = f"/plugins/{plugin_name}/{path}"

    handler_info = plugin_webhooks.get(full_path)
    if not handler_info:
        # Try loading handler directly from manifest / 尝试从 manifest 加载
        handler_path = matched_webhook.get("handler", "")
        handler = _load_webhook_handler(plugin_name, handler_path)
    else:
        handler = handler_info.get("handler")

    if not handler:
        return JSONResponse(
            status_code=500,
            content={"error": "Webhook handler not available"},
        )

    try:
        # Pass parsed request data to handler / 传递解析后的数据给 handler
        import json
        try:
            payload = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            payload = {"raw_body": body.decode("utf-8", errors="replace")}

        import asyncio
        if asyncio.iscoroutinefunction(handler):
            result = await handler(
                plugin_name=plugin_name,
                path=path,
                method=method,
                headers=dict(request.headers),
                payload=payload,
            )
        else:
            result = handler(
                plugin_name=plugin_name,
                path=path,
                method=method,
                headers=dict(request.headers),
                payload=payload,
            )

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "Webhook %s/%s handled in %dms",
            plugin_name, path, duration_ms,
        )

        if isinstance(result, dict):
            return JSONResponse(status_code=200, content=result)
        return JSONResponse(status_code=200, content={"ok": True})

    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(
            "Webhook handler error: %s/%s: %s (%dms)",
            plugin_name, path, exc, duration_ms, exc_info=True,
        )
        err_message = str(exc) if settings.DEBUG else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"error": err_message},
        )


async def _verify_webhook_auth(
    auth_type: str,
    auth_config: dict,
    plugin_config: dict,
    request: Request,
    body: bytes,
) -> bool:
    """Verify Webhook origin / 验证 Webhook 来源"""
    def _decrypt_if_needed(secret_value: str) -> str | None:
        from app.plugins.crypto import _FERNET_PREFIX

        if secret_value.startswith(_FERNET_PREFIX):
            from app.core.security import decrypt_data

            try:
                return decrypt_data(secret_value)
            except Exception:
                return None
        return secret_value

    if auth_type == "hmac":
        secret_key = auth_config.get("secret_config_key", "")
        secret = plugin_config.get(secret_key, "")
        if not secret:
            return False

        header_name = auth_config.get("header_name", "X-Webhook-Signature")
        signature = request.headers.get(header_name, "")
        if not signature:
            return False

        # Decrypt secret (if encrypted stored) / 解密密钥
        decrypted = _decrypt_if_needed(secret)
        if decrypted is None:
            return False
        secret = decrypted

        expected = hmac.new(
            secret.encode(), body, hashlib.sha256,
        ).hexdigest()

        # Support sha256=xxx format / 支持 sha256=xxx 格式
        if signature.startswith("sha256="):
            signature = signature[7:]

        return hmac.compare_digest(expected, signature)

    elif auth_type == "token":
        token_key = auth_config.get("secret_config_key", "webhook_token")
        expected_token = plugin_config.get(token_key, "")
        if not expected_token:
            return False

        decrypted = _decrypt_if_needed(expected_token)
        if decrypted is None:
            return False
        expected_token = decrypted

        header_name = auth_config.get("header_name", "Authorization")
        actual_token = request.headers.get(header_name, "")
        if actual_token.startswith("Bearer "):
            actual_token = actual_token[7:]

        return hmac.compare_digest(expected_token, actual_token)

    elif auth_type == "signature":
        # Same handling as hmac / 与 hmac 相同处理
        return await _verify_webhook_auth("hmac", auth_config, plugin_config, request, body)

    # unknown auth type → fail-close
    logger.warning(
        "Webhook auth: unknown auth_type '%s', denying request",
        auth_type,
    )
    return False


def _load_webhook_handler(plugin_name: str, handler_path: str):
    """Load Webhook handler — delegate to unified module loader
    / 加载 Webhook handler"""
    from app.plugins.module_loader import load_plugin_handler

    return load_plugin_handler(plugin_name, handler_path)
