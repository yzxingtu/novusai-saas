"""
Shared helpers and constants for plugin manifest schemas.
"""

import re

# ── Type aliases / 类型别名 ──
I18nText = dict[str, str]
"""Multilingual text, e.g. {"zh-CN": "CRM 管理", "en": "CRM Management"}. / 多语言文本。"""

# Plugin manifest menu/slot scope = endpoint side, not ResourceScopeEnum. / 插件菜单/插槽 scope 表端侧，非 ResourceScopeEnum
# Only canonical values are accepted; legacy aliases are no longer tolerated. / 仅接受规范取值，不再兼容历史别名
_VALID_PLUGIN_ENDPOINT_SCOPES = frozenset({"admin", "tenant", "both", ""})
_VALID_PLUGIN_PERMISSION_EXT_SCOPES = frozenset({"admin", "tenant", "both"})

_FRONTEND_PLUGIN_ROUTE_PREFIXES = ("/admin/plugins/", "/tenant/plugins/")
_API_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_WEBHOOK_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE"}
_API_AUTH_VALUES = {"required", "none"}
_WEBHOOK_AUTH_VALUES = {"none", "hmac", "token", "signature"}
_PATH_PARAM_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SOCKETIO_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_DB_TABLE_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,62}_$")
# Handler path: dot-separated Python module path, e.g. "api.handlers.handle_current"
# Allows letters, digits, underscores and dots; forbids .. / \ and other path traversal chars
# / Handler 路径：点分隔的 Python 模块路径
# 允许字母、数字、下划线和点；禁止 .. / \ 等路径遍历字符
_HANDLER_PATH_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _validate_handler_path(v: str, field_name: str = "handler") -> str:
    """Handler module path validation: prevent path traversal and illegal characters (e.g. ../../etc)
    / Handler 模块路径校验：防止路径遍历和非法字符"""
    path = (v or "").strip()
    if not path:
        raise ValueError(f"{field_name} cannot be empty")
    if not _HANDLER_PATH_PATTERN.match(path):
        raise ValueError(
            f"{field_name} '{path}' is invalid. "
            f"Only letters, digits, underscores and dots are allowed "
            f"(e.g. 'api.handlers.my_handler')."
        )
    return path


def _validate_frontend_plugin_route_path(path: str) -> str:
    """Frontend plugin routes must be under /admin/plugins/* or /tenant/plugins/*.
    / 前端插件路由必须位于 /admin/plugins/* 或 /tenant/plugins/* 下。"""
    if not any(path.startswith(prefix) for prefix in _FRONTEND_PLUGIN_ROUTE_PREFIXES):
        raise ValueError(
            "Frontend plugin route path must start with '/admin/plugins/' "
            "or '/tenant/plugins/'"
        )
    return path


def _normalize_extension_path(
    path: str,
    *,
    field_name: str,
    keep_leading_slash: bool,
    allow_path_params: bool = True,
) -> str:
    """Extension point path normalization and security validation.
    / 扩展点路径规范化与安全校验。"""
    normalized = (path or "").strip().replace("\\", "/")
    normalized = normalized.strip("/")
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")

    for segment in normalized.split("/"):
        if segment in {"", ".", ".."}:
            raise ValueError(f"{field_name} contains illegal segment '{segment}'")

        if segment.startswith("{") and segment.endswith("}"):
            if not allow_path_params:
                raise ValueError(f"{field_name} does not allow path parameters")
            param_name = segment[1:-1].strip()
            if not _PATH_PARAM_NAME_PATTERN.match(param_name):
                raise ValueError(
                    f"{field_name} contains invalid path parameter name '{param_name}'"
                )
            continue

        if "{" in segment or "}" in segment:
            raise ValueError(
                f"{field_name} contains malformed parameter segment '{segment}'"
            )

    return f"/{normalized}" if keep_leading_slash else normalized
