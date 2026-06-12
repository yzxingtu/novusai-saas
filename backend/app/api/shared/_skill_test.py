"""
Skill 测试执行器 / Skill test executor.

按 Skill 类型执行不同的测试逻辑，验证 Skill 配置是否正确。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.enums.agent import SkillTypeEnum
from app.models.ai.skill import Skill

logger = LogManager.get_logger("ai.skill.test")


async def test_skill(db: AsyncSession, skill: Skill) -> dict[str, Any]:
    """
    执行技能测试 / Execute skill test

    Args:
        db: 数据库会话 / Database session
        skill: 技能模型实例 / Skill model instance

    Returns:
        测试结果字典 / Test result dictionary
        {"success": bool, "message": str, "details": dict | None}
    """
    skill_type = skill.type
    config = skill.config or {}

    try:
        if skill_type == SkillTypeEnum.TOOLKIT.value:
            return await _test_toolkit(db, skill)
        elif skill_type == SkillTypeEnum.BUILTIN.value:
            return _test_builtin(skill, config)
        elif skill_type == SkillTypeEnum.HTTP.value:
            return await _test_http(skill, config)
        elif skill_type == SkillTypeEnum.EMAIL.value:
            return await _test_email(db, config)
        elif skill_type == SkillTypeEnum.CODE_EXECUTION.value:
            return _test_code_execution(config)
        else:
            return {
                "success": False,
                "message": _("skill.test.unknown_type", type=skill_type),
                "details": None,
            }
    except Exception as exc:
        logger.warning(
            "Skill test failed: skill={} type={} error={}",
            skill.id,
            skill_type,
            str(exc),
        )
        return {
            "success": False,
            "message": build_public_error_text(
                exc=exc,
                message=_("common.server_error"),
            ),
            "details": None,
        }


def _test_builtin(
    skill: Skill,
    config: dict[str, Any],
) -> dict[str, Any]:
    """测试 Builtin Skill：验证内置功能标识 / Test Builtin skill: validate built-in function identifier"""
    # 代码定义型 builtin：internal_ops 元工具 / Code-defined builtin: internal_ops meta-tools
    builtin_type = str(config.get("builtin_type") or "").strip()
    if builtin_type == "internal_ops":
        try:
            from app.ai.internal_ops.tools import (
                TOOL_DESCRIBE_OPERATION,
                TOOL_INVOKE_OPERATION,
                TOOL_LIST_OPERATIONS,
                build_internal_ops_tool_definitions,
            )

            tools = build_internal_ops_tool_definitions(skill=skill, config=config)
            tool_names = [t.name for t in tools]
            expected = [
                TOOL_LIST_OPERATIONS,
                TOOL_DESCRIBE_OPERATION,
                TOOL_INVOKE_OPERATION,
            ]
            missing = [n for n in expected if n not in tool_names]
            if missing:
                return {
                    "success": False,
                    "message": _(
                        "skill.test.internal_ops_missing_tools",
                        missing=", ".join(missing),
                    ),
                    "details": {"tool_names": tool_names, "missing": missing},
                }
            return {
                "success": True,
                "message": _(
                    "skill.test.internal_ops_ok",
                    tools=len(tools),
                ),
                "details": {
                    "builtin_type": builtin_type,
                    "tool_names": tool_names,
                    "tool_count": len(tools),
                },
            }
        except Exception as exc:
            return {
                "success": False,
                "message": _(
                    "skill.test.internal_ops_error",
                    error=str(exc),
                ),
                "details": None,
            }

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
    db: AsyncSession,
    skill: Skill,
) -> dict[str, Any]:
    """测试 Toolkit Skill：验证源码可解析 + 安全扫描 + Tools 类有效 / Test Toolkit skill: validate source code parsing + security scanning + Tools class validity"""
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
                "message": _("skill.test.toolkit_invalid", errors="; ".join(errors)),
                "details": {"validation_errors": errors},
            }

        # 安全扫描（非系统技能） / Security scanning (non-system skills)
        security_warnings: list[str] = []
        if not skill.is_system:
            from app.ai.tools.executors.toolkit_executor import _scan_toolkit_security
            from app.configs.service import ConfigService

            cfg = ConfigService(db)
            security_level = await cfg.get_platform_config(
                "toolkit_security_level",
                default="normal",
            )
            violations = _scan_toolkit_security(toolkit_content, str(security_level))
            if violations:
                security_warnings = violations

        meta = parse_toolkit(toolkit_content)

        details: dict[str, Any] = {
            "title": meta.title,
            "version": meta.version,
            "tools_count": len(meta.tools),
            "tool_names": [t.name for t in meta.tools],
            "has_valves": bool(meta.valves_schema),
        }
        if security_warnings:
            details["security_warnings"] = security_warnings

        return {
            "success": len(security_warnings) == 0,
            "message": (
                _("skill.test.toolkit_security_warn", count=len(security_warnings))
                if security_warnings
                else _(
                    "skill.test.toolkit_ok",
                    tools=len(meta.tools),
                    valves=bool(meta.valves_schema),
                )
            ),
            "details": details,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": _(
                "skill.test.toolkit_error",
                error=build_public_error_text(
                    exc=exc,
                    message=_("common.server_error"),
                ),
            ),
            "details": None,
        }


async def _test_http(
    skill: Skill,
    config: dict[str, Any],
) -> dict[str, Any]:
    """测试 HTTP Skill：验证 URL 可达性 / Test HTTP skill: validate URL reachability"""
    url = config.get("url", "")
    if not url:
        return {
            "success": False,
            "message": _("skill.test.http_no_url"),
            "details": None,
        }

    method = (config.get("method", "GET") or "GET").upper()

    try:
        import httpx

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.request(
                method="HEAD" if method == "GET" else method, url=url
            )
            return {
                "success": resp.status_code < 500,
                "message": _(
                    "skill.test.http_ok", status=resp.status_code, method=method
                ),
                "details": {
                    "url": url,
                    "method": method,
                    "status_code": resp.status_code,
                    "auth_type": config.get("auth_type", "none"),
                    "has_body_template": bool(config.get("body_template")),
                },
            }
    except Exception as exc:
        return {
            "success": False,
            "message": _(
                "skill.test.http_error",
                error=build_public_error_text(
                    exc=exc,
                    message=_("common.server_error"),
                ),
            ),
            "details": {"url": url, "method": method},
        }


async def _test_email(
    db: AsyncSession,
    config: dict[str, Any],
) -> dict[str, Any]:
    """测试 Email Skill：检查 SMTP 配置可用性 / Test Email Skill: check SMTP config availability."""
    try:
        from app.services.common.email_service import EmailService

        service = EmailService(db)
        smtp_config = await service._load_smtp_config()

        issues: list[str] = []
        if not smtp_config.enabled:
            issues.append("email_disabled")
        if not smtp_config.host:
            issues.append("smtp_host_missing")
        if not smtp_config.from_address:
            issues.append("from_address_missing")

        if issues:
            return {
                "success": False,
                "message": _(
                    "skill.test.email_config_issues", issues=", ".join(issues)
                ),
                "details": {
                    "enabled": smtp_config.enabled,
                    "host": smtp_config.host or "(not set)",
                    "from_address": smtp_config.from_address or "(not set)",
                    "issues": issues,
                },
            }

        allowed_domains = config.get("allowed_domains", [])
        max_recipients = config.get("max_recipients", 5)

        return {
            "success": True,
            "message": _("skill.test.email_ok"),
            "details": {
                "smtp_host": smtp_config.host,
                "from_address": smtp_config.from_address,
                "encryption": smtp_config.encryption,
                "allowed_domains": allowed_domains or "(all)",
                "max_recipients": max_recipients,
            },
        }
    except Exception as exc:
        return {
            "success": False,
            "message": _(
                "skill.test.email_error",
                error=build_public_error_text(
                    exc=exc,
                    message=_("common.server_error"),
                ),
            ),
            "details": None,
        }


def _test_code_execution(
    config: dict[str, Any],
) -> dict[str, Any]:
    """测试 Code Execution Skill：验证配置合理性 / Test Code Execution Skill: validate config."""
    language = config.get("language", "python")
    if language != "python":
        return {
            "success": False,
            "message": _("skill.test.code_unsupported_lang", lang=language),
            "details": None,
        }

    allowed_modules = config.get("allowed_modules", [])
    timeout = config.get("timeout", 30)
    memory_limit = config.get("memory_limit_mb", 256)

    return {
        "success": True,
        "message": _(
            "skill.test.code_ok", modules=len(allowed_modules), timeout=timeout
        ),
        "details": {
            "language": language,
            "timeout": timeout,
            "memory_limit_mb": memory_limit,
            "allowed_modules": allowed_modules,
        },
    }


__all__ = ["test_skill"]
