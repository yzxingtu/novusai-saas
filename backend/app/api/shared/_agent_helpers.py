"""
智能体列表项构建共享逻辑

admin/tenant 两端 _build_agent_item 的公共部分提取。
"""

from __future__ import annotations

from typing import Any


def extract_agent_relations(agent: Any) -> tuple[str | None, dict | None, list[dict]]:
    """
    从 ORM Agent 对象中安全提取关联的 model_name、model_capabilities 和 skill_packages。

    Returns:
        (model_name, model_capabilities, skill_packages) 元组
    """
    model_name = None
    model_capabilities: dict | None = None
    try:
        model_obj = getattr(agent, "model", None)
        if model_obj is not None:
            model_name = model_obj.name
            model_capabilities = {
                "supports_vision": getattr(model_obj, "supports_vision", False),
                "max_image_count": getattr(model_obj, "max_image_count", None),
                "max_image_size_mb": getattr(model_obj, "max_image_size_mb", None),
            }
    except AttributeError:
        pass

    skill_packages: list[dict] = []
    try:
        bindings = getattr(agent, "skill_bindings", None)
        if bindings is not None:
            for b in bindings:
                pkg = getattr(b, "package", None)
                if pkg is not None:
                    skill_packages.append({"id": pkg.id, "name": pkg.name})
    except AttributeError:
        pass

    return model_name, model_capabilities, skill_packages


def build_agent_base_item(agent: Any) -> dict[str, Any]:
    """
    构建智能体列表项的公共字段。

    admin/tenant 各自在此基础上追加端特有的字段。
    """
    model_name, model_capabilities, skill_packages = extract_agent_relations(agent)

    result: dict[str, Any] = {
        "id": agent.id,
        "tenant_id": agent.tenant_id,
        "name": agent.name,
        "avatar": agent.avatar,
        "description": agent.description,
        "status": agent.status,
        "scope": agent.scope,
        "execution_mode": agent.execution_mode,
        "is_system": agent.is_system,
        "model_name": model_name,
        "model_capabilities": model_capabilities,
        "skill_packages": skill_packages,
        "published_version": agent.published_version,
        "welcome_message": agent.welcome_message,
        "suggested_questions": agent.suggested_questions,
        "input_variables": agent.input_variables,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }
    return result
