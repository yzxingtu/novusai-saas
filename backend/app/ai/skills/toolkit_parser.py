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
import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.types import ToolParameter
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.skill.toolkit")

# --------------------------------------------------------------------------- #
# Data Structures / 数据结构
# --------------------------------------------------------------------------- #

_FRONTMATTER_RE = re.compile(
    r'^"""(.*?)"""',
    re.DOTALL,
)

_PARAM_DOC_RE = re.compile(
    r":param\s+(\w+)\s*:\s*(.+)",
)

# Python type hint → JSON Schema type mapping / 映射
_TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "List": "array",
    "Dict": "object",
    "Optional": "string",
}


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

    # 1. Parse AST / 解析 AST
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ToolkitParseError(
            _("toolkit.error.syntax_error").format(line=exc.lineno, msg=exc.msg)
        ) from exc

    # 2. Extract module docstring metadata / 提取模块 docstring 元数据
    meta = _parse_module_docstring(tree)

    # 3. Find Tools class / 查找 Tools 类
    tools_class = _find_class(tree, "Tools")
    if tools_class is None:
        raise ToolkitParseError(_("toolkit.error.missing_tools_class"))

    # 4. Extract public methods of Tools class / 提取 Tools 类的公开方法
    meta.tools = _extract_tools_methods(tools_class, source)

    if not meta.tools:
        logger.warning("Toolkit '%s' has no public methods in Tools class", meta.title)

    # 5. Extract Valves schema / 提取 Valves schema
    valves_class = _find_class(tree, "Valves")
    if valves_class is not None:
        meta.valves_schema = _extract_valves_schema(valves_class, source)

    logger.info(
        "Toolkit parsed: '%s' v%s — %d tools, valves=%s",
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
# Internal: Module docstring parsing / 内部：模块 docstring 解析
# --------------------------------------------------------------------------- #


def _parse_module_docstring(tree: ast.Module) -> ToolkitMeta:
    """Extract key: value metadata from module docstring. / 从模块 docstring 提取 key: value 元数据。"""
    meta = ToolkitMeta()
    docstring = ast.get_docstring(tree)
    if not docstring:
        return meta

    for line in docstring.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if not value:
            continue

        if key == "title":
            meta.title = value
        elif key == "description":
            meta.description = value
        elif key == "version":
            meta.version = value
        elif key == "author":
            meta.author = value
        elif key == "requirements":
            meta.requirements = [
                r.strip() for r in value.split(",") if r.strip()
            ]

    return meta


# --------------------------------------------------------------------------- #
# Internal: AST traversal helpers / 内部：AST 遍历辅助
# --------------------------------------------------------------------------- #


def _find_class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    """Find class with specified name at AST top level. / 在 AST 顶层查找指定名称的 class。"""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _extract_tools_methods(
    cls: ast.ClassDef, source: str
) -> list[ToolkitToolMeta]:
    """Extract metadata of all public methods in Tools class. / 提取 Tools 类中所有公开方法的元数据。"""
    methods: list[ToolkitToolMeta] = []

    for node in ast.iter_child_nodes(cls):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Skip private methods and dunder methods / 跳过私有方法和 dunder 方法
        if node.name.startswith("_"):
            continue

        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Extract docstring / 提取 docstring
        docstring = ast.get_docstring(node) or ""
        # Clean docstring: first line as description, extract :param from rest
        # 清理 docstring：第一行作为 description，后面提取 :param
        desc_lines: list[str] = []
        param_docs: dict[str, str] = {}

        for line in docstring.splitlines():
            stripped = line.strip()
            m = _PARAM_DOC_RE.match(stripped)
            if m:
                param_docs[m.group(1)] = m.group(2).strip()
            elif stripped and not stripped.startswith(":return"):
                desc_lines.append(stripped)

        description = " ".join(desc_lines).strip()

        # Extract parameters / 提取参数
        parameters = _extract_method_parameters(node, param_docs)

        methods.append(
            ToolkitToolMeta(
                name=node.name,
                description=description,
                parameters=parameters,
                is_async=is_async,
            )
        )

    return methods


def _extract_method_parameters(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    param_docs: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Extract parameter list from method signature type hints.
    从方法签名的 type hints 提取参数列表。

    Skips 'self' parameter. / 跳过 'self' 参数。
    """
    params: list[dict[str, Any]] = []
    args = func.args

    # Calculate default value offset / 计算默认值的偏移量
    # args.args contains all positional params, args.defaults only corresponds to trailing params with defaults
    # args.args 包含所有 positional 参数，args.defaults 仅对应末尾有默认值的参数
    num_args = len(args.args)
    num_defaults = len(args.defaults)
    default_offset = num_args - num_defaults

    for i, arg in enumerate(args.args):
        if arg.arg == "self":
            continue

        # Type inference / 类型推断
        json_type = "string"
        if arg.annotation:
            json_type = _annotation_to_json_type(arg.annotation)

        # Default value / 默认值
        default_idx = i - default_offset
        has_default = default_idx >= 0
        default_value = None
        if has_default:
            default_value = _ast_value_to_python(args.defaults[default_idx])

        # Required: no default value = required / 是否必填：没有默认值 = 必填
        required = not has_default

        param_info: dict[str, Any] = {
            "name": arg.arg,
            "type": json_type,
            "description": param_docs.get(arg.arg, ""),
            "required": required,
        }
        if default_value is not None:
            param_info["default"] = default_value

        params.append(param_info)

    return params


def _annotation_to_json_type(annotation: ast.expr) -> str:
    """Convert AST type annotation to JSON Schema type. / 将 AST 类型注解转换为 JSON Schema 类型。"""
    if isinstance(annotation, ast.Name):
        return _TYPE_MAP.get(annotation.id, "string")

    if isinstance(annotation, ast.Constant):
        return _TYPE_MAP.get(str(annotation.value), "string")

    # Optional[X] = Union[X, None], List[X], Dict[K, V], Union[X, Y, ...]
    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        outer = annotation.value.id
        if outer == "Optional":
            # Extract inner type / 提取内部类型
            if isinstance(annotation.slice, ast.Name):
                return _TYPE_MAP.get(annotation.slice.id, "string")
            return "string"
        if outer == "Union":
            # Union[X, Y, ...] → take the first non-None type / 取第一个非 None 的类型
            if isinstance(annotation.slice, ast.Tuple):
                for elt in annotation.slice.elts:
                    if isinstance(elt, ast.Constant) and elt.value is None:
                        continue
                    if isinstance(elt, ast.Name) and elt.id == "None":
                        continue
                    return _annotation_to_json_type(elt)
            elif isinstance(annotation.slice, ast.Name):
                return _TYPE_MAP.get(annotation.slice.id, "string")
            return "string"
        if outer in ("list", "List"):
            return "array"
        if outer in ("dict", "Dict"):
            return "object"

    # Union type: take the first non-None type / Union 类型：取第一个非 None 的类型
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        # X | None syntax / X | None 语法
        left_type = _annotation_to_json_type(annotation.left)
        if left_type != "string":
            return left_type
        return _annotation_to_json_type(annotation.right)

    # ast.Attribute (e.g. typing.Optional) / ast.Attribute (如 typing.Optional)
    if isinstance(annotation, ast.Attribute):
        return _TYPE_MAP.get(annotation.attr, "string")

    return "string"


def _ast_value_to_python(node: ast.expr) -> Any:
    """Convert AST default value node to Python value. / 将 AST 默认值节点转换为 Python 值。"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_ast_value_to_python(el) for el in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _ast_value_to_python(k) if k else None: _ast_value_to_python(v)
            for k, v in zip(node.keys, node.values, strict=False)
        }
    if isinstance(node, ast.Name):
        if node.id == "None":
            return None
        if node.id == "True":
            return True
        if node.id == "False":
            return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _ast_value_to_python(node.operand)
        if isinstance(val, (int, float)):
            return -val
    return None


def _extract_literal_values(annotation: ast.expr) -> list[str] | None:
    """
    Extract enum value list from Literal['a', 'b', 'c'] type annotation.
    从 Literal['a', 'b', 'c'] 类型注解提取枚举值列表。

    Returns:
        Literal value list, or None (not a Literal type) /
        字面量值列表，或 None（非 Literal 类型）
    """
    if not isinstance(annotation, ast.Subscript):
        return None
    if not isinstance(annotation.value, ast.Name):
        return None
    if annotation.value.id != "Literal":
        return None

    values: list[str] = []
    # Literal['a', 'b'] → slice is Tuple / slice 是 Tuple
    if isinstance(annotation.slice, ast.Tuple):
        for elt in annotation.slice.elts:
            if isinstance(elt, ast.Constant) and elt.value is not None:
                values.append(str(elt.value))
    # Literal['a'] → slice is a single Constant / slice 是单个 Constant
    elif isinstance(annotation.slice, ast.Constant) and annotation.slice.value is not None:
        values.append(str(annotation.slice.value))

    return values if values else None


# --------------------------------------------------------------------------- #
# Internal: Valves schema extraction / 内部：Valves schema 提取
# --------------------------------------------------------------------------- #


def _extract_valves_schema(
    cls: ast.ClassDef, source: str
) -> dict[str, Any]:
    """
    Extract JSON Schema from Valves(BaseModel) class definition.
    从 Valves(BaseModel) 类定义提取 JSON Schema。

    Supports two approaches / 支持两种方式：
    1. Static AST parsing (from class field type hints and defaults)
       静态 AST 解析（从类字段的 type hints 和默认值）
    2. If parsing fails, return empty dict
       如果解析失败，返回空 dict
    """
    properties: dict[str, Any] = {}
    required_fields: list[str] = []

    for node in ast.iter_child_nodes(cls):
        if not isinstance(node, ast.AnnAssign):
            continue

        # Field name / 字段名
        if not isinstance(node.target, ast.Name):
            continue
        field_name = node.target.id

        # Skip class var / private / 跳过 class var / private
        if field_name.startswith("_"):
            continue

        # Type + Literal enum detection / 类型 + Literal 枚举检测
        json_type = "string"
        enum_values: list[str] | None = None
        if node.annotation:
            json_type = _annotation_to_json_type(node.annotation)
            enum_values = _extract_literal_values(node.annotation)

        prop: dict[str, Any] = {"type": json_type}
        if enum_values:
            prop["enum"] = enum_values

        # Default value / 默认值
        if node.value is not None:
            default = _extract_field_default(node.value)
            description = _extract_field_description(node.value)

            if default is not None:
                prop["default"] = default
            if description:
                prop["description"] = description
        else:
            # No default = required / 无默认值 = 必填
            required_fields.append(field_name)

        properties[field_name] = prop

    if not properties:
        return {}

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required_fields:
        schema["required"] = required_fields

    return schema


def _extract_field_default(value_node: ast.expr) -> Any:
    """
    Extract default value for Valves field.
    提取 Valves 字段的默认值。

    Supports / 支持：
    - Direct literal: app_id: str = "" / 直接字面量
    - Field(default, ...): app_id: str = Field("", description="...")
    """
    # Direct literal / 直接字面量
    if isinstance(value_node, ast.Constant):
        return value_node.value

    # Field(...) call / Field(...) 调用
    if isinstance(value_node, ast.Call):
        func_name = _get_call_name(value_node)
        if func_name == "Field":
            # Field's first positional argument is default / Field 的第一个位置参数是 default
            if value_node.args:
                return _ast_value_to_python(value_node.args[0])
            # Or Field(default=xxx) / 或 Field(default=xxx)
            for kw in value_node.keywords:
                if kw.arg == "default":
                    return _ast_value_to_python(kw.value)
    return None


def _extract_field_description(value_node: ast.expr) -> str:
    """Extract description from Field(..., description="xxx"). / 提取 Field(..., description="xxx") 中的 description。"""
    if not isinstance(value_node, ast.Call):
        return ""

    func_name = _get_call_name(value_node)
    if func_name != "Field":
        return ""

    for kw in value_node.keywords:
        if kw.arg == "description" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return ""


def _get_call_name(node: ast.Call) -> str:
    """Get function call name. / 获取函数调用的名称。"""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


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

    # Syntax check / 语法检查
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        errors.append(_("toolkit.error.syntax_error").format(line=exc.lineno, msg=exc.msg))
        return errors

    # Must have Tools class / 必须有 Tools 类
    tools_class = _find_class(tree, "Tools")
    if tools_class is None:
        errors.append(_("toolkit.error.missing_tools_class"))
        return errors

    # Tools class must have at least one public method / Tools 类至少有一个公开方法
    has_public_method = False
    for node in ast.iter_child_nodes(tools_class):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            has_public_method = True
            break

    if not has_public_method:
        errors.append(_("toolkit.error.no_public_methods"))

    # Dangerous pattern scan (warning, non-blocking) / 危险模式扫描（警告，不阻断）
    warnings = scan_dangerous_patterns(tree)
    errors.extend(warnings)

    return errors


# Dangerous import module blacklist / 危险导入模块黑名单
_DANGEROUS_MODULES = {"os", "subprocess", "sys", "shutil", "ctypes", "signal"}

# Dangerous function call blacklist / 危险函数调用黑名单
_DANGEROUS_CALLS = {"exec", "eval", "compile", "__import__", "execfile", "globals"}

# Dangerous attribute call patterns (module.func) / 危险属性调用模式（module.func）
_DANGEROUS_ATTR_CALLS = {
    ("os", "system"), ("os", "popen"), ("os", "exec"),
    ("os", "execvp"), ("os", "remove"), ("os", "rmdir"),
    ("subprocess", "call"), ("subprocess", "run"),
    ("subprocess", "Popen"), ("subprocess", "check_output"),
    ("shutil", "rmtree"),
}


def scan_dangerous_patterns(tree: ast.Module) -> list[str]:
    """
    Scan AST for dangerous patterns, return warning list (non-blocking for uploads).
    扫描 AST 中的危险模式，返回警告列表（不阻断上传）。

    Checks / 检查项：
    - Dangerous module imports (os, subprocess, sys, shutil, etc.)
      危险模块导入
    - Dangerous function calls (exec, eval, compile, __import__, etc.)
      危险函数调用
    - Dangerous attribute calls (os.system, subprocess.run, etc.)
      危险属性调用
    """
    warnings: list[str] = []

    for node in ast.walk(tree):
        # Check import statements / 检查 import 语句
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in _DANGEROUS_MODULES:
                    warnings.append(
                        f"[WARNING] Line {node.lineno}: import of '{alias.name}' "
                        f"— may pose security risks in sandbox"
                    )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod in _DANGEROUS_MODULES:
                    warnings.append(
                        f"[WARNING] Line {node.lineno}: import from '{node.module}' "
                        f"— may pose security risks in sandbox"
                    )

        # Check function calls / 检查函数调用
        elif isinstance(node, ast.Call):
            # Direct call: exec(...), eval(...) / 直接调用
            if isinstance(node.func, ast.Name):
                if node.func.id in _DANGEROUS_CALLS:
                    warnings.append(
                        f"[WARNING] Line {node.lineno}: call to '{node.func.id}()' "
                        f"— potential code execution risk"
                    )
            # Attribute call: os.system(...), subprocess.run(...) / 属性调用
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                pair = (node.func.value.id, node.func.attr)
                if pair in _DANGEROUS_ATTR_CALLS:
                    warnings.append(
                        f"[WARNING] Line {node.lineno}: call to "
                        f"'{pair[0]}.{pair[1]}()' — potential security risk"
                    )

    return warnings


__all__ = [
    "ToolkitMeta",
    "ToolkitToolMeta",
    "ToolkitParseError",
    "parse_toolkit",
    "validate_toolkit_source",
    "toolkit_tools_to_definitions",
]
