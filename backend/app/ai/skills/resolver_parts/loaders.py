from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.skills.plugin_identity import plugin_skill_lookup_name
from app.ai.skills.resolution_contracts import (
    append_skill_resolve_issue,
    make_skill_resolve_issue,
)
from app.ai.text_semantics import extract_double_brace_placeholders
from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.logging import LogManager
from app.enums.agent import SkillTypeEnum, ToolTypeEnum
from app.plugins.preview import resolve_i18n

logger = LogManager.get_logger("ai.skill.resolver")


async def load_source_plugins(
    *,
    db: Any,
    skills: list[Any],
) -> dict[int, str]:
    if not db or not skills:
        return {}

    package_ids = list({s.package_id for s in skills if s.package_id})
    if not package_ids:
        return {}

    from sqlalchemy import select

    from app.models.ai.skill_package import SkillPackage

    stmt = select(
        SkillPackage.id,
        SkillPackage.source_plugin,
    ).where(
        SkillPackage.id.in_(package_ids),
        SkillPackage.source_plugin.isnot(None),
    )
    rows = await db.execute(stmt)
    return {row.id: row.source_plugin for row in rows}


def _normalize_preview_names(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _manifest_skill_candidate_names(entry: dict[str, Any]) -> list[str]:
    display_name = entry.get("display_name")
    candidates: list[Any] = [entry.get("name")]
    if isinstance(display_name, dict):
        candidates.extend(display_name.values())
        candidates.append(resolve_i18n(display_name))
    elif display_name:
        candidates.append(display_name)
    return _normalize_preview_names(candidates)


async def load_plugin_skill_startup_previews(
    *,
    db: Any,
    source_plugins: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not db or not source_plugins:
        return {}

    from sqlalchemy import select

    from app.models.system.plugin import Plugin

    stmt = select(Plugin.name, Plugin.manifest).where(
        Plugin.name.in_(list(dict.fromkeys(source_plugins))),
        Plugin.is_deleted.is_(False),
    )
    rows = await db.execute(stmt)

    previews: dict[str, list[dict[str, Any]]] = {}
    for plugin_name, manifest in rows.all():
        if not isinstance(manifest, dict):
            continue
        extensions = manifest.get("extensions")
        if not isinstance(extensions, dict):
            continue
        skills = extensions.get("skills")
        if not isinstance(skills, list):
            continue

        plugin_previews: list[dict[str, Any]] = []
        for item in skills:
            if not isinstance(item, dict):
                continue
            plugin_previews.append(
                {
                    "name": str(item.get("name") or "").strip(),
                    "candidate_names": _manifest_skill_candidate_names(item),
                    "type": str(item.get("type") or "").strip(),
                    "entry_point": str(item.get("entry_point") or "").strip(),
                    "description": resolve_i18n(item.get("description") or {}),
                    "preview_tool_names": _normalize_preview_names(
                        list(item.get("preview_tool_names") or [])
                    ),
                    "preview_semantic_families": _normalize_preview_names(
                        list(item.get("preview_semantic_families") or [])
                    ),
                }
            )
        if plugin_previews:
            previews[str(plugin_name or "").strip()] = plugin_previews

    return previews


def resolve_toolkit_skill(
    *,
    skill: Any,
    config: dict[str, Any],
    result: Any,
) -> None:
    toolkit_content = getattr(skill, "toolkit_content", None) or ""
    if not toolkit_content:
        append_skill_resolve_issue(
            result,
            make_skill_resolve_issue(
                skill=skill,
                code="toolkit_content_missing",
                message=(
                    f"Skill '{getattr(skill, 'name', '')}' "
                    f"(id={getattr(skill, 'id', None)}) has no toolkit_content"
                ),
                severity="error",
            ),
        )
        logger.warning(
            "Toolkit skill {} ({}) has no toolkit_content",
            skill.id,
            skill.name,
        )
        return

    from app.ai.skills.toolkit_parser import (
        parse_toolkit,
        toolkit_tools_to_definitions,
    )

    meta = parse_toolkit(toolkit_content)
    tool_defs = toolkit_tools_to_definitions(meta)
    valves_config = config.get("valves", {})

    for td in tool_defs:
        td.tool_type = ToolTypeEnum.TOOLKIT.value
        td.config = {
            "_toolkit_content": toolkit_content,
            "_toolkit_method": td.name,
            "_toolkit_is_async": td.config.get("is_async", True),
            "_valves_config": valves_config,
            "_toolkit_trusted": bool(getattr(skill, "is_system", False)),
        }
        td.enabled = True
        td.timeout = skill.timeout
        td.source_skill_id = skill.id
        td.source_skill_name = skill.name
        td.source_skill_type = skill.type
        result.tools.append(td)

    logger.debug(
        "Toolkit skill '{}' resolved {} tools",
        skill.name,
        len(tool_defs),
    )


def resolve_http_skill(
    *,
    skill: Any,
    config: dict[str, Any],
    result: Any,
) -> None:
    url = config.get("url", "")
    if not url:
        logger.warning(
            "HTTP skill {} ({}) has no URL configured",
            skill.id,
            skill.name,
        )
        return

    method = (config.get("method", "GET") or "GET").upper()
    body_template = config.get("body_template", "")
    response_path = config.get("response_path", "")
    template_vars = extract_double_brace_placeholders(body_template)
    url_vars = extract_double_brace_placeholders(url)
    query_params = config.get("query_params", {}) or {}
    qp_vars = []
    for value in query_params.values():
        if isinstance(value, str):
            qp_vars.extend(extract_double_brace_placeholders(value))

    all_vars = list(dict.fromkeys(url_vars + template_vars + qp_vars))
    params: list[ToolParameter] = [
        ToolParameter(
            name=var_name,
            type="string",
            description=f"Value for {{{{{var_name}}}}}",
            required=True,
        )
        for var_name in all_vars
    ]
    if not params and method in ("POST", "PUT", "PATCH"):
        params.append(
            ToolParameter(
                name="input",
                type="string",
                description="Request body or input data",
                required=True,
            )
        )

    description = skill.description or f"Call {method} {url}"
    result.tools.append(
        ToolDefinition(
            name=skill.name.lower().replace(" ", "_"),
            description=description,
            tool_type=ToolTypeEnum.HTTP.value,
            parameters=params,
            config={
                "_http_url": url,
                "_http_method": method,
                "_http_headers": config.get("headers", {}),
                "_http_body_template": body_template,
                "_http_query_params": query_params,
                "_http_auth_type": config.get("auth_type", "none"),
                "_http_auth_config": config.get("auth_config", {}),
                "_http_response_path": response_path,
            },
            enabled=True,
            timeout=config.get("timeout", skill.timeout),
            source_skill_id=skill.id,
            source_skill_name=skill.name,
            source_skill_type=skill.type,
        )
    )


def resolve_email_skill(
    *,
    skill: Any,
    config: dict[str, Any],
    result: Any,
) -> None:
    max_recipients = config.get("max_recipients", 5)
    allow_cc = config.get("allow_cc", True)
    description = render_prompt_contract(
        "email_tool_description",
        max_recipients=max_recipients,
    )
    if skill.description:
        description = skill.description

    params: list[ToolParameter] = [
        ToolParameter(
            name="to",
            type="string",
            description="Recipient email address(es), comma-separated for multiple",
            required=True,
        ),
        ToolParameter(
            name="subject",
            type="string",
            description="Email subject line",
            required=True,
        ),
        ToolParameter(
            name="body",
            type="string",
            description="Email body content (supports HTML)",
            required=True,
        ),
    ]

    if allow_cc:
        params.append(
            ToolParameter(
                name="cc",
                type="string",
                description="CC email address(es), comma-separated (optional)",
                required=False,
            )
        )

    result.tools.append(
        ToolDefinition(
            name="send_email",
            description=description,
            tool_type=ToolTypeEnum.EMAIL.value,
            parameters=params,
            config={
                "_email_subject_prefix": config.get("subject_prefix", ""),
                "_email_allowed_domains": config.get("allowed_domains", []),
                "_email_max_recipients": max_recipients,
                "_email_require_confirmation": config.get("require_confirmation", True),
                "_email_allow_cc": allow_cc,
                "_email_allow_attachments": config.get("allow_attachments", False),
            },
            enabled=True,
            timeout=config.get("timeout", skill.timeout),
            source_skill_id=skill.id,
            source_skill_name=skill.name,
            source_skill_type=skill.type,
        )
    )


def resolve_code_execution_skill(
    *,
    skill: Any,
    config: dict[str, Any],
    result: Any,
) -> None:
    language = config.get("language", "python")
    allowed_modules = config.get(
        "allowed_modules",
        [
            "math",
            "json",
            "datetime",
            "re",
            "collections",
            "itertools",
            "functools",
            "statistics",
            "decimal",
            "fractions",
            "random",
            "string",
            "textwrap",
        ],
    )

    description = render_prompt_contract(
        "execute_code_tool_description",
        language=language,
        allowed_modules=", ".join(allowed_modules[:10]),
    )
    if skill.description:
        description = skill.description

    result.tools.append(
        ToolDefinition(
            name="execute_code",
            description=description,
            tool_type=ToolTypeEnum.CODE_EXECUTION.value,
            parameters=[
                ToolParameter(
                    name="code",
                    type="string",
                    description=f"The {language} code to execute. Must use print() to output results.",
                    required=True,
                ),
            ],
            config={
                "_code_language": language,
                "_code_timeout": config.get("timeout", skill.timeout),
                "_code_memory_limit_mb": config.get("memory_limit_mb", 256),
                "_code_allowed_modules": allowed_modules,
            },
            enabled=True,
            timeout=config.get("timeout", skill.timeout),
            source_skill_id=skill.id,
            source_skill_name=skill.name,
            source_skill_type=skill.type,
        )
    )


async def resolve_plugin_skill(
    *,
    skill: Any,
    config: dict[str, Any],
    result: Any,
    source_plugin: str = "",
) -> bool:
    from app.plugins.registry import ExtensionRegistry

    registry = ExtensionRegistry.get_instance()
    skill_lookup_name = plugin_skill_lookup_name(skill, source_plugin)
    if not skill_lookup_name:
        append_skill_resolve_issue(
            result,
            make_skill_resolve_issue(
                skill=skill,
                code="plugin_skill_identity_missing",
                message=(
                    f"Plugin '{source_plugin}' skill "
                    f"'{getattr(skill, 'name', '')}' "
                    "has no stable source_ref/key identity"
                ),
                severity="error",
                source_plugin=source_plugin,
            ),
        )
        logger.warning(
            "Plugin skill identity missing for plugin '{}' (skill={}, type={})",
            source_plugin,
            skill.id,
            skill.type,
        )
        return True

    resolver_func = registry.get_plugin_skill_resolver(
        source_plugin,
        skill_lookup_name,
    )
    if resolver_func is None:
        append_skill_resolve_issue(
            result,
            make_skill_resolve_issue(
                skill=skill,
                code="plugin_resolver_missing",
                message=(
                    f"Plugin '{source_plugin}' resolver is unavailable for "
                    f"skill '{getattr(skill, 'name', '')}' "
                    f"(id={getattr(skill, 'id', None)})"
                ),
                severity="error",
                source_plugin=source_plugin,
            ),
        )
        logger.warning(
            "No plugin resolver for plugin '{}' (skill={}, type={}); plugin-owned skill is unavailable",
            source_plugin,
            skill.id,
            skill.type,
        )
        return True

    try:
        tool_defs = (
            await resolver_func(skill, config)
            if asyncio.iscoroutinefunction(resolver_func)
            else resolver_func(skill, config)
        )
        if not isinstance(tool_defs, list):
            append_skill_resolve_issue(
                result,
                make_skill_resolve_issue(
                    skill=skill,
                    code="plugin_resolver_invalid_result",
                    message=(
                        f"Plugin '{source_plugin}' resolver returned "
                        f"{type(tool_defs).__name__} for skill "
                        f"'{getattr(skill, 'name', '')}'"
                    ),
                    severity="error",
                    source_plugin=source_plugin,
                ),
            )
            return True

        if not tool_defs:
            append_skill_resolve_issue(
                result,
                make_skill_resolve_issue(
                    skill=skill,
                    code="plugin_resolver_returned_no_tools",
                    message=(
                        f"Plugin '{source_plugin}' resolver returned no tools "
                        f"for skill '{getattr(skill, 'name', '')}'"
                    ),
                    severity="error",
                    source_plugin=source_plugin,
                ),
            )
            return True

        for td in tool_defs:
            td.config = {
                **dict(getattr(td, "config", {}) or {}),
                "plugin_skill_name": skill_lookup_name,
            }
            td.source_skill_id = skill.id
            td.source_skill_name = skill.name
            td.source_skill_type = skill.type
            td.source_plugin = source_plugin
            result.tools.append(td)
        logger.info(
            "Plugin '{}' skill '{}' resolved {} tools",
            source_plugin,
            skill.name,
            len(tool_defs),
        )
    except Exception as exc:
        append_skill_resolve_issue(
            result,
            make_skill_resolve_issue(
                skill=skill,
                code="plugin_resolver_failed",
                message=(
                    f"Plugin '{source_plugin}' resolver failed for skill "
                    f"'{getattr(skill, 'name', '')}': {exc}"
                ),
                severity="error",
                source_plugin=source_plugin,
            ),
        )
        logger.error(
            "Plugin skill resolver failed for '{}' (plugin={}): {}",
            skill.name,
            source_plugin,
            exc,
        )
    return True


async def resolve_one_skill(
    *,
    skill: Any,
    config: dict[str, Any],
    result: Any,
    source_plugin: str | None,
    resolve_toolkit: Callable[..., None],
    resolve_builtin: Callable[..., None],
    resolve_http: Callable[..., None],
    resolve_email: Callable[..., None],
    resolve_code_execution: Callable[..., None],
    resolve_plugin: Callable[..., Any],
) -> None:
    if config.get("internal"):
        return
    normalized_source_plugin = str(source_plugin or "").strip()
    fallback_start_index = len(result.tools)

    if normalized_source_plugin:
        plugin_owned = await resolve_plugin(
            skill=skill,
            config=config,
            result=result,
            source_plugin=normalized_source_plugin,
        )
        if plugin_owned:
            return

    skill_type = skill.type
    if skill_type == SkillTypeEnum.TOOLKIT.value:
        resolve_toolkit(skill=skill, config=config, result=result)
    elif skill_type == SkillTypeEnum.BUILTIN.value:
        resolve_builtin(skill=skill, config=config, result=result)
    elif skill_type == SkillTypeEnum.HTTP.value:
        resolve_http(skill=skill, config=config, result=result)
    elif skill_type == SkillTypeEnum.EMAIL.value:
        resolve_email(skill=skill, config=config, result=result)
    elif skill_type == SkillTypeEnum.CODE_EXECUTION.value:
        resolve_code_execution(skill=skill, config=config, result=result)
    else:
        logger.warning(
            "Unknown skill type: {} (skill={}), no resolver available",
            skill_type,
            skill.id,
        )
        return

    if normalized_source_plugin:
        for tool in result.tools[fallback_start_index:]:
            if not getattr(tool, "source_plugin", None):
                tool.source_plugin = normalized_source_plugin
