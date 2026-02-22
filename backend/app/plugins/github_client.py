"""
Git 平台统一客户端

支持 GitHub 和 Gitee 双节点。根据 PLUGIN_REGISTRY_MIRROR 配置自动选择平台，
统一处理代理、认证、重试、超时、大小限制。

GitHub（海外用户 / 有代理的国内用户）:
- Raw:     https://raw.githubusercontent.com/{repo}/{branch}/{path}
- Release: https://api.github.com/repos/{repo}/releases/tags/{tag}
- Auth:    Authorization: Bearer {token}

Gitee（国内用户）:
- Raw:     https://gitee.com/{repo}/raw/{branch}/{path}
- Release: https://gitee.com/api/v5/repos/{repo}/releases/tags/{tag}
- Auth:    ?access_token={token}（query param）
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# 平台类型
PlatformType = Literal["github", "gitee"]

# 默认超时（秒）
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 30
_DOWNLOAD_TIMEOUT = 300

# 重试配置
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1


# ========================================
# 平台感知：URL 构建
# ========================================

def get_mirror() -> PlatformType:
    """获取当前配置的镜像平台"""
    mirror = settings.PLUGIN_REGISTRY_MIRROR.lower()
    if mirror in ("github", "gitee"):
        return mirror  # type: ignore[return-value]
    return "github"


def build_raw_url(
    repo: str,
    branch: str,
    path: str,
    *,
    platform: PlatformType | None = None,
) -> str:
    """
    构建 raw 文件 URL

    Args:
        repo: 仓库全名（如 novusai-plugins/plugin-registry）
        branch: 分支名（如 main）
        path: 文件路径（如 registry.json）
        platform: 指定平台，None 使用配置值
    """
    p = platform or get_mirror()
    if p == "gitee":
        return f"https://gitee.com/{repo}/raw/{branch}/{path}"
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"


def build_release_api_url(
    repo: str,
    tag: str,
    *,
    platform: PlatformType | None = None,
) -> str:
    """
    构建 Release API URL

    Args:
        repo: 仓库全名
        tag: Release tag（如 v1.2.0）
        platform: 指定平台，None 使用配置值
    """
    p = platform or get_mirror()
    if p == "gitee":
        return f"https://gitee.com/api/v5/repos/{repo}/releases/tags/{tag}"
    return f"https://api.github.com/repos/{repo}/releases/tags/{tag}"


def build_repo_url(
    repo: str,
    *,
    platform: PlatformType | None = None,
) -> str:
    """
    构建仓库主页 URL（用于前端展示链接）

    Args:
        repo: 仓库全名
        platform: 指定平台，None 使用配置值
    """
    p = platform or get_mirror()
    if p == "gitee":
        return f"https://gitee.com/{repo}"
    return f"https://github.com/{repo}"


# ========================================
# 平台感知：认证 + 代理
# ========================================

def resolve_url(url: str) -> str:
    """
    根据 GITHUB_PROXY 配置替换 GitHub URL 前缀（仅 GitHub 生效）

    Gitee 无需代理（国内可直接访问），故不处理 Gitee URL。
    """
    proxy = settings.GITHUB_PROXY.rstrip("/") if settings.GITHUB_PROXY else ""
    if not proxy:
        return url

    github_prefixes = (
        "https://raw.githubusercontent.com/",
        "https://github.com/",
        "https://api.github.com/",
    )
    for prefix in github_prefixes:
        if url.startswith(prefix):
            return f"{proxy}/{url}"

    return url


def _get_auth_params(url: str) -> tuple[dict[str, str], dict[str, str]]:
    """
    根据 URL 所属平台返回 (headers, query_params)

    GitHub: Authorization header
    Gitee:  access_token query param
    """
    headers: dict[str, str] = {
        "User-Agent": f"NovusAI/{settings.APP_VERSION}",
    }
    params: dict[str, str] = {}

    if "gitee.com" in url:
        headers["Accept"] = "application/json"
        if settings.GITEE_TOKEN:
            params["access_token"] = settings.GITEE_TOKEN
    else:
        headers["Accept"] = "application/vnd.github.v3+json"
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    return headers, params


# ========================================
# 通用请求方法
# ========================================

async def async_get(
    url: str,
    *,
    timeout: float | None = None,
    raw_response: bool = False,
) -> dict[str, Any] | str | bytes:
    """
    发起 GET 请求（自动识别平台 + 代理 + 认证 + 指数退避重试）

    Args:
        url: 目标 URL（GitHub 或 Gitee）
        timeout: 自定义超时（秒）
        raw_response: True 返回 bytes/text，False 返回 JSON dict

    Returns:
        JSON dict 或 bytes/text

    Raises:
        httpx.HTTPStatusError: 重试耗尽后仍失败
    """
    resolved = resolve_url(url)
    headers, query_params = _get_auth_params(url)
    read_timeout = timeout or _READ_TIMEOUT

    last_exc: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT,
                    read=read_timeout,
                    write=read_timeout,
                    pool=read_timeout,
                ),
                follow_redirects=True,
            ) as client:
                resp = await client.get(
                    resolved, headers=headers, params=query_params,
                )

                _check_rate_limit(resp)

                if resp.status_code == 429:
                    retry_after = int(
                        resp.headers.get("Retry-After", _RETRY_BASE_DELAY * attempt)
                    )
                    logger.warning(
                        "Rate limited (429), retry after %ds (attempt %d/%d): %s",
                        retry_after, attempt, _MAX_RETRIES, url,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                resp.raise_for_status()

                if raw_response:
                    content_type = resp.headers.get("content-type", "")
                    if "text" in content_type:
                        return resp.text
                    return resp.content

                return resp.json()

        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code in (429, 500, 502, 503, 504):
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Request failed (HTTP %d), retrying in %ds (attempt %d/%d): %s",
                    exc.response.status_code, delay, attempt, _MAX_RETRIES, url,
                )
                await asyncio.sleep(delay)
                continue
            raise

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            last_exc = exc
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Request error, retrying in %ds (attempt %d/%d): %s — %s",
                delay, attempt, _MAX_RETRIES, url, str(exc),
            )
            await asyncio.sleep(delay)
            continue

    if last_exc:
        raise last_exc
    raise httpx.ReadTimeout(
        f"Request failed after {_MAX_RETRIES} retries: {url}"
    )


async def async_download(
    url: str,
    dest_path: str | Path,
    *,
    max_size: int | None = None,
    expected_content_types: tuple[str, ...] | None = None,
) -> Path:
    """
    流式下载文件（自动识别平台 + 代理 + 认证 + 大小限制 + MIME 校验）

    Args:
        url: 下载 URL（GitHub 或 Gitee）
        dest_path: 目标文件路径
        max_size: 最大文件大小（字节），None 使用配置默认值
        expected_content_types: 允许的 MIME 类型前缀，None 不校验

    Returns:
        下载完成的文件路径

    Raises:
        ValueError: MIME 类型不匹配或文件过大
        httpx.HTTPStatusError: HTTP 错误
    """
    resolved = resolve_url(url)
    headers, query_params = _get_auth_params(url)
    headers["Accept"] = "application/octet-stream"
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    size_limit = max_size or settings.PLUGIN_MAX_PACKAGE_SIZE
    last_exc: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT,
                    read=_DOWNLOAD_TIMEOUT,
                    write=_DOWNLOAD_TIMEOUT,
                    pool=_DOWNLOAD_TIMEOUT,
                ),
                follow_redirects=True,
            ) as client:
                async with client.stream(
                    "GET", resolved, headers=headers, params=query_params,
                ) as resp:
                    if resp.status_code == 429:
                        retry_after = int(
                            resp.headers.get("Retry-After", _RETRY_BASE_DELAY * attempt)
                        )
                        logger.warning(
                            "Download rate limited (429), retry after %ds",
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    resp.raise_for_status()

                    if expected_content_types:
                        content_type = resp.headers.get("content-type", "")
                        if not any(
                            content_type.startswith(ct)
                            for ct in expected_content_types
                        ):
                            raise ValueError(
                                f"Unexpected content type: {content_type}. "
                                f"Expected one of: {expected_content_types}"
                            )

                    downloaded = 0
                    with open(dest, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=8192):
                            downloaded += len(chunk)
                            if downloaded > size_limit:
                                f.close()
                                dest.unlink(missing_ok=True)
                                raise ValueError(
                                    f"Download exceeds size limit: "
                                    f"{downloaded} > {size_limit} bytes"
                                )
                            f.write(chunk)

                    logger.info(
                        "Downloaded %d bytes from %s → %s",
                        downloaded, url, dest,
                    )
                    return dest

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            last_exc = exc
            dest.unlink(missing_ok=True)
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Download error, retrying in %ds (attempt %d/%d): %s — %s",
                delay, attempt, _MAX_RETRIES, url, str(exc),
            )
            await asyncio.sleep(delay)
            continue

        except httpx.HTTPStatusError as exc:
            last_exc = exc
            dest.unlink(missing_ok=True)
            if exc.response.status_code in (429, 500, 502, 503, 504):
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
                continue
            raise

        except ValueError:
            raise

    if last_exc:
        raise last_exc
    raise httpx.ReadTimeout(
        f"Download failed after {_MAX_RETRIES} retries: {url}"
    )


# ========================================
# Release asset 解析
# ========================================

def parse_release_download_url(
    release_data: dict[str, Any],
    *,
    platform: PlatformType | None = None,
) -> str | None:
    """
    从 Release API 响应中提取 .zip/.nap asset 下载 URL

    GitHub assets 结构: release_data["assets"][*]["browser_download_url"]
    Gitee  assets 结构: release_data["assets"][*]["browser_download_url"]

    Args:
        release_data: Release API 响应 JSON
        platform: 平台类型

    Returns:
        下载 URL，未找到返回 None
    """
    assets = release_data.get("assets") or []
    for asset in assets:
        name = asset.get("name", "")
        if name.endswith((".zip", ".nap")):
            return asset.get("browser_download_url")
    return None


# ========================================
# 辅助
# ========================================

def get_repo_for_mirror(
    repos: dict[str, str],
    *,
    platform: PlatformType | None = None,
) -> str:
    """
    从 registry 条目的 repos 字典中选择当前镜像对应的 repo

    Args:
        repos: {"github": "owner/repo", "gitee": "owner/repo"}
        platform: 指定平台，None 使用配置值

    Returns:
        仓库全名

    Raises:
        ValueError: 当前镜像无对应 repo
    """
    p = platform or get_mirror()
    repo = repos.get(p)
    if not repo:
        fallback = "github" if p == "gitee" else "gitee"
        repo = repos.get(fallback)
    if not repo:
        raise ValueError(
            f"No repository configured for mirror '{p}': {repos}"
        )
    return repo


def _check_rate_limit(resp: httpx.Response) -> None:
    """检查 API 速率限制并在接近时发出警告（GitHub 专用头）"""
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining is not None:
        try:
            remaining_int = int(remaining)
            if remaining_int < 10:
                limit = resp.headers.get("X-RateLimit-Limit", "?")
                logger.warning(
                    "API rate limit low: %d/%s remaining",
                    remaining_int, limit,
                )
        except (ValueError, TypeError):
            pass
