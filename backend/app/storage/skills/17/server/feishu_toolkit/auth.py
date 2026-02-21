"""飞书 tenant_access_token 管理

Token 有效期 2 小时，提前 5 分钟刷新。
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import ssl

import httpx
import truststore
from fastapi import HTTPException

# 使用系统证书存储，解决 macOS 上 SSL 验证问题
truststore.inject_into_ssl()
_ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

FEISHU_HOST = "https://open.feishu.cn"
TOKEN_URL = f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal"

logger = logging.getLogger("feishu_toolkit.auth")


@dataclass
class _TokenCache:
    token: str = ""
    expires_at: float = 0.0


_cache = _TokenCache()

# 提前 5 分钟刷新
_REFRESH_MARGIN = 300


def _get_credentials() -> tuple[str, str]:
    """读取飞书应用凭证"""
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise HTTPException(
            status_code=500,
            detail="FEISHU_APP_ID / FEISHU_APP_SECRET is not set.",
        )
    return app_id, app_secret


def get_tenant_token() -> str:
    """获取 tenant_access_token，自动刷新过期 token"""
    now = time.time()
    if _cache.token and now < _cache.expires_at:
        return _cache.token

    app_id, app_secret = _get_credentials()
    body = {"app_id": app_id, "app_secret": app_secret}

    try:
        with httpx.Client(timeout=10.0, verify=_ssl_ctx) as client:
            resp = client.post(TOKEN_URL, json=body)
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch tenant_access_token: %s", exc)
        raise HTTPException(status_code=502, detail="Feishu auth unavailable.") from exc

    data = resp.json()
    if data.get("code") != 0:
        logger.error("Feishu auth error: %s", data)
        raise HTTPException(
            status_code=502,
            detail=f"Feishu auth error: {data.get('msg', 'unknown')}",
        )

    _cache.token = data["tenant_access_token"]
    _cache.expires_at = now + data.get("expire", 7200) - _REFRESH_MARGIN
    logger.info("tenant_access_token refreshed, expires in %ds", data.get("expire", 7200))
    return _cache.token


def feishu_headers() -> dict[str, str]:
    """返回带有认证信息的请求头"""
    return {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {get_tenant_token()}",
    }


def feishu_request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    """通用飞书 API 请求封装

    自动处理认证、错误和重试。
    """
    url = f"{FEISHU_HOST}{path}"
    headers = feishu_headers()

    try:
        with httpx.Client(timeout=30.0, verify=_ssl_ctx) as client:
            resp = client.request(method, url, headers=headers, params=params, json=json_body)
    except httpx.HTTPError as exc:
        logger.error("Feishu API request failed: %s %s – %s", method, path, exc)
        raise HTTPException(status_code=502, detail="Feishu API unavailable.") from exc

    if resp.status_code != 200:
        logger.error("Feishu API HTTP error: status=%d, body=%s", resp.status_code, resp.text)
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    code = data.get("code", -1)
    if code != 0:
        logger.error("Feishu API biz error: code=%d, msg=%s", code, data.get("msg"))
        raise HTTPException(
            status_code=400,
            detail=f"Feishu API error (code={code}): {data.get('msg', 'unknown')}",
        )

    return data.get("data", data)
