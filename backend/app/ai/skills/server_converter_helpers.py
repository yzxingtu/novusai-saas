"""
Server Package → Toolkit Converter helpers.

This module contains the full conversion implementation used by
server_converter.convert_server_to_toolkit.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.ai.skills.server_converter_codegen import (
    generate_toolkit_source as _generate,
)
from app.ai.text_semantics import extract_braced_identifiers
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.skill.converter")


def convert_server_to_toolkit(
    server_dir: Path,
    metadata: dict[str, Any],
    env_schema: dict[str, Any] | None = None,
) -> str:
    """
    Convert a server/ directory to a class Tools Python source.
    将 server/ 目录转换为 class Tools 的 Python 源码。

    Args:
        server_dir: Path to the extracted server/ directory / 解压后的 server/ 目录路径
        metadata: Parsed SKILL.md metadata / 解析后的 SKILL.md 元数据
        env_schema: Valves schema parsed from .env.example (optional),
                    used to generate Valves class with descriptions and defaults /
                    从 .env.example 解析的 valves_schema（可选），
                    用于生成带描述和默认值的 Valves 类

    Returns:
        Python source code containing class Valves + class Tools /
        包含 class Valves + class Tools 的 Python 源码
    """
    sources = _read_sources(server_dir)
    if not sources:
        return ""

    # If any file already has class Tools, use it directly
    # 如果任何文件已有 class Tools，直接使用
    for src in sources.values():
        if "class Tools" in src:
            return src

    result = _convert(sources, metadata, env_schema)
    logger.info(
        "Server package auto-converted to toolkit: {}",
        metadata.get("name", "unknown"),
    )
    return result


# ─────────────────────────────────────────────────────────────
# File reading / 文件读取
# ─────────────────────────────────────────────────────────────


def _read_sources(server_dir: Path) -> dict[str, str]:
    """Read all .py files recursively, skip __init__.py. / 递归读取所有 .py 文件，跳过 __init__.py。"""
    result: dict[str, str] = {}
    for pf in sorted(server_dir.rglob("*.py")):
        if pf.name == "__init__.py":
            continue
        try:
            result[pf.stem] = pf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
    return result


# ─────────────────────────────────────────────────────────────
# Main conversion / 主转换逻辑
# ─────────────────────────────────────────────────────────────


def _convert(
    sources: dict[str, str],
    metadata: dict[str, Any],
    env_schema: dict[str, Any] | None = None,
) -> str:
    env_requires = _extract_env_requires(metadata)
    name = metadata.get("name", "Toolkit")
    desc = metadata.get("description", "")

    base_url = _find_base_url(sources)
    auth_mod = _find_auth_module(sources)

    # Extract route handlers from API modules / 从 API 模块提取路由处理函数
    handlers: list[dict[str, Any]] = []
    for mod_name, src in sources.items():
        if mod_name == auth_mod or mod_name == "main":
            continue
        handlers.extend(_parse_handlers(src, mod_name))

    if not handlers:
        raise ValueError("No FastAPI route handlers found in server/ source")

    return _generate(name, desc, base_url, env_requires, handlers, env_schema)


# ─────────────────────────────────────────────────────────────
# Metadata extraction / 元数据提取
# ─────────────────────────────────────────────────────────────


def _extract_env_requires(metadata: dict[str, Any]) -> list[str]:
    meta = metadata.get("metadata", {})
    if not isinstance(meta, dict):
        return []
    clawdbot = meta.get("clawdbot", {})
    if not isinstance(clawdbot, dict):
        return []
    requires = clawdbot.get("requires", {})
    if not isinstance(requires, dict):
        return []
    return requires.get("env", [])


def _find_base_url(sources: dict[str, str]) -> str:
    keys = {"HOST", "BASE_URL", "API_URL", "FEISHU_HOST", "API_BASE"}
    for src in sources.values():
        for line in src.splitlines():
            stripped = line.strip()
            if "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip().upper() not in keys:
                continue
            normalized_value = value.strip().strip('"').strip("'")
            if normalized_value:
                return normalized_value
    return ""


def _find_auth_module(sources: dict[str, str]) -> str | None:
    for name, src in sources.items():
        if "access_token" in src.lower() and "def " in src:
            return name
    return None


# ─────────────────────────────────────────────────────────────
# AST-based handler extraction / 基于 AST 的处理函数提取
# ─────────────────────────────────────────────────────────────


def _parse_handlers(source: str, module_name: str) -> list[dict[str, Any]]:
    """Extract FastAPI route handlers from a module source. / 从模块源码提取 FastAPI 路由处理函数。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    models = _find_pydantic_models(tree)
    handlers: list[dict[str, Any]] = []

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.decorator_list:
            continue

        http_method, url_path = "", ""
        for dec in node.decorator_list:
            http_method, url_path = _parse_route_decorator(dec)
            if http_method:
                break

        if not http_method:
            continue

        # Extract path parameters like {event_id} / 提取路径参数如 {event_id}
        path_params = extract_braced_identifiers(url_path)

        params = _extract_params(node, models, path_params)
        docstring = ast.get_docstring(node) or ""

        handlers.append(
            {
                "name": node.name,
                "method": http_method,
                "path": url_path,
                "module": module_name,
                "docstring": docstring,
                "params": params,
                "path_params": path_params,
            }
        )

    return handlers


def _parse_route_decorator(dec: ast.expr) -> tuple[str, str]:
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
        method = dec.func.attr
        if method in ("get", "post", "put", "patch", "delete"):
            path = ""
            if dec.args and isinstance(dec.args[0], ast.Constant):
                path = str(dec.args[0].value)
            return method.upper(), path
    return "", ""


def _find_pydantic_models(tree: ast.Module) -> dict[str, list[dict[str, Any]]]:
    """Find Pydantic BaseModel classes and extract their fields. / 查找 Pydantic BaseModel 类并提取其字段。"""
    models: dict[str, list[dict[str, Any]]] = {}
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(isinstance(b, ast.Name) and b.id == "BaseModel" for b in node.bases):
            continue

        fields: list[dict[str, Any]] = []
        for item in node.body:
            if not (
                isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            ):
                continue

            fname = item.target.id
            ftype = _simplify_type(
                ast.unparse(item.annotation) if item.annotation else "str"
            )
            description = ""
            default = None
            required = True

            if item.value and isinstance(item.value, ast.Call):
                func = item.value.func
                if isinstance(func, ast.Name) and func.id == "Field":
                    for kw in item.value.keywords:
                        if kw.arg == "description" and isinstance(
                            kw.value, ast.Constant
                        ):
                            description = kw.value.value
                        elif kw.arg == "default" and isinstance(kw.value, ast.Constant):
                            default = kw.value.value
                            required = False
                    if item.value.args:
                        first_arg = item.value.args[0]
                        if (
                            isinstance(first_arg, ast.Constant)
                            and first_arg.value is not ...
                        ):
                            default = first_arg.value
                            required = False

            fields.append(
                {
                    "name": fname,
                    "type": ftype,
                    "description": description,
                    "default": default,
                    "required": required,
                }
            )
        models[node.name] = fields
    return models


def _extract_params(
    node: ast.FunctionDef,
    models: dict[str, list[dict[str, Any]]],
    path_params: list[str],
) -> list[dict[str, Any]]:
    """Extract parameters, flattening Pydantic models into individual params. / 提取参数，将 Pydantic 模型展平为单独参数。"""
    params: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Path params first (always required str) / 先处理路径参数（始终必填 str）
    for pp in path_params:
        params.append(
            {
                "name": pp,
                "type": "str",
                "description": pp,
                "default": None,
                "required": True,
            }
        )
        seen.add(pp)

    num_args = len(node.args.args)
    num_defaults = len(node.args.defaults)
    default_offset = num_args - num_defaults

    for i, arg in enumerate(node.args.args):
        name = arg.arg
        if name in ("self", "request"):
            continue
        if name in seen:
            continue

        type_str = ast.unparse(arg.annotation) if arg.annotation else ""

        # If type is a Pydantic model → flatten its fields / 如果类型是 Pydantic 模型 → 展平其字段
        if type_str in models:
            for field in models[type_str]:
                if field["name"] not in seen:
                    params.append(field)
                    seen.add(field["name"])
            continue

        if type_str in ("Request", "Response"):
            continue

        description = ""
        default = None
        required = True

        default_idx = i - default_offset
        if 0 <= default_idx < len(node.args.defaults):
            dnode = node.args.defaults[default_idx]
            if isinstance(dnode, ast.Call):
                func = dnode.func
                if isinstance(func, ast.Name) and func.id in ("Query", "Path"):
                    for kw in dnode.keywords:
                        if kw.arg == "description" and isinstance(
                            kw.value, ast.Constant
                        ):
                            description = kw.value.value
                    if dnode.args:
                        first = dnode.args[0]
                        if isinstance(first, ast.Constant):
                            if first.value is not None and first.value is not ...:
                                default = first.value
                                required = False
                            elif first.value is None:
                                default = ""
                                required = False
            elif isinstance(dnode, ast.Constant):
                default = dnode.value
                required = False

        simple_type = _simplify_type(type_str) or "str"
        params.append(
            {
                "name": name,
                "type": simple_type,
                "description": description,
                "default": default,
                "required": required,
            }
        )
        seen.add(name)

    return params


def _simplify_type(type_str: str) -> str:
    t = type_str.replace("| None", "").strip()
    if t.startswith("list[") or t == "list":
        return "str"
    if t.startswith("dict[") or t == "dict":
        return "str"
    if t in ("int", "float", "bool", "str"):
        return t
    return "str"
