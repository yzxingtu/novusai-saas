"""
Skill package summary helpers / 技能包摘要辅助函数

Provide a normalized, non-sensitive payload for admin and tenant package APIs.
为管理端与企业端技能包 API 提供统一、非敏感的摘要载荷。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.ai.skill_package import SkillPackage


def _get_package_value(
    package: Mapping[str, Any] | SkillPackage,
    field: str,
    default: Any = None,
) -> Any:
    """Read a field from either ORM object or dict payload. / 兼容 ORM 与 dict 读取字段。"""
    if isinstance(package, Mapping):
        return package.get(field, default)
    return getattr(package, field, default)


def _is_configured_value(value: Any) -> bool:
    """Determine whether a valves value should count as configured. / 判断配置项是否算作“已配置”。"""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _build_skill_package_summary(
    package: Mapping[str, Any] | SkillPackage,
) -> dict[str, Any]:
    """
    Build normalized info-architecture fields for SkillPackage.
    构建 SkillPackage 的统一信息架构字段。
    """
    source_plugin = _get_package_value(package, "source_plugin")
    tenant_id = _get_package_value(package, "tenant_id")
    is_system = bool(_get_package_value(package, "is_system", False))
    valves_schema = _get_package_value(package, "valves_schema") or {}
    valves_config = _get_package_value(package, "valves_config") or {}

    properties = (
        valves_schema.get("properties", {}) if isinstance(valves_schema, dict) else {}
    )
    if source_plugin:
        package_role_key = "plugin_managed"
        source_summary = f"plugin:{source_plugin}"
    elif tenant_id is not None:
        package_role_key = "tenant_owned"
        source_summary = f"tenant:{tenant_id}"
    elif is_system:
        package_role_key = "platform_system"
        source_summary = "platform:system"
    else:
        package_role_key = "platform_catalog"
        source_summary = "platform:catalog"

    valves_field_count = len(properties)
    if properties:
        configured_valves_count = sum(
            1 for key in properties if _is_configured_value(valves_config.get(key))
        )
    elif isinstance(valves_config, dict):
        configured_valves_count = sum(
            1 for value in valves_config.values() if _is_configured_value(value)
        )
    else:
        configured_valves_count = 0

    return {
        "package_role_key": package_role_key,
        "source_summary": source_summary,
        "runtime_binding_mode": "direct_agent_skill_grant",
        "valves_field_count": valves_field_count,
        "configured_valves_count": configured_valves_count,
    }


def build_skill_package_payload(
    package: Mapping[str, Any] | SkillPackage,
    *,
    include_valves_config: bool = False,
    skill_count: int | None = None,
) -> dict[str, Any]:
    """
    Build a normalized, non-sensitive API payload for SkillPackage.
    构建统一且默认去敏的 SkillPackage API 载荷。
    """
    payload = {
        "id": _get_package_value(package, "id"),
        "tenant_id": _get_package_value(package, "tenant_id"),
        "name": _get_package_value(package, "name"),
        "description": _get_package_value(package, "description"),
        "avatar": _get_package_value(package, "avatar"),
        "is_recommended": bool(_get_package_value(package, "is_recommended", False)),
        "is_system": bool(_get_package_value(package, "is_system", False)),
        "is_active": bool(_get_package_value(package, "is_active", True)),
        "sort_order": _get_package_value(package, "sort_order", 0),
        "source_plugin": _get_package_value(package, "source_plugin"),
        "valves_schema": _get_package_value(package, "valves_schema"),
        "created_at": _get_package_value(package, "created_at"),
        "updated_at": _get_package_value(package, "updated_at"),
        "skill_count": (
            skill_count
            if skill_count is not None
            else _get_package_value(package, "skill_count", 0)
        ),
    }
    if include_valves_config:
        payload["valves_config"] = _get_package_value(package, "valves_config")

    payload.update(_build_skill_package_summary(package))
    return payload


__all__ = [
    "build_skill_package_payload",
]
