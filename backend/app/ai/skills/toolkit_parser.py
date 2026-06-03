"""
Toolkit Parser
Toolkit 解析器

Parses Toolkit Python files, extracting:
解析 Toolkit Python 文件，提取：
- Module docstring metadata (title / description / version / author / requirements)
  模块 docstring 元数据
- Tools class public methods → ToolDefinition list
  Tools 类的公开方法 → ToolDefinition 列表
- Valves(BaseModel) JSON Schema → for frontend dynamic config form rendering
  Valves(BaseModel) 的 JSON Schema → 供前端动态渲染配置表单

Based on Open WebUI's Workspace Tools design:
one Python file defines a Tools class, each public method automatically becomes a Tool.
参考 Open WebUI 的 Workspace Tools 设计：
一个 Python 文件定义 Tools 类，每个公开方法自动成为一个 Tool。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

from app.ai.skills import toolkit_parser_helpers as helpers
from app.ai.tools.types import ToolParameter
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.skill.toolkit")

# --------------------------------------------------------------------------- #
# Data Structures / 数据结构
# --------------------------------------------------------------------------- #


@dataclass
class ToolkitToolMeta:
    """Metadata for a single Tool method / 单个 Tool 方法的元数据"""

    name: str
    description: str = ""
    parameters: list[dict[str, Any]] = field(default_factory=list)
    is_async: bool = False


@dataclass
class ToolkitMeta:
    """Toolkit metadata / Toolkit 元数据"""

    title: str = ""
    description: str = ""
    version: str = "0.0.0"
    author: str = ""
    requirements: list[str] = field(default_factory=list)
    tools: list[ToolkitToolMeta] = field(default_factory=list)
    valves_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to storable dict (for toolkit_meta JSON field). / 序列化为可存储的 dict（用于 toolkit_meta JSON 字段）。"""
        return {
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "requirements": self.requirements,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                    "is_async": t.is_async,
                }
                for t in self.tools
            ],
            "valves_schema": self.valves_schema,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolkitMeta:
        """Deserialize from dict. / 从 dict 反序列化。"""
        tools = [
            ToolkitToolMeta(
                name=t["name"],
                description=t.get("description", ""),
                parameters=t.get("parameters", []),
                is_async=t.get("is_async", False),
            )
            for t in data.get("tools", [])
        ]
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            version=data.get("version", "0.0.0"),
            author=data.get("author", ""),
            requirements=data.get("requirements", []),
            tools=tools,
            valves_schema=data.get("valves_schema", {}),
        )


class ToolkitParseError(Exception):
    """Toolkit parse error / Toolkit 解析错误"""


# --------------------------------------------------------------------------- #
# Core Parse Functions / 核心解析函数
# --------------------------------------------------------------------------- #


def parse_toolkit(source: str) -> ToolkitMeta:
    """
    Parse Toolkit Python source, extract metadata, Tools methods, and Valves schema.
    解析 Toolkit Python 源码，提取元数据、Tools 方法、Valves schema。

    Args:
        source: Complete source code string of the Toolkit Python file /
                Toolkit Python 文件的完整源码字符串

    Returns:
        ToolkitMeta parse result / ToolkitMeta 解析结果

    Raises:
        ToolkitParseError: Parse failure (syntax error, missing Tools class, etc.) /
        解析失败（语法错误、缺少 Tools 类等）
    """
    if not source or not source.strip():
        raise ToolkitParseError(_("toolkit.error.source_empty"))

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ToolkitParseError(
            _("toolkit.error.syntax_error").format(line=exc.lineno, msg=exc.msg)
        ) from exc

    meta_values = helpers.parse_module_docstring(tree)
    meta = ToolkitMeta(**meta_values)

    tools_class = helpers.find_class(tree, "Tools")
    if tools_class is None:
        raise ToolkitParseError(_("toolkit.error.missing_tools_class"))

    tool_meta_items = helpers.extract_tools_method_meta(tools_class, source)
    meta.tools = [
        ToolkitToolMeta(
            name=item["name"],
            description=item.get("description", ""),
            parameters=item.get("parameters", []),
            is_async=item.get("is_async", False),
        )
        for item in tool_meta_items
    ]

    if not meta.tools:
        logger.warning("Toolkit '{}' has no public methods in Tools class", meta.title)

    valves_class = helpers.find_class(tree, "Valves")
    if valves_class is not None:
        meta.valves_schema = helpers.extract_valves_schema(valves_class, source)

    logger.info(
        "Toolkit parsed: '{}' v{} — {} tools, valves={}",
        meta.title,
        meta.version,
        len(meta.tools),
        bool(meta.valves_schema),
    )
    return meta


def toolkit_tools_to_definitions(
    meta: ToolkitMeta,
    *,
    skill_id: int | None = None,
    skill_name: str | None = None,
    toolkit_content: str = "",
    valves_config: dict[str, Any] | None = None,
    timeout: int = 30,
) -> list[ToolParameter]:
    """
    Convert tools from ToolkitMeta to ToolDefinition list. / 将 ToolkitMeta 中的 tools 转换为 ToolDefinition 列表。

    Note: This function returns a ToolParameter list. The ToolDefinition construction
    is done by SkillResolver._resolve_toolkit (which injects config, etc.).
    注意：此函数返回的是 ToolParameter 列表，ToolDefinition 的构建
    由 SkillResolver._resolve_toolkit 完成（需要注入 config 等）。

    This function is provided for convenience only.
    此函数仅供便捷调用。
    """
    from app.ai.tools.types import ToolDefinition

    definitions: list[ToolDefinition] = []
    for tool_meta in meta.tools:
        params = [
            ToolParameter(
                name=p["name"],
                type=p.get("type", "string"),
                description=p.get("description", ""),
                required=p.get("required", False),
                default=p.get("default"),
            )
            for p in tool_meta.parameters
        ]
        definitions.append(
            ToolDefinition(
                name=tool_meta.name,
                description=tool_meta.description,
                tool_type="toolkit",
                parameters=params,
                config={
                    "_toolkit_content": toolkit_content,
                    "_toolkit_method": tool_meta.name,
                    "_toolkit_is_async": tool_meta.is_async,
                    "_valves_config": valves_config or {},
                },
                timeout=timeout,
                source_skill_id=skill_id,
                source_skill_name=skill_name,
                source_skill_type="toolkit",
            )
        )
    return definitions


# --------------------------------------------------------------------------- #
# Convenience Functions / 便捷函数
# --------------------------------------------------------------------------- #


def validate_toolkit_source(source: str) -> list[str]:
    """
    Validate Toolkit source code legality, return error list (empty = passed).
    校验 Toolkit 源码的合法性，返回错误列表（空列表表示通过）。

    Args:
        source: Toolkit Python source code / Toolkit Python 源码

    Returns:
        Error list / 错误列表
    """
    errors: list[str] = []

    if not source or not source.strip():
        errors.append(_("toolkit.error.source_empty"))
        return errors

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        errors.append(
            _("toolkit.error.syntax_error").format(line=exc.lineno, msg=exc.msg)
        )
        return errors

    tools_class = helpers.find_class(tree, "Tools")
    if tools_class is None:
        errors.append(_("toolkit.error.missing_tools_class"))
        return errors

    has_public_method = False
    for node in ast.iter_child_nodes(tools_class):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and not node.name.startswith("_"):
            has_public_method = True
            break

    if not has_public_method:
        errors.append(_("toolkit.error.no_public_methods"))

    warnings = scan_dangerous_patterns(tree)
    errors.extend(warnings)

    return errors


def scan_dangerous_patterns(tree: ast.Module) -> list[str]:
    """
    Scan AST for dangerous patterns, return warning list (non-blocking for uploads).
    扫描 AST 中的危险模式，返回警告列表（不阻断上传）。
    """
    return helpers.scan_dangerous_patterns(tree)


__all__ = [
    "ToolkitMeta",
    "ToolkitToolMeta",
    "ToolkitParseError",
    "parse_toolkit",
    "validate_toolkit_source",
    "toolkit_tools_to_definitions",
]
