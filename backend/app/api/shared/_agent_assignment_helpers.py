"""
智能体功能分配公共辅助函数 / Agent Feature Assignment Shared Helpers

供 admin / tenant 两端 agent_assignments controller 共用。
Shared by admin / tenant agent_assignments controllers.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def build_plugin_feature_i18n_map(db: AsyncSession) -> dict[str, dict]:
    """
    从已安装插件的 manifest 中提取 ai_requirements.features 的多语言 display_name / description，
    Extract i18n display_name / description from installed plugin manifests' ai_requirements.features,
    构建 feature_code → {"display_name": {...}, "description": {...}} 映射。
    build feature_code → {"display_name": {...}, "description": {...}} mapping.
    """
    from app.models.system.plugin import Plugin

    result = await db.execute(
        select(Plugin.name, Plugin.ai_requirements).where(
            Plugin.ai_requirements.isnot(None),
            Plugin.is_deleted.is_(False),
        )
    )
    i18n_map: dict[str, dict] = {}
    for plugin_name, ai_req in result.all():
        if not isinstance(ai_req, dict):
            continue
        features = ai_req.get("features", [])
        if not isinstance(features, list):
            continue
        for feat in features:
            if not isinstance(feat, dict):
                continue
            code = feat.get("feature_code", "")
            full_code = f"plugin.{plugin_name}.{code}" if not code.startswith("plugin.") else code
            i18n_map[full_code] = {
                "display_name": feat.get("display_name", {}),
                "description": feat.get("description", {}),
            }
    return i18n_map


def build_assignment_item(
    assignment,
    global_default=None,
    i18n_map: dict[str, dict] | None = None,
) -> dict:
    """构建绑定列表项（admin / tenant 共用） / Build assignment list item (shared by admin / tenant)

    Args:
        assignment: SystemAgentAssignment 实例 / SystemAgentAssignment instance
        global_default: 可选，全局默认绑定（tenant 端传入以对比覆盖） / Optional, global default binding (tenant passes in for override comparison)
        i18n_map: feature_code → {"display_name": {...}, "description": {...}} 多语言映射 / i18n mapping
    """
    agent_name = None
    agent_avatar = None
    try:
        agent_obj = getattr(assignment, "agent", None)
        # 过滤已软删除的 Agent（selectin 不自动过滤 is_deleted） / Filter soft-deleted agents (selectin doesn't auto-filter is_deleted)
        if agent_obj is not None and not getattr(agent_obj, "is_deleted", False):
            agent_name = agent_obj.name
            agent_avatar = agent_obj.avatar
    except AttributeError:
        pass

    is_override = assignment.tenant_id is not None

    # Resolve global default agent info
    gd_agent_id = None
    gd_agent_name = None
    if global_default:
        gd_agent_id = global_default.agent_id
        try:
            gd_agent_obj = getattr(global_default, "agent", None)
            if gd_agent_obj is not None and not getattr(gd_agent_obj, "is_deleted", False):
                gd_agent_name = gd_agent_obj.name
        except AttributeError:
            pass
    elif not is_override:
        # Non-override item IS the global default
        gd_agent_id = assignment.agent_id
        gd_agent_name = agent_name

    item: dict = {
        "id": assignment.id,
        "feature_code": assignment.feature_code,
        "feature_name": assignment.feature_name,
        "description": assignment.description,
        "agent_id": assignment.agent_id,
        "agent_name": agent_name,
        "agent_avatar": agent_avatar,
        "config": assignment.config,
        "is_active": assignment.is_active,
        "is_override": is_override,
        "global_agent_id": gd_agent_id,
        "global_agent_name": gd_agent_name,
        "created_at": assignment.created_at,
        "updated_at": assignment.updated_at,
    }

    # 注入插件级多语言 display_name / description / Inject plugin-level i18n display_name / description
    if i18n_map:
        i18n = i18n_map.get(assignment.feature_code)
        if i18n:
            item["display_name"] = i18n.get("display_name", {})
            item["description_i18n"] = i18n.get("description", {})

    return item
