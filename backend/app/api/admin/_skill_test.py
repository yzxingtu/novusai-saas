"""
Skill 测试执行器

按 Skill 类型执行不同的测试逻辑，验证 Skill 配置是否正确。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import SkillTypeEnum
from app.models.ai.skill import Skill

logger = LogManager.get_logger("ai.skill.test")


async def test_skill(db: AsyncSession, skill: Skill) -> dict[str, Any]:
    """
    测试 Skill 配置是否正确

    Args:
        db: 数据库会话
        skill: Skill 模型实例

    Returns:
        {"success": bool, "message": str, "details": dict | None}
    """
    skill_type = skill.type
    config = skill.config or {}

    try:
        if skill_type == SkillTypeEnum.KNOWLEDGE_BASE.value:
            return await _test_knowledge_base(db, skill, config)
        elif skill_type == SkillTypeEnum.DATA_INTELLIGENCE.value:
            return await _test_data_intelligence(db, skill, config)
        elif skill_type == SkillTypeEnum.TOOLKIT.value:
            return await _test_toolkit(skill)
        elif skill_type == SkillTypeEnum.BUILTIN.value:
            return _test_builtin(skill, config)
        else:
            return {
                "success": False,
                "message": _("skill.test.unknown_type", type=skill_type),
                "details": None,
            }
    except Exception as exc:
        logger.warning(
            "Skill test failed: skill=%d type=%s error=%s",
            skill.id, skill_type, str(exc),
        )
        return {
            "success": False,
            "message": str(exc),
            "details": None,
        }


async def _test_knowledge_base(
    db: AsyncSession,
    skill: Skill,
    config: dict[str, Any],
) -> dict[str, Any]:
    """测试知识库 Skill：检查知识库是否存在且有文档"""
    kb_ids = config.get("knowledge_base_ids", [])
    if not kb_ids:
        return {
            "success": False,
            "message": _("skill.test.kb_no_ids"),
            "details": None,
        }

    from app.repositories.ai.knowledge_base_repository import AdminKnowledgeBaseRepository
    kb_repo = AdminKnowledgeBaseRepository(db)

    found_kbs = []
    missing_ids = []
    total_docs = 0

    for kb_id in kb_ids:
        kb = await kb_repo.get_by_id(kb_id)
        if kb:
            doc_count = 0
            if hasattr(kb, "document_count"):
                doc_count = kb.document_count or 0
            found_kbs.append({"id": kb.id, "name": kb.name, "documents": doc_count})
            total_docs += doc_count
        else:
            missing_ids.append(kb_id)

    if missing_ids:
        return {
            "success": False,
            "message": _("skill.test.kb_missing", ids=str(missing_ids)),
            "details": {"found": found_kbs, "missing": missing_ids},
        }

    return {
        "success": True,
        "message": _("skill.test.kb_ok", count=len(found_kbs), docs=total_docs),
        "details": {"knowledge_bases": found_kbs},
    }


async def _test_data_intelligence(
    db: AsyncSession,
    skill: Skill,
    config: dict[str, Any],
) -> dict[str, Any]:
    """测试数据智能 Skill：执行 SELECT 1 验证数据库可达"""
    from sqlalchemy import text

    try:
        result = await db.execute(text("SELECT 1"))
        row = result.scalar()
        if row == 1:
            # 检查是否有可用的表策略
            table_count = 0
            try:
                from app.ai.data_intelligence.schema_provider import SchemaProvider
                descs = await SchemaProvider.get_table_descriptions(db)
                table_count = len(descs) if descs else 0
            except Exception:
                pass

            return {
                "success": True,
                "message": _("skill.test.di_ok", tables=table_count),
                "details": {"db_reachable": True, "table_policies": table_count},
            }

        return {
            "success": False,
            "message": _("skill.test.di_fail"),
            "details": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": _("skill.test.di_error", error=str(exc)),
            "details": None,
        }


def _test_builtin(
    skill: Skill,
    config: dict[str, Any],
) -> dict[str, Any]:
    """测试 Builtin Skill：验证内置功能标识"""
    builtin_name = config.get("builtin_name", "") or config.get("name", "")

    if not builtin_name:
        return {
            "success": False,
            "message": _("skill.test.builtin_no_name"),
            "details": None,
        }

    return {
        "success": True,
        "message": _("skill.test.builtin_ok", name=builtin_name),
        "details": {"builtin_name": builtin_name},
    }


async def _test_toolkit(
    skill: Skill,
) -> dict[str, Any]:
    """测试 Toolkit Skill：验证源码可解析且 Tools 类有效"""
    toolkit_content = getattr(skill, "toolkit_content", None) or ""

    if not toolkit_content:
        return {
            "success": False,
            "message": _("skill.test.toolkit_no_content"),
            "details": None,
        }

    try:
        from app.ai.skills.toolkit_parser import parse_toolkit, validate_toolkit_source

        errors = validate_toolkit_source(toolkit_content)
        if errors:
            return {
                "success": False,
                "message": _("skill.test.toolkit_invalid",
                             errors="; ".join(errors)),
                "details": {"validation_errors": errors},
            }

        meta = parse_toolkit(toolkit_content)
        return {
            "success": True,
            "message": _("skill.test.toolkit_ok",
                         tools=len(meta.tools),
                         valves=bool(meta.valves_schema)),
            "details": {
                "title": meta.title,
                "version": meta.version,
                "tools_count": len(meta.tools),
                "tool_names": [t.name for t in meta.tools],
                "has_valves": bool(meta.valves_schema),
            },
        }
    except Exception as exc:
        return {
            "success": False,
            "message": _("skill.test.toolkit_error", error=str(exc)),
            "details": None,
        }


__all__ = ["test_skill"]
