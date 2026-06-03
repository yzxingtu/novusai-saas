"""Generator support utilities. / 生成器支撑工具。"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.codegen.config_parser import ParsedConfig
from app.codegen.type_registry import type_registry


def detect_scenario(parsed: ParsedConfig) -> str:
    """
    判断生成场景 A/B/C/D / Detect generation scenario.

    A: BaseModel + admin_only (平台独立)
    B: TenantModel + admin + cross_tenant
    C: TenantModel + tenant_only
    D: TenantModel + dual + cross_tenant
    """
    base = (parsed.model or {}).get("base_class", "TenantModel")
    scopes = [e.get("scope") for e in parsed.endpoints if e.get("scope")]
    data_modes = [e.get("data_mode") for e in parsed.endpoints]
    has_admin = "admin" in scopes or "admin_only" in scopes
    has_tenant = "tenant" in scopes or "tenant_only" in scopes
    cross_tenant = "cross_tenant" in data_modes

    if base == "BaseModel":
        if has_tenant:
            return "invalid"
        return "A"
    if has_admin and has_tenant and cross_tenant:
        return "D"
    if has_admin and cross_tenant:
        return "B"
    if has_tenant and not has_admin:
        return "C"
    if has_admin and has_tenant:
        return "D"
    return "A"


def path_no_leading_slash(s: str) -> str:
    """Strip leading slashes only; preserve multi-segment paths. /foo/bar -> foo/bar."""
    if not s:
        return s or ""
    return str(s).lstrip("/")


def string_max_length(yaml_type: str) -> int | None:
    """Extract max length from String(N) type, e.g. String(50) -> 50."""
    if not yaml_type or "String" not in str(yaml_type):
        return None
    m = re.search(r"String\s*\(\s*(\d+)\s*\)", str(yaml_type), re.I)
    return int(m.group(1)) if m else None


def to_python_literal(val: str) -> str:
    """Convert JSON-style true/false/null in string to Python literals."""
    if not val:
        return val
    s = str(val)
    s = re.sub(r"\btrue\b", "True", s)
    s = re.sub(r"\bfalse\b", "False", s)
    s = re.sub(r"\bnull\b", "None", s)
    return s


def camel(s: str) -> str:
    """snake_case 转 camelCase / snake_case -> camelCase."""
    if not s:
        return s
    parts = str(s).replace("-", "_").split("_")
    return parts[0].lower() + "".join(w.capitalize() for w in parts[1:])


def get_column_args(field: dict, reg=None) -> str:
    """生成 mapped_column 参数字符串，含 ForeignKey 时自动插入 / Gen mapped_column args with FK when needed."""
    registry = reg or type_registry
    base = registry.get_mapped_column_args(field)
    fk = fk_ref(field.get("type", ""))
    if fk and base.startswith("Integer, "):
        return f"Integer, {fk}, {base[9:]}"
    return base


def pascal(s: str) -> str:
    """snake_case / 单数 -> PascalCase."""
    if not s:
        return s
    return "".join(w.capitalize() for w in str(s).replace("-", "_").split("_"))


def fk_ref(yaml_type: str) -> str | None:
    """ForeignKey(table) -> ForeignKey(\"table.id\")."""
    m = re.match(
        r"^ForeignKey\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)$",
        str(yaml_type or ""),
        re.I,
    )
    if m:
        table = m.group(1)
        return f'ForeignKey("{table}.id")'
    return None


def model_to_table(model_name: str) -> str:
    """Model class name -> table name."""
    if not model_name:
        return ""
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", str(model_name)).lower()
    if s.endswith(("s", "x", "ch", "sh")):
        return s + "es"
    if s.endswith("y") and len(s) > 1 and s[-2] not in "aeiou":
        return s[:-1] + "ies"
    return s + "s"


def pluralize(word: str) -> str:
    """单数->复数 / Singular to plural."""
    if not word:
        return word
    w = str(word)
    if w.endswith("ies") or w.endswith("es"):
        return w
    if w.endswith("s") and not w.endswith("ss"):
        if w.endswith(("us", "as", "is", "os")) and len(w) > 2:
            return w + "es"
        return w
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    if w.endswith(("s", "x", "ch", "sh")):
        return w + "es"
    return w + "s"


def singularize(table_name: str) -> str:
    """复数表名->单数 / Plural table name to singular."""
    if not table_name or len(table_name) < 2:
        return table_name
    t = str(table_name)
    if t.endswith("ies") and len(t) > 3 and t[-4] not in "aeiou":
        return t[:-3] + "y"
    if (
        t.endswith("es")
        and len(t) > 2
        and (
            t.endswith("ses")
            or t.endswith("xes")
            or t.endswith("ches")
            or t.endswith("shes")
        )
    ):
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def model_to_fk(model_name: str) -> str:
    """Model -> fk column name."""
    if not model_name:
        return "_id"
    t = model_to_table(model_name)
    singular = singularize(t)
    return singular + "_id"


def derive_workflow_states(workflow: dict | None) -> list[dict]:
    """Derive states from workflow.states or transitions."""
    if not workflow:
        return []
    states = workflow.get("states") or []
    if states:
        return [
            s if isinstance(s, dict) else {"name": str(s), "label": str(s)}
            for s in states
        ]
    trans = workflow.get("transitions") or []
    seen: set[str] = set()
    result: list[dict] = []
    for t in trans:
        for key in ("from", "to"):
            val = t.get(key)
            if val and val not in seen:
                seen.add(val)
                result.append(
                    {"name": val, "label": str(val).replace("_", " ").title()}
                )
    return result


def create_template_environment(templates_dir: Path) -> Environment:
    """Create jinja environment with codegen helpers."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["type_registry"] = type_registry
    env.filters["pascal"] = pascal
    env.filters["fk_ref"] = fk_ref
    env.filters["model_to_table"] = model_to_table
    env.filters["model_to_fk"] = model_to_fk
    env.filters["camel"] = camel
    env.filters["pluralize"] = pluralize
    env.filters["to_python_literal"] = to_python_literal
    env.filters["string_max_length"] = string_max_length
    env.filters["path_no_leading_slash"] = path_no_leading_slash
    env.globals["get_column_args"] = get_column_args
    return env


__all__ = [
    "detect_scenario",
    "path_no_leading_slash",
    "string_max_length",
    "to_python_literal",
    "camel",
    "get_column_args",
    "pascal",
    "fk_ref",
    "model_to_table",
    "pluralize",
    "singularize",
    "model_to_fk",
    "derive_workflow_states",
    "create_template_environment",
]
