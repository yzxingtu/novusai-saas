"""
Server converter code generation support.

Keeps toolkit source rendering out of the AST parsing helper facade.
"""

from __future__ import annotations

from typing import Any


def generate_toolkit_source(
    name: str,
    desc: str,
    base_url: str,
    env_requires: list[str],
    handlers: list[dict[str, Any]],
    env_schema: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []

    lines.append(f'"""\ntitle: {name}\ndescription: {desc}\nversion: 1.0.0\n"""')
    lines.append("")
    lines.append("import json")
    lines.append("import time")
    lines.append("from typing import Any")
    lines.append("")
    lines.append("import httpx")
    lines.append("from pydantic import BaseModel, Field")
    lines.append("")

    if base_url:
        lines.append(f'_BASE_URL = "{base_url}"')
        lines.append("")

    lines.append("")
    lines.append("class Valves(BaseModel):")
    lines.append('    """Configuration"""')
    lines.append("")

    env_props = (env_schema or {}).get("properties", {}) if env_schema else {}
    if env_requires or env_props:
        all_vars = list(
            dict.fromkeys(
                list(env_props.keys()) + [value.lower() for value in env_requires]
            )
        )
        for var in all_vars:
            prop = env_props.get(var, {})
            field_desc = str(prop.get("description", var)).replace('"', '\\"')
            field_default = str(prop.get("default", "")).replace('"', '\\"')
            lines.append(
                f"    {var.lower()}: str = Field("
                f'default="{field_default}", '
                f'description="{field_desc}")'
            )
    else:
        lines.append("    pass")
    lines.append("")
    lines.append("")

    lines.append("class Tools:")
    lines.append(f'    """{desc}"""')
    lines.append("")
    lines.append("    valves: Valves")
    lines.append("")
    lines.append("    def __init__(self):")
    lines.append("        self.valves = Valves()")
    lines.append('        self._token = ""')
    lines.append("        self._token_expires = 0.0")
    lines.append("")

    _append_token_method(lines, base_url, env_requires)
    lines.append("")
    _append_headers_method(lines)
    lines.append("")
    _append_request_method(lines, base_url)
    lines.append("")

    for handler in handlers:
        _append_tool_method(lines, handler)

    return "\n".join(lines) + "\n"


def _append_headers_method(lines: list[str]) -> None:
    lines.append("    async def _headers(self) -> dict[str, str]:")
    lines.append("        token = await self._get_token()")
    lines.append("        return {")
    lines.append('            "Content-Type": "application/json; charset=utf-8",')
    lines.append('            "Authorization": f"Bearer {token}",')
    lines.append("        }")


def _append_token_method(
    lines: list[str],
    base_url: str,
    env_requires: list[str],
) -> None:
    lines.append("    async def _get_token(self) -> str:")
    lines.append("        now = time.time()")
    lines.append("        if self._token and now < self._token_expires:")
    lines.append("            return self._token")

    id_var = next((value for value in env_requires if "ID" in value.upper()), None)
    secret_var = next(
        (value for value in env_requires if "SECRET" in value.upper()),
        None,
    )

    if id_var and secret_var:
        if "feishu" in base_url.lower() or "lark" in base_url.lower():
            token_url = f"{base_url}/open-apis/auth/v3/tenant_access_token/internal"
            token_key = "tenant_access_token"
        else:
            token_url = f"{base_url}/auth/token"
            token_key = "access_token"

        lines.append("        async with httpx.AsyncClient(timeout=10.0) as _client:")
        lines.append("            resp = await _client.post(")
        lines.append(f'                "{token_url}",')
        lines.append("                json={")
        lines.append(f'                    "app_id": self.valves.{id_var.lower()},')
        lines.append(
            f'                    "app_secret": self.valves.{secret_var.lower()},'
        )
        lines.append("                },")
        lines.append("            )")
        lines.append("        data = resp.json()")
        lines.append('        if data.get("code") != 0:')
        lines.append(
            "            raise Exception(f\"Auth error: {data.get('msg', 'unknown')}\")"
        )
        lines.append(
            f'        self._token = data.get("{token_key}",'
            f' data.get("access_token", ""))'
        )
        lines.append(
            '        self._token_expires = now + data.get("expire", 7200) - 300'
        )
        lines.append("        return self._token")
        return

    lines.append(
        '        raise NotImplementedError("Configure _get_token for your API")'
    )


def _append_request_method(lines: list[str], base_url: str) -> None:
    lines.append("    async def _request(")
    lines.append("        self,")
    lines.append("        method: str,")
    lines.append("        path: str,")
    lines.append("        *,")
    lines.append("        params: dict | None = None,")
    lines.append("        json_body: dict | None = None,")
    lines.append("    ) -> dict:")
    if base_url:
        lines.append('        url = f"{_BASE_URL}{path}"')
    else:
        lines.append("        url = path")
    lines.append("        headers = await self._headers()")
    lines.append("        async with httpx.AsyncClient(timeout=30.0) as _client:")
    lines.append("            resp = await _client.request(")
    lines.append("                method, url, headers=headers,")
    lines.append("                params=params, json=json_body,")
    lines.append("            )")
    lines.append("        if resp.status_code != 200:")
    lines.append(
        '            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")'
    )
    lines.append("        data = resp.json()")
    lines.append('        code = data.get("code", -1)')
    lines.append("        if code != 0:")
    lines.append(
        "            raise Exception("
        "f\"API error (code={code}): {data.get('msg', '')}\")"
    )
    lines.append('        return data.get("data", data)')


def _append_tool_method(lines: list[str], handler: dict[str, Any]) -> None:
    name = handler["name"]
    params = handler["params"]
    docstring = handler["docstring"]
    method = handler["method"]
    path = handler["path"]
    path_params = handler.get("path_params", [])

    sig_parts = ["self"]
    for param in params:
        param_type = param.get("type", "str")
        if param.get("required", True):
            sig_parts.append(f"{param['name']}: {param_type}")
            continue

        default_value = param.get("default")
        if default_value is None or default_value == "":
            rendered_default = (
                '""' if param_type == "str" else "0" if param_type == "int" else '""'
            )
        elif isinstance(default_value, str):
            rendered_default = f'"{default_value}"'
        else:
            rendered_default = repr(default_value)
        sig_parts.append(f"{param['name']}: {param_type} = {rendered_default}")

    if len(sig_parts) <= 3:
        lines.append(f"    async def {name}({', '.join(sig_parts)}) -> str:")
    else:
        lines.append(f"    async def {name}(")
        for signature_part in sig_parts:
            lines.append(f"        {signature_part},")
        lines.append("    ) -> str:")

    if docstring:
        lines.append('        """')
        for doc_line in docstring.splitlines():
            lines.append(f"        {doc_line.strip()}" if doc_line.strip() else "")
        if params:
            lines.append("")
            lines.append("        Args:")
            for param in params:
                description = param.get("description") or param["name"]
                lines.append(f"            {param['name']}: {description}")
        lines.append('        """')
    else:
        lines.append(f'        """{name}"""')

    path_expr = f'f"{path}"' if path_params else f'"{path}"'
    non_path_params = [param for param in params if param["name"] not in path_params]

    if method in ("POST", "PUT", "PATCH"):
        _append_payload_request_body(
            lines,
            method=method,
            path_expr=path_expr,
            params=non_path_params,
            payload_name="body",
            request_kwarg="json_body",
        )
    else:
        _append_payload_request_body(
            lines,
            method=method,
            path_expr=path_expr,
            params=non_path_params,
            payload_name="params",
            request_kwarg="params",
        )

    lines.append("        return json.dumps(data, ensure_ascii=False)")
    lines.append("")


def _append_payload_request_body(
    lines: list[str],
    *,
    method: str,
    path_expr: str,
    params: list[dict[str, Any]],
    payload_name: str,
    request_kwarg: str,
) -> None:
    if not params:
        lines.append(f'        data = await self._request("{method}", {path_expr})')
        return

    lines.append(f"        {payload_name}: dict[str, Any] = {{}}")
    for param in params:
        param_name = param["name"]
        lines.append(f"        if {param_name} is not None:")
        lines.append(f'            {payload_name}["{param_name}"] = {param_name}')
    lines.append(
        f'        data = await self._request("{method}", {path_expr}, {request_kwarg}={payload_name})'
    )
