"""
配置解析器 / Config Parser

YAML/JSON 配置解析、简写展开、合法性校验
YAML/JSON config parsing, shorthand expansion, validation.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from app.codegen.constants import (
    BASE_CLASS_VALUES,
    DATA_MODE_VALUES,
    SCOPE_VALUES,
    SUB_TABLE_MODE_VALUES,
)
from app.codegen.type_registry import type_registry
from app.core.i18n import _

# 字段名保留字（Python/SQL/JS 冲突 + 系统/DB 字段）/ Reserved names (Python/SQL/JS + system/DB)
RESERVED_NAMES = frozenset(
    {
        "id", "type", "class", "for", "def", "if", "else", "from", "import", "return", "async", "await",
        "created_at", "updated_at", "deleted_at", "tenant_id", "is_deleted",
    }
)

# 字段名格式：小写字母开头，仅小写字母、数字、下划线 / Field name: [a-z] start, then [a-z0-9_] only
FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# module/resource 格式：小写字母、数字、下划线 / module/resource: [a-z0-9_]
MODULE_RESOURCE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class ValidationError:
    """校验错误 / Validation error."""

    code: str
    message: str
    path: str = ""
    field: str = ""


@dataclass
class ParsedConfig:
    """
    解析后的配置 / Parsed config.

    包含所有解析、展开、校验后的结构化数据
    Contains all parsed, expanded, validated structured data.
    """

    raw: dict[str, Any]
    module: str = ""
    resource: str = ""
    resource_plural: str = ""
    display_name: str = ""
    display_name_en: str = ""
    model: dict[str, Any] = field(default_factory=dict)
    fields: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    endpoints: list[dict[str, Any]] = field(default_factory=list)
    workflow: dict[str, Any] | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    batch: dict[str, Any] | None = None
    detail: dict[str, Any] | None = None
    clone: dict[str, Any] | None = None
    sub_tables: list[dict[str, Any]] = field(default_factory=list)


def _infer_plural(resource: str) -> str:
    """推断复数形式 / Infer plural form. 与 generator._pluralize 逻辑一致."""
    if not resource:
        return ""
    # 已是复数（与 generator 一致）
    if resource.endswith("ies") or resource.endswith("es"):
        return resource
    if resource.endswith("s") and not resource.endswith("ss"):
        if resource.endswith(("us", "as", "is", "os")) and len(resource) > 2:
            return resource + "es"
        return resource
    if resource.endswith("y") and len(resource) > 1 and resource[-2] not in "aeiou":
        return resource[:-1] + "ies"
    if resource.endswith(("s", "x", "ch", "sh")):
        return resource + "es"
    return resource + "s"


def _expand_shorthand_field(field_def: dict[str, Any]) -> dict[str, Any]:
    """
    展开字段简写 / Expand field shorthand.

    searchable: true -> filterable + search.enabled + filter_op: ilike
    column: true -> column.visible = true
    form: input -> form.component = input
    """
    out = dict(field_def)

    if field_def.get("searchable") is True:
        out["filterable"] = True
        if "search" not in out or not isinstance(out["search"], dict):
            out["search"] = {}
        out["search"] = dict(out["search"])
        out["search"]["enabled"] = True
        out["search"]["type"] = out["search"].get("type") or "input"
        out["filter_op"] = out.get("filter_op") or "ilike"
    elif field_def.get("searchable") is False:
        out["filterable"] = False
        if "search" not in out or not isinstance(out["search"], dict):
            out["search"] = {}
        out["search"] = dict(out["search"])
        out["search"]["enabled"] = False

    if "column" in field_def:
        col = field_def["column"]
        if col is True:
            out["column"] = {"visible": True}
        elif col is False:
            out["column"] = {"visible": False}
        elif isinstance(col, dict):
            out["column"] = dict(col)
            if "visible" not in out["column"]:
                out["column"]["visible"] = True

    if "form" in field_def:
        form_val = field_def["form"]
        if isinstance(form_val, str):
            out["form"] = {"component": form_val}
        elif isinstance(form_val, dict):
            out["form"] = dict(form_val)

    # 自动拆分 comment 的 中文 / English 格式为 comment 和 comment_en
    comment = out.get("comment", "")
    if comment and " / " in comment and not out.get("comment_en"):
        parts = str(comment).split(" / ", 1)
        out["comment"] = parts[0].strip()
        out["comment_en"] = parts[1].strip()

    return out


def _expand_shorthand(config: dict[str, Any]) -> dict[str, Any]:
    """展开配置中所有简写（含 fields 与 sub_tables[].fields）/ Expand all shorthand (fields + sub_tables[].fields)."""
    out = copy.deepcopy(config)
    if "fields" in out and isinstance(out["fields"], list):
        out["fields"] = [_expand_shorthand_field(f) for f in out["fields"]]
    if "sub_tables" in out and isinstance(out["sub_tables"], list):
        for i, st in enumerate(out["sub_tables"]):
            if isinstance(st, dict) and "fields" in st and isinstance(st["fields"], list):
                st = dict(st)
                st["fields"] = [_expand_shorthand_field(f) for f in st["fields"]]
                out["sub_tables"][i] = st
    return out


def _expand_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """
    自动填充未设置的默认值 / Auto-fill unset defaults.

    为 model, fields, endpoints 等节点填充合理默认
    """
    out = dict(config)

    # model 默认值 / model defaults
    model = out.get("model") or {}
    if not isinstance(model, dict):
        model = {}
    model = dict(model)
    model.setdefault("base_class", "TenantModel")
    model.setdefault("table_name", out.get("resource_plural") or _infer_plural(out.get("resource", "")))
    model.setdefault("soft_delete", True)
    model.setdefault("data_permission", False)
    out["model"] = model

    # resource_plural 默认 / resource_plural default
    if not out.get("resource_plural") and out.get("resource"):
        out["resource_plural"] = _infer_plural(out["resource"])

    # endpoints 默认值 / endpoints defaults
    if "endpoints" in out and isinstance(out["endpoints"], list):
        for i, ep in enumerate(out["endpoints"]):
            if not isinstance(ep, dict):
                continue
            ep = dict(ep)
            ep.setdefault("scope", "admin")
            ep.setdefault("data_mode", "cross_tenant" if ep.get("scope") == "admin" else "independent")
            if "route_prefix" in ep and ep["route_prefix"] and not str(ep["route_prefix"]).startswith("/"):
                ep["route_prefix"] = "/" + str(ep["route_prefix"])
            frontend = ep.get("frontend") or {}
            if isinstance(frontend, dict):
                frontend = dict(frontend)
                frontend.setdefault("mode", "table")
                frontend.setdefault("page_size", 20)
                frontend.setdefault("default_sort", "-created_at")
                frontend.setdefault("search_default_open", False)
                frontend.setdefault("quick_search", True)
                frontend.setdefault("recycle_bin", False)
                frontend.setdefault("export", False)
                batch_cfg = out.get("batch") or {}
                frontend.setdefault("import", batch_cfg.get("import", False))
                frontend.setdefault("drag_sort", False)
                ep["frontend"] = frontend
            out["endpoints"][i] = ep

    return out


def _is_search_enabled(field_def: dict[str, Any]) -> bool:
    search_cfg = field_def.get("search", {})
    if isinstance(search_cfg, dict):
        return bool(search_cfg.get("enabled", field_def.get("filterable", False)))
    return bool(field_def.get("filterable", False))


def _is_quick_search_candidate(field_def: dict[str, Any]) -> bool:
    if field_def.get("divider") or field_def.get("type") == "__divider__":
        return False
    if not _is_search_enabled(field_def):
        return False
    try:
        return type_registry.get_search_component(field_def) == "input"
    except Exception:
        return False


class ConfigParser:
    """
    配置解析器 / Config parser.

    解析 YAML/JSON，展开简写，校验合法性
    Parses YAML/JSON, expands shorthand, validates.
    """

    def parse(self, config: dict | str) -> ParsedConfig:
        """
        解析配置 / Parse config.

        Args:
            config: YAML 字符串或 dict

        Returns:
            ParsedConfig
        """
        if isinstance(config, str):
            data = yaml.safe_load(config)
            if not isinstance(data, dict):
                raise ValueError(_("codegen.config_invalid_yaml"))
        else:
            data = dict(config)

        data = _expand_shorthand(data)
        data = _expand_defaults(data)

        return ParsedConfig(
            raw=data,
            module=str(data.get("module", "")),
            resource=str(data.get("resource", "")),
            resource_plural=str(data.get("resource_plural", "")),
            display_name=str(data.get("display_name", "")),
            display_name_en=str(data.get("display_name_en", "")),
            model=data.get("model") or {},
            fields=data.get("fields") or [],
            relations=data.get("relations") or [],
            endpoints=data.get("endpoints") or [],
            workflow=data.get("workflow"),
            actions=data.get("actions") or [],
            batch=data.get("batch"),
            detail=data.get("detail"),
            clone=data.get("clone"),
            sub_tables=data.get("sub_tables") or [],
        )

    def validate(
        self,
        config: dict | str | ParsedConfig,
        *,
        require_fields: bool = True,
    ) -> list[ValidationError]:
        """
        校验配置，返回所有错误 / Validate config, return all errors.

        Args:
            config: 配置 dict、YAML 字符串或 ParsedConfig
            require_fields: 是否要求 fields 非空；草稿保存时为 False，生成前校验时为 True

        Returns:
            错误列表，空表示通过
        """
        errors: list[ValidationError] = []

        if isinstance(config, ParsedConfig):
            parsed = config
            data = parsed.raw
        else:
            try:
                parsed = self.parse(config)
                data = parsed.raw
            except Exception as e:
                errors.append(
                    ValidationError(
                        code="parse_error",
                        message=str(e),
                        path="",
                    )
                )
                return errors

        # 必填字段（草稿保存不校验 fields，仅生成前校验）
        # Required fields (draft save skips fields check; only validate before generate)
        if not parsed.module:
            errors.append(ValidationError("missing_module", _("codegen.validation.module_required"), path="module"))
        elif not MODULE_RESOURCE_PATTERN.match(parsed.module):
            errors.append(
                ValidationError(
                    "invalid_module",
                    _("codegen.validation.invalid_module_format"),
                    path="module",
                )
            )
        if not parsed.resource:
            errors.append(ValidationError("missing_resource", _("codegen.validation.resource_required"), path="resource"))
        elif not MODULE_RESOURCE_PATTERN.match(parsed.resource):
            errors.append(
                ValidationError(
                    "invalid_resource",
                    _("codegen.validation.invalid_resource_format"),
                    path="resource",
                )
            )
        if not parsed.display_name:
            errors.append(
                ValidationError("missing_display_name", _("codegen.validation.display_name_required"), path="display_name")
            )
        if require_fields and not parsed.fields:
            errors.append(ValidationError("missing_fields", _("codegen.validation.fields_required"), path="fields"))

        # scope / data_mode / base_class 合法值校验 / Validate scope, data_mode, base_class
        base_class = (parsed.model or {}).get("base_class", "TenantModel")
        if base_class not in BASE_CLASS_VALUES:
            errors.append(
                ValidationError(
                    "invalid_base_class",
                    _("codegen.validation.invalid_base_class").format(
                        value=base_class, allowed=", ".join(sorted(BASE_CLASS_VALUES))
                    ),
                    path="model.base_class",
                )
            )
        for i, ep in enumerate(parsed.endpoints):
            scope = (ep or {}).get("scope")
            data_mode = (ep or {}).get("data_mode")
            if scope is not None and scope not in SCOPE_VALUES:
                errors.append(
                    ValidationError(
                        "invalid_scope",
                        _("codegen.validation.invalid_scope").format(
                            value=scope, allowed=", ".join(sorted(SCOPE_VALUES))
                        ),
                        path=f"endpoints[{i}].scope",
                    )
                )
            if data_mode is not None and data_mode not in DATA_MODE_VALUES:
                errors.append(
                    ValidationError(
                        "invalid_data_mode",
                        _("codegen.validation.invalid_data_mode").format(
                            value=data_mode, allowed=", ".join(sorted(DATA_MODE_VALUES))
                        ),
                        path=f"endpoints[{i}].data_mode",
                    )
                )
            # BaseModel + tenant_only 非法 / BaseModel + tenant_only invalid
            if base_class == "BaseModel":
                if scope == "tenant_only":
                    errors.append(
                        ValidationError(
                            "invalid_base_tenant",
                            _("codegen.validation.base_model_tenant_only"),
                            path=f"endpoints[{i}]",
                        )
                    )
                if data_mode == "cross_tenant":
                    errors.append(
                        ValidationError(
                            "invalid_base_cross_tenant",
                            _("codegen.validation.base_model_cross_tenant"),
                            path=f"endpoints[{i}]",
                        )
                    )

            frontend = (ep or {}).get("frontend")
            if frontend is not None and not isinstance(frontend, dict):
                errors.append(
                    ValidationError(
                        "invalid_frontend_config",
                        "frontend config must be an object",
                        path=f"endpoints[{i}].frontend",
                    )
                )
                continue

            frontend_cfg = frontend or {}
            search_default_open = frontend_cfg.get("search_default_open")
            if search_default_open is not None and not isinstance(search_default_open, bool):
                errors.append(
                    ValidationError(
                        "invalid_search_default_open",
                        "frontend.search_default_open must be boolean",
                        path=f"endpoints[{i}].frontend.search_default_open",
                    )
                )

            quick_search = frontend_cfg.get("quick_search")
            quick_search_candidates = {
                str(field.get("name"))
                for field in parsed.fields
                if isinstance(field.get("name"), str) and _is_quick_search_candidate(field)
            }
            if quick_search is not None:
                if isinstance(quick_search, bool):
                    pass
                elif isinstance(quick_search, dict):
                    qs_fields = quick_search.get("fields")
                    default_field = quick_search.get("default_field") or quick_search.get(
                        "defaultField"
                    )

                    if qs_fields is not None and not isinstance(qs_fields, list):
                        errors.append(
                            ValidationError(
                                "invalid_quick_search_fields",
                                "frontend.quick_search.fields must be a list of field names",
                                path=f"endpoints[{i}].frontend.quick_search.fields",
                            )
                        )
                    elif isinstance(qs_fields, list):
                        for j, field_name in enumerate(qs_fields):
                            source_field = None
                            if isinstance(field_name, str):
                                source_field = field_name
                            elif isinstance(field_name, dict):
                                source_field = field_name.get("fieldName")
                                if source_field is not None and not isinstance(source_field, str):
                                    errors.append(
                                        ValidationError(
                                            "invalid_quick_search_field",
                                            "frontend.quick_search.fields[].fieldName must be a string",
                                            path=f"endpoints[{i}].frontend.quick_search.fields[{j}].fieldName",
                                        )
                                    )
                                    continue
                            else:
                                errors.append(
                                    ValidationError(
                                        "invalid_quick_search_field",
                                        "frontend.quick_search.fields items must be strings or objects",
                                        path=f"endpoints[{i}].frontend.quick_search.fields[{j}]",
                                    )
                                )
                                continue

                            if not source_field:
                                errors.append(
                                    ValidationError(
                                        "invalid_quick_search_field",
                                        "frontend.quick_search.fields items must define fieldName",
                                        path=f"endpoints[{i}].frontend.quick_search.fields[{j}]",
                                    )
                                )
                                continue

                            if source_field not in quick_search_candidates:
                                errors.append(
                                    ValidationError(
                                        "unknown_quick_search_field",
                                        f"frontend.quick_search field '{source_field}' is not a valid quick-search candidate",
                                        path=f"endpoints[{i}].frontend.quick_search.fields[{j}]",
                                    )
                                )

                    if default_field is not None and not isinstance(default_field, str):
                        errors.append(
                            ValidationError(
                                "invalid_quick_search_default_field",
                                "frontend.quick_search.default_field must be a string",
                                path=f"endpoints[{i}].frontend.quick_search.default_field",
                            )
                        )
                    elif isinstance(default_field, str):
                        if default_field not in quick_search_candidates:
                            errors.append(
                                ValidationError(
                                    "unknown_quick_search_default_field",
                                    f"frontend.quick_search default field '{default_field}' is not a valid quick-search candidate",
                                        path=f"endpoints[{i}].frontend.quick_search.default_field",
                                    )
                                )
                        qs_source_fields: list[str] = []
                        if isinstance(qs_fields, list):
                            for field_item in qs_fields:
                                if isinstance(field_item, str):
                                    qs_source_fields.append(field_item)
                                elif isinstance(field_item, dict) and isinstance(
                                    field_item.get("fieldName"), str
                                ):
                                    qs_source_fields.append(field_item["fieldName"])
                        if qs_source_fields and default_field not in qs_source_fields:
                            errors.append(
                                ValidationError(
                                    "inconsistent_quick_search_default_field",
                                    "frontend.quick_search.default_field must be included in frontend.quick_search.fields",
                                    path=f"endpoints[{i}].frontend.quick_search.default_field",
                                )
                            )
                else:
                    errors.append(
                        ValidationError(
                            "invalid_quick_search_config",
                            "frontend.quick_search must be boolean or an object",
                            path=f"endpoints[{i}].frontend.quick_search",
                        )
                    )

        # sub_tables mode 合法值校验 / Validate sub_table mode
        for i, st in enumerate(parsed.sub_tables or []):
            if isinstance(st, dict) and (mode := st.get("mode")) is not None and mode not in SUB_TABLE_MODE_VALUES:
                errors.append(
                    ValidationError(
                        "invalid_sub_table_mode",
                        _("codegen.validation.invalid_sub_table_mode").format(
                            value=mode, allowed=", ".join(sorted(SUB_TABLE_MODE_VALUES))
                        ),
                        path=f"sub_tables[{i}].mode",
                    )
                )

        # tree 需要 TenantModel 或 BaseModel
        model = parsed.model or {}
        if model.get("tree") and isinstance(model["tree"], dict) and model["tree"].get("enabled"):
            if base_class not in ("TenantModel", "BaseModel"):
                errors.append(
                    ValidationError(
                        "invalid_tree_base",
                        _("codegen.validation.tree_requires_base"),
                        path="model.tree",
                    )
                )

        # 字段基本校验 / Field basic validation
        seen_names: dict[str, list[int]] = {}
        for i, f in enumerate(parsed.fields):
            if f.get("divider") or f.get("type") == "__divider__":
                continue
            name = f.get("name")
            if not name:
                errors.append(
                    ValidationError("field_no_name", _("codegen.validation.field_name_required"), path=f"fields[{i}]")
                )
            else:
                key = str(name).strip()
                if key.lower() in RESERVED_NAMES:
                    errors.append(
                        ValidationError(
                            "reserved_field_name",
                            _("codegen.validation.reserved_field_name").format(name=key),
                            path=f"fields[{i}]",
                            field="name",
                        )
                    )
                elif not FIELD_NAME_PATTERN.match(key):
                    errors.append(
                        ValidationError(
                            "invalid_field_name",
                            _("codegen.validation.invalid_field_name").format(name=key),
                            path=f"fields[{i}]",
                            field="name",
                        )
                    )
                key_lower = key.lower()
                if key_lower not in seen_names:
                    seen_names[key_lower] = []
                seen_names[key_lower].append(i)
            ftype = f.get("type", "String")
            if ftype and not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*(\s*\([^)]*\))?$", str(ftype)):
                errors.append(
                    ValidationError(
                        "invalid_field_type",
                        _("codegen.validation.invalid_field_type").format(type=ftype),
                        path=f"fields[{i}]",
                        field="type",
                    )
                )
            elif ftype and not type_registry.is_type_registered(ftype):
                errors.append(
                    ValidationError(
                        "unknown_field_type",
                        _("codegen.validation.unknown_field_type").format(type=ftype),
                        path=f"fields[{i}]",
                        field="type",
                    )
                )

        duplicates = {k: v for k, v in seen_names.items() if len(v) > 1}
        if duplicates:
            names_str = ", ".join(duplicates.keys())
            errors.append(
                ValidationError(
                    "duplicate_field_name",
                    _("codegen.validation.duplicate_field_name").format(names=names_str),
                    path="fields",
                )
            )

        return errors

    def expand_defaults(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        对配置执行默认值展开 / Expand defaults for config.

        Returns:
            展开后的 config dict
        """
        return _expand_defaults(_expand_shorthand(config))


# 添加 i18n 键 / Add i18n keys
# codegen.validation.* 需在 messages.json 中定义 / Define in messages.json

__all__ = ["ConfigParser", "ParsedConfig", "ValidationError"]
