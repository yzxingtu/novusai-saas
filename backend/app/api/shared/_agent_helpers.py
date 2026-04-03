"""
智能体列表项构建共享逻辑 / Agent List Item Build Shared Logic

admin/tenant 两端 _build_agent_item 的公共部分提取。
Common logic extracted from admin/tenant _build_agent_item.
"""

from __future__ import annotations

from typing import Any


def _normalize_input_variables(value: Any) -> list[Any]:
    """
    Normalize persisted input_variables to a list shape.
    将持久化的 input_variables 统一归一化为 list 形态。

    Old/bad historical records may contain `{}` instead of `[]`.
    历史脏数据里可能出现 `{}`，前端按数组消费时会直接报错。
    """
    return value if isinstance(value, list) else []


def _extract_agent_relations(agent: Any) -> tuple[str | None, dict | None, list[dict]]:
    """
    从 ORM Agent 对象中安全提取关联的 model_name、model_capabilities 和 skills。
    Safely extract related model_name, model_capabilities and skills from ORM Agent object.

    Returns:
        (model_name, model_capabilities, skills) 元组 / tuple
    """
    model_name = None
    model_capabilities: dict | None = None
    try:
        model_obj = getattr(agent, "model", None)
        if model_obj is not None:
            model_name = model_obj.name
            model_capabilities = {
                "supports_vision": getattr(model_obj, "supports_vision", False),
                "supports_audio": getattr(model_obj, "supports_audio", False),
                "supports_video": getattr(model_obj, "supports_video", False),
                "max_image_count": getattr(model_obj, "max_image_count", None),
                "max_image_size_mb": getattr(model_obj, "max_image_size_mb", None),
            }
    except AttributeError:
        pass

    skills: list[dict] = []
    try:
        grants = getattr(agent, "skill_grants", None)
        if grants is not None:
            for grant in grants:
                skill = getattr(grant, "skill", None)
                if skill is not None:
                    skills.append({"id": skill.id, "name": skill.name})
    except AttributeError:
        pass

    return model_name, model_capabilities, skills


def build_agent_base_item(agent: Any) -> dict[str, Any]:
    """
    构建智能体列表项的公共字段 / Build common fields for agent list item.

    admin/tenant 各自在此基础上追加端特有的字段。
    admin/tenant each append endpoint-specific fields on top of this.
    """
    model_name, model_capabilities, skills = _extract_agent_relations(agent)

    _otid = getattr(agent, "owner_tenant_id", None)
    # owner_type: 仅列表/详情展示用派生字段（非 ORM 列、非历史 owner_type 列）。
    # owner_type: display-only derived field (not an ORM column; not the removed agents.owner_type).
    _derived_owner_type = "tenant" if _otid is not None else "platform"
    result: dict[str, Any] = {
        "id": agent.id,
        "tenant_id": _otid,
        "owner_tenant_id": _otid,
        "owner_type": _derived_owner_type,
        "scope": getattr(agent, "scope", None),
        "source_plugin": getattr(agent, "source_plugin", None),
        "name": agent.name,
        "avatar": agent.avatar,
        "description": agent.description,
        "status": agent.status,
        "execution_mode": agent.execution_mode,
        "is_system": agent.is_system,
        "model_name": model_name,
        "model_capabilities": model_capabilities,
        "skills": skills,
        "published_version": agent.published_version,
        "welcome_message": agent.welcome_message,
        "suggested_questions": agent.suggested_questions,
        "input_variables": _normalize_input_variables(agent.input_variables),
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }
    return result
