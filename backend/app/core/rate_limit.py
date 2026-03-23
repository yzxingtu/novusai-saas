"""
IP 级速率限制 / IP-based rate limiting.

In-memory sliding window for login and other public endpoints.
内存滑动窗口，用于登录等公开端点防暴力破解。
"""

from __future__ import annotations

import time
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.i18n import _
from app.core.response import build_error_payload


_login_buckets: dict[str, list[float]] = defaultdict(list)
_LOGIN_WINDOW = 60  # seconds
_LOGIN_MAX = 10  # requests per window
_eviction_last = 0.0


def _get_client_ip(request: Request) -> str:
    """
    Get real client IP, respecting reverse proxy headers.
    获取真实客户端 IP，支持反向代理头 X-Forwarded-For / X-Real-IP。
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def check_login_rate_limit(request: Request) -> JSONResponse | None:
    """
    IP 维度限流：10 次/60 秒 / IP rate limit: 10 req / 60 sec.

    Returns 429 JSONResponse if over limit, None otherwise.
    超限返回 429，否则返回 None。
    """
    global _eviction_last
    client_ip = _get_client_ip(request)
    now = time.monotonic()
    cutoff = now - _LOGIN_WINDOW

    # Periodic eviction of stale IPs / 定期清理过期 IP
    if now - _eviction_last > 300:
        stale = [ip for ip, ts in _login_buckets.items() if not ts or ts[-1] < cutoff]
        for ip in stale:
            del _login_buckets[ip]
        _eviction_last = now

    bucket = [t for t in _login_buckets.get(client_ip, []) if t > cutoff]
    if len(bucket) >= _LOGIN_MAX:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(int(_LOGIN_WINDOW))},
            content=build_error_payload(
                message=_("auth.rate_limited"),
                code=4290,
                extra={"retry_after": int(_LOGIN_WINDOW)},
            ),
        )

    bucket.append(now)
    _login_buckets[client_ip] = bucket
    return None
