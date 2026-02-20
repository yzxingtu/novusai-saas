"""
插件安全机制

提供：
1. Manifest 完整性校验（必填字段、版本格式、权限合法性）
2. 权限感知的 PluginContext 构建（仅注入已声明权限对应的能力）
3. 敏感配置加密存储（config_schema 中 format:password 的字段）
4. 插件操作审计日志
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

from app.core.i18n import _
from app.core.logging import LogManager
from app.core.security import encrypt_data, decrypt_data
from app.exceptions import ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = LogManager.get_logger("app")

# 合法的插件权限声明
VALID_PERMISSIONS = frozenset({
    "db:read",
    "db:write",
    "http:outbound",
    "tool:register",
    "event:subscribe",
    "event:publish",
    "api:register",
    "skill:register",
    "config:read",
    "config:write",
    "storage:read",
    "storage:write",
    "storage:register",
})

# semver 正则
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?"
    r"(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$"
)

# 插件名称正则（小写字母、数字、连字符，防止路径穿越）
_PLUGIN_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")

# Manifest 必填字段
_REQUIRED_MANIFEST_FIELDS = {"name", "display_name", "version", "entry_point"}


# ========================================
# Manifest 校验
# ========================================

def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """
    校验插件 manifest 完整性

    检查项：
    - 必填字段存在且非空
    - version 符合 semver 格式
    - required_permissions 中的权限合法

    Args:
        manifest: 插件 manifest 字典

    Returns:
        错误列表（为空表示通过）
    """
    errors: list[str] = []

    # 必填字段
    for field in _REQUIRED_MANIFEST_FIELDS:
        val = manifest.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing required field: {field}")

    # 名称格式（防止路径穿越和非法字符）
    name = manifest.get("name", "")
    if name and not _PLUGIN_NAME_RE.match(name):
        errors.append(
            f"Invalid plugin name: '{name}'. "
            "Must be lowercase letters, digits, hyphens, "
            "starting with a letter and ending with a letter or digit."
        )

    # 版本号格式
    version = manifest.get("version", "")
    if version and not _SEMVER_RE.match(version):
        errors.append(f"Invalid version format: {version} (expected semver)")

    # 权限合法性
    permissions = manifest.get("required_permissions") or []
    for perm in permissions:
        if perm not in VALID_PERMISSIONS:
            errors.append(f"Unknown permission: {perm}")

    return errors


def validate_manifest_or_raise(manifest: dict[str, Any]) -> None:
    """
    校验 manifest，失败时抛出 ValidationException

    Args:
        manifest: 插件 manifest 字典

    Raises:
        ValidationException: manifest 不合法
    """
    errors = validate_manifest(manifest)
    if errors:
        raise ValidationException(
            _("plugin.invalid_manifest") + ": " + "; ".join(errors)
        )


# ========================================
# 权限感知的 Context 构建
# ========================================

def build_permission_aware_context_kwargs(
    declared_permissions: list[str] | None,
    *,
    db: AsyncSession | None = None,
    event_bus: object | None = None,
    tool_registry: object | None = None,
) -> dict[str, Any]:
    """
    根据插件声明的权限，决定注入哪些能力到 PluginContext

    未声明 db:read/db:write → db=None
    未声明 event:subscribe/event:publish → event_bus=None
    未声明 tool:register → tool_registry=None

    Args:
        declared_permissions: 插件声明的权限列表
        db: 数据库会话
        event_bus: 事件总线
        tool_registry: 工具注册表

    Returns:
        用于构建 PluginContext 的 kwargs
    """
    perms = set(declared_permissions or [])

    kwargs: dict[str, Any] = {}

    # DB access
    if perms & {"db:read", "db:write"}:
        kwargs["db"] = db
    else:
        kwargs["db"] = None

    # Event bus
    if perms & {"event:subscribe", "event:publish"}:
        kwargs["event_bus"] = event_bus
    else:
        kwargs["event_bus"] = None

    # Tool registry
    if "tool:register" in perms:
        kwargs["tool_registry"] = tool_registry
    else:
        kwargs["tool_registry"] = None

    return kwargs


# ========================================
# 敏感配置加密 / 解密
# ========================================

_ENCRYPTED_PREFIX = "enc:"


def encrypt_sensitive_config(
    config: dict[str, Any],
    config_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    加密 config 中标记为 format:password 的字段

    遍历 config_schema.properties，对标记了 "format": "password" 的字段，
    将其值加密后以 "enc:" 前缀存储。

    Args:
        config: 插件配置
        config_schema: JSON Schema

    Returns:
        加密后的配置副本
    """
    if not config_schema or not config:
        return dict(config) if config else {}

    properties = config_schema.get("properties", {})
    result = dict(config)

    for field_name, field_schema in properties.items():
        if field_schema.get("format") == "password":
            value = result.get(field_name)
            if value and isinstance(value, str) and not value.startswith(_ENCRYPTED_PREFIX):
                result[field_name] = _ENCRYPTED_PREFIX + encrypt_data(value)

    return result


def decrypt_sensitive_config(
    config: dict[str, Any],
    config_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    解密 config 中加密的字段

    Args:
        config: 含加密值的配置
        config_schema: JSON Schema

    Returns:
        解密后的配置副本
    """
    if not config_schema or not config:
        return dict(config) if config else {}

    properties = config_schema.get("properties", {})
    result = dict(config)

    for field_name, field_schema in properties.items():
        if field_schema.get("format") == "password":
            value = result.get(field_name)
            if value and isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX):
                try:
                    result[field_name] = decrypt_data(
                        value[len(_ENCRYPTED_PREFIX):]
                    )
                except Exception:
                    logger.warning(
                        "Failed to decrypt config field: %s", field_name
                    )

    return result


def mask_sensitive_config(
    config: dict[str, Any],
    config_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    脱敏展示：将 password 字段替换为 ******

    Args:
        config: 配置
        config_schema: JSON Schema

    Returns:
        脱敏后的配置副本
    """
    if not config_schema or not config:
        return dict(config) if config else {}

    properties = config_schema.get("properties", {})
    result = dict(config)

    for field_name, field_schema in properties.items():
        if field_schema.get("format") == "password":
            if field_name in result and result[field_name]:
                result[field_name] = "******"

    return result


# ========================================
# 审计日志
# ========================================

def log_plugin_action(
    action: str,
    plugin_name: str,
    admin_id: int | None = None,
    tenant_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    记录插件操作审计日志（异步写入 operation_logs 表）

    Args:
        action: 操作类型（install/uninstall/enable/disable/configure/upgrade）
        plugin_name: 插件名称
        admin_id: 操作管理员 ID
        tenant_id: 租户 ID（租户级操作时）
        details: 额外详情
    """
    from app.services.system.operation_log_service import create_log_async

    user_type = "system"
    if admin_id and tenant_id:
        user_type = "tenant_admin"
    elif admin_id:
        user_type = "admin"

    create_log_async(
        tenant_id=tenant_id,
        user_type=user_type,
        user_id=admin_id,
        username=None,
        module="plugin",
        action=action,
        resource=f"plugin:{action}",
        method="SYSTEM",
        path=f"/plugins/{plugin_name}",
        request_body=details,
        status_code=200,
        response_code=0,
        response_message=None,
    )

    logger.info(
        "Plugin audit: action=%s plugin=%s admin_id=%s tenant_id=%s",
        action, plugin_name, admin_id, tenant_id,
    )


# ========================================
# pip install 包白名单
# ========================================

# 允许自动安装的 Python 包（小写规范化）
# 超出白名单的包需管理员手动审批后添加
ALLOWED_PACKAGES: frozenset[str] = frozenset({
    # HTTP / 网络
    "requests", "httpx", "aiohttp", "urllib3", "certifi",
    # 数据解析
    "beautifulsoup4", "bs4", "lxml", "html5lib",
    "pyyaml", "toml", "tomli", "tomli-w",
    # 数据处理
    "pandas", "numpy", "openpyxl", "xlsxwriter",
    "tabulate", "python-dateutil", "pytz",
    # 文本处理
    "markdown", "markupsafe", "jinja2",
    "chardet", "charset-normalizer",
    # 类型 / 校验
    "pydantic", "pydantic-settings",
    "typing-extensions",
    # 加密 / 编码
    "cryptography", "pyjwt", "python-jose",
    "hashlib", "base64",
    # 图片处理
    "pillow",
    # 工具库
    "tenacity", "cachetools", "python-dotenv",
    "click", "rich", "tqdm",
    # AI / ML（常用客户端）
    "openai", "anthropic", "tiktoken",
    "langchain-core", "langchain-community",
    # 存储客户端
    "boto3", "botocore", "minio",
    "redis", "aioredis",
    # 邮件
    "python-multipart",
    # JSON
    "orjson", "ujson", "simplejson",
})

# 包名正则：仅允许合法的 PyPI 包名字符
_PACKAGE_NAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$")


def _parse_package_name(requirement_line: str) -> str:
    """从 requirements.txt 行中提取包名

    Examples:
        "requests>=2.28.0" → "requests"
        "pydantic[email]~=2.0" → "pydantic"
        "beautifulsoup4==4.12" → "beautifulsoup4"
    """
    # 移除 extras (如 [email])
    line = requirement_line.strip()
    bracket_idx = line.find("[")
    if bracket_idx > 0:
        line = line[:bracket_idx] + line[line.find("]") + 1:]

    # 移除版本约束
    for sep in (">=", "<=", "~=", "==", "!=", ">", "<", ";"):
        idx = line.find(sep)
        if idx > 0:
            line = line[:idx]

    return line.strip().lower()


def validate_requirements(deps: list[str]) -> tuple[list[str], list[str]]:
    """校验依赖包是否在白名单中

    Args:
        deps: requirements.txt 中的依赖行列表

    Returns:
        (allowed, rejected): 允许安装的依赖行列表, 被拒绝的包名列表
    """
    allowed: list[str] = []
    rejected: list[str] = []

    for dep in deps:
        pkg_name = _parse_package_name(dep)
        if not pkg_name:
            continue

        if not _PACKAGE_NAME_RE.match(pkg_name):
            rejected.append(pkg_name)
            continue

        if pkg_name in ALLOWED_PACKAGES:
            allowed.append(dep)
        else:
            rejected.append(pkg_name)

    return allowed, rejected


__all__ = [
    "VALID_PERMISSIONS",
    "ALLOWED_PACKAGES",
    "validate_manifest",
    "validate_manifest_or_raise",
    "validate_requirements",
    "build_permission_aware_context_kwargs",
    "encrypt_sensitive_config",
    "decrypt_sensitive_config",
    "mask_sensitive_config",
    "log_plugin_action",
]
