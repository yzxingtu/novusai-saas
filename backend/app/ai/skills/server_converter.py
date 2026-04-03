"""
Server Package → Toolkit Converter
Server 包 → Toolkit 转换器

Automatically converts SKILL.md server packages (FastAPI-based)
into class Tools format compatible with ToolkitParser.
自动将 SKILL.md server 包（基于 FastAPI）转换为与 ToolkitParser 兼容的 class Tools 格式。

Handles the common pattern / 处理常见模式：
  server/
    auth.py          → _get_token() / _request() internal helpers / 内部辅助函数
    xxx_api.py       → async def methods in class Tools / Tools 类的异步方法
    main.py          → skipped (app entry point) / 跳过（应用入口）

Falls back to a combined-source template if auto-conversion fails.
自动转换失败时回退到合并源码模板。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

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

    try:
        result = _convert(sources, metadata, env_schema)
        logger.info(
            "Server package auto-converted to toolkit: {}",
            metadata.get("name", "unknown"),
        )
        return result
    except Exception as exc:
        logger.warning(
            "Auto-conversion failed for '{}', using fallback: {}",
            metadata.get("name", "unknown"),
            exc,
        )
        return _fallback_combine(sources, metadata)


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
    for src in sources.values():
        m = re.search(
            r"(?:HOST|BASE_URL|API_URL|FEISHU_HOST|API_BASE)"
            r"\s*=\s*[\"']([^\"']+)[\"']",
            src,
        )
        if m:
            return m.group(1)
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
        path_params = re.findall(r"\{(\w+)\}", url_path)

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


# ─────────────────────────────────────────────────────────────
# Code generation / 代码生成
# ─────────────────────────────────────────────────────────────


def _generate(
    name: str,
    desc: str,
    base_url: str,
    env_requires: list[str],
    handlers: list[dict[str, Any]],
    env_schema: dict[str, Any] | None = None,
) -> str:
    L: list[str] = []

    # Module docstring / 模块文档字符串
    L.append(f'"""\ntitle: {name}\ndescription: {desc}\nversion: 1.0.0\n"""')
    L.append("")
    L.append("import json")
    L.append("import time")
    L.append("from typing import Any")
    L.append("")
    L.append("import httpx")
    L.append("from pydantic import BaseModel, Field")
    L.append("")

    if base_url:
        L.append(f'_BASE_URL = "{base_url}"')
        L.append("")

    # Valves — use env_schema for rich descriptions/defaults if available
    # Valves — 使用 env_schema 提供丰富描述和默认值（如可用）
    L.append("")
    L.append("class Valves(BaseModel):")
    L.append('    """Configuration"""')
    L.append("")

    env_props = (env_schema or {}).get("properties", {}) if env_schema else {}

    if env_requires or env_props:
        # Merge: env_requires list + env_schema properties (unified lowercase)
        # 合并：env_requires 列表 + env_schema properties（统一 lowercase）
        all_vars = list(
            dict.fromkeys(list(env_props.keys()) + [v.lower() for v in env_requires])
        )
        for var in all_vars:
            prop = env_props.get(var, {})
            field_desc = prop.get("description", var)
            field_default = prop.get("default", "")
            # Escape quotes in description / 转义描述中的引号
            field_desc = str(field_desc).replace('"', '\\"')
            field_default_str = str(field_default).replace('"', '\\"')
            L.append(
                f"    {var.lower()}: str = Field("
                f'default="{field_default_str}", '
                f'description="{field_desc}")'
            )
    else:
        L.append("    pass")
    L.append("")
    L.append("")

    # class Tools / Tools 类
    L.append("class Tools:")
    L.append(f'    """{desc}"""')
    L.append("")
    L.append("    valves: Valves")
    L.append("")
    L.append("    def __init__(self):")
    L.append("        self.valves = Valves()")
    L.append('        self._token = ""')
    L.append("        self._token_expires = 0.0")
    L.append("")

    # _get_token / 获取访问令牌
    _gen_token_method(L, base_url, env_requires)
    L.append("")

    # _headers / 请求头
    L.append("    async def _headers(self) -> dict[str, str]:")
    L.append("        token = await self._get_token()")
    L.append("        return {")
    L.append('            "Content-Type": "application/json; charset=utf-8",')
    L.append('            "Authorization": f"Bearer {token}",')
    L.append("        }")
    L.append("")

    # _request / HTTP 请求方法
    _gen_request_method(L, base_url)
    L.append("")

    # Tool methods / 工具方法
    for h in handlers:
        _gen_tool_method(L, h)

    return "\n".join(L) + "\n"


def _gen_token_method(
    L: list[str],
    base_url: str,
    env_requires: list[str],
) -> None:
    L.append("    async def _get_token(self) -> str:")
    L.append("        now = time.time()")
    L.append("        if self._token and now < self._token_expires:")
    L.append("            return self._token")

    id_var = next(
        (v for v in env_requires if "ID" in v.upper()),
        None,
    )
    secret_var = next(
        (v for v in env_requires if "SECRET" in v.upper()),
        None,
    )

    if id_var and secret_var:
        if "feishu" in base_url.lower() or "lark" in base_url.lower():
            token_url = f"{base_url}/open-apis/auth/v3/tenant_access_token/internal"
            token_key = "tenant_access_token"
        else:
            token_url = f"{base_url}/auth/token"
            token_key = "access_token"

        L.append("        async with httpx.AsyncClient(timeout=10.0) as _client:")
        L.append("            resp = await _client.post(")
        L.append(f'                "{token_url}",')
        L.append("                json={")
        L.append(f'                    "app_id": self.valves.{id_var.lower()},')
        L.append(f'                    "app_secret": self.valves.{secret_var.lower()},')
        L.append("                },")
        L.append("            )")
        L.append("        data = resp.json()")
        L.append('        if data.get("code") != 0:')
        L.append(
            "            raise Exception(f\"Auth error: {data.get('msg', 'unknown')}\")"
        )
        L.append(
            f'        self._token = data.get("{token_key}",'
            f' data.get("access_token", ""))'
        )
        L.append('        self._token_expires = now + data.get("expire", 7200) - 300')
        L.append("        return self._token")
    else:
        L.append(
            '        raise NotImplementedError("Configure _get_token for your API")'
        )


def _gen_request_method(L: list[str], base_url: str) -> None:
    L.append("    async def _request(")
    L.append("        self,")
    L.append("        method: str,")
    L.append("        path: str,")
    L.append("        *,")
    L.append("        params: dict | None = None,")
    L.append("        json_body: dict | None = None,")
    L.append("    ) -> dict:")
    if base_url:
        L.append('        url = f"{_BASE_URL}{path}"')
    else:
        L.append("        url = path")
    L.append("        headers = await self._headers()")
    L.append("        async with httpx.AsyncClient(timeout=30.0) as _client:")
    L.append("            resp = await _client.request(")
    L.append("                method, url, headers=headers,")
    L.append("                params=params, json=json_body,")
    L.append("            )")
    L.append("        if resp.status_code != 200:")
    L.append(
        '            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")'
    )
    L.append("        data = resp.json()")
    L.append('        code = data.get("code", -1)')
    L.append("        if code != 0:")
    L.append(
        "            raise Exception("
        "f\"API error (code={code}): {data.get('msg', '')}\")"
    )
    L.append('        return data.get("data", data)')


def _gen_tool_method(L: list[str], handler: dict[str, Any]) -> None:
    name = handler["name"]
    params = handler["params"]
    docstring = handler["docstring"]
    method = handler["method"]
    path = handler["path"]
    path_params = handler.get("path_params", [])

    # Signature / 函数签名
    sig_parts = ["self"]
    for p in params:
        ptype = p.get("type", "str")
        if p.get("required", True):
            sig_parts.append(f"{p['name']}: {ptype}")
        else:
            dval = p.get("default")
            if dval is None or dval == "":
                ds = '""' if ptype == "str" else "0" if ptype == "int" else '""'
            elif isinstance(dval, str):
                ds = f'"{dval}"'
            else:
                ds = repr(dval)
            sig_parts.append(f"{p['name']}: {ptype} = {ds}")

    if len(sig_parts) <= 3:
        sig = ", ".join(sig_parts)
        L.append(f"    async def {name}({sig}) -> str:")
    else:
        L.append(f"    async def {name}(")
        for _i, sp in enumerate(sig_parts):
            L.append(f"        {sp},")
        L.append("    ) -> str:")

    # Docstring / 文档字符串
    if docstring:
        L.append('        """')
        for dl in docstring.splitlines():
            L.append(f"        {dl.strip()}" if dl.strip() else "")
        if params:
            L.append("")
            L.append("        Args:")
            for p in params:
                pdesc = p.get("description") or p["name"]
                L.append(f"            {p['name']}: {pdesc}")
        L.append('        """')
    else:
        L.append(f'        """{name}"""')

    # Body: build params/body and call self._request()
    # 构建参数/请求体并调用 self._request()
    # Handle path formatting with path params / 处理带路径参数的路径格式化
    path_expr = f'f"{path}"' if path_params else f'"{path}"'

    non_path_params = [p for p in params if p["name"] not in path_params]

    if method in ("POST", "PUT", "PATCH"):
        if non_path_params:
            L.append("        body: dict[str, Any] = {}")
            for p in non_path_params:
                pn = p["name"]
                L.append(f"        if {pn} is not None:")
                L.append(f'            body["{pn}"] = {pn}')
            L.append(
                f"        data = await self._request("
                f'"{method}", {path_expr}, json_body=body)'
            )
        else:
            L.append(f'        data = await self._request("{method}", {path_expr})')
    else:
        if non_path_params:
            L.append("        params: dict[str, Any] = {}")
            for p in non_path_params:
                pn = p["name"]
                L.append(f"        if {pn} is not None:")
                L.append(f'            params["{pn}"] = {pn}')
            L.append(
                f"        data = await self._request("
                f'"{method}", {path_expr}, params=params)'
            )
        else:
            L.append(f'        data = await self._request("{method}", {path_expr})')

    L.append("        return json.dumps(data, ensure_ascii=False)")
    L.append("")


# ─────────────────────────────────────────────────────────────
# Credential sanitisation / 凭据脱敏
# ─────────────────────────────────────────────────────────────

_CREDENTIAL_PATTERN = re.compile(
    r"""(?ix)
    ^\s*
    (?:
        [A-Z_]*(?:SECRET|PASSWORD|PASSWD|TOKEN|API_KEY|APP_KEY|PRIVATE_KEY|ACCESS_KEY)
        [A-Z_]*
    )
    \s*=\s*
    ['\"]
    [^'\"]+
    ['\"]
    """,
)


def _sanitize_source(source: str) -> str:
    """Redact credential-like assignments from source code. / 从源码中脱敏凭据类赋值。"""
    lines: list[str] = []
    for line in source.splitlines():
        if _CREDENTIAL_PATTERN.match(line):
            var_name = line.split("=", 1)[0].strip()
            lines.append(f'{var_name} = "***REDACTED***"')
        else:
            lines.append(line)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Fallback: combine all source files with template / 回退：合并所有源文件与模板
# ─────────────────────────────────────────────────────────────


def _fallback_combine(
    sources: dict[str, str],
    metadata: dict[str, Any],
) -> str:
    env_requires = _extract_env_requires(metadata)
    name = metadata.get("name", "Toolkit")
    desc = metadata.get("description", "")

    L: list[str] = []
    L.append(f'"""\ntitle: {name}\ndescription: {desc}\nversion: 1.0.0')
    L.append("")
    L.append(
        "Auto-conversion failed. Original server source appended below as reference."
    )
    L.append(
        "Wrap relevant functions in class Tools to make them available as LLM tools."
    )
    L.append('"""')
    L.append("")
    L.append("import json")
    L.append("from typing import Any")
    L.append("")
    L.append("import httpx")
    L.append("from pydantic import BaseModel, Field")
    L.append("")
    L.append("")
    L.append("class Valves(BaseModel):")
    if env_requires:
        for var in env_requires:
            L.append(f'    {var.lower()}: str = Field(default="", description="{var}")')
    else:
        L.append("    pass")
    L.append("")
    L.append("")
    L.append("class Tools:")
    L.append(f'    """{desc}"""')
    L.append("")
    L.append("    valves: Valves")
    L.append("")
    L.append("    def __init__(self):")
    L.append("        self.valves = Valves()")
    L.append("")
    L.append("    # TODO: Add async methods here.")
    L.append("    # Each public async method becomes an LLM tool.")
    L.append("    # See original source below for reference.")
    L.append("")
    L.append("")

    for fname, src in sources.items():
        L.append(f"# {'=' * 60}")
        L.append(f"# Original source: {fname}.py")
        L.append(f"# {'=' * 60}")
        L.append("")
        sanitized = _sanitize_source(src)
        for line in sanitized.splitlines():
            L.append(f"# {line}" if line.strip() else "#")
        L.append("")

    return "\n".join(L) + "\n"
