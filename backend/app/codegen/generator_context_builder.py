"""Template context builder for codegen generator."""

from __future__ import annotations

from app.codegen import generator_support as support
from app.codegen.config_parser import ParsedConfig


def build_generation_context(parsed: ParsedConfig) -> dict:
    """构建 Jinja2 模板上下文 / Build Jinja2 template context."""
    scenario = support.detect_scenario(parsed)
    if scenario == "invalid":
        from app.exceptions import ValidationException

        raise ValidationException(
            message="Invalid scenario: BaseModel cannot have tenant scope. Use TenantModel."
        )
    admin_eps = [
        e
        for e in (parsed.endpoints or [])
        if (e or {}).get("scope") in ("admin", "admin_only")
    ]
    tenant_eps = [
        e
        for e in (parsed.endpoints or [])
        if (e or {}).get("scope") in ("tenant", "tenant_only")
    ]
    admin_only_eps = [e for e in admin_eps if (e or {}).get("scope") == "admin_only"]
    tenant_only_eps = [e for e in tenant_eps if (e or {}).get("scope") == "tenant_only"]
    admin_ep = admin_eps[0] if admin_eps else {}
    tenant_ep = tenant_eps[0] if tenant_eps else {}
    toggle_field = ""
    for f in parsed.fields or []:
        if f.get("toggle_api"):
            toggle_field = f.get("toggle_field") or f.get("name", "")
            break
    has_toggle = bool(toggle_field)
    model_dict = dict(parsed.model or {})
    raw_deps = model_dict.get("__delete_deps__") or model_dict.get("delete_deps")
    if raw_deps and isinstance(raw_deps, list):
        deps_out = []
        for item in raw_deps:
            if isinstance(item, dict) and item.get("model"):
                deps_out.append(item)
            elif isinstance(item, str) and item.strip():
                pascal_name = "".join(
                    w.capitalize() for w in item.strip().replace("-", "_").split("_")
                )
                fk_col = support.model_to_fk(pascal_name)
                deps_out.append(
                    {"model": pascal_name, "fk_field": fk_col, "strategy": "BLOCK"}
                )
        model_dict = {**model_dict, "delete_deps": deps_out}

    merged_relations = list(parsed.relations or [])
    for st in parsed.sub_tables or []:
        sub_res = st.get("resource", "")
        if not sub_res:
            continue
        fk = st.get("foreign_key") or f"{parsed.resource}_id"
        merged_relations.append(
            {
                "type": "one_to_many",
                "target": "".join(
                    w.capitalize() for w in str(sub_res).replace("-", "_").split("_")
                ),
                "foreign_key": fk,
                "name": support.pluralize(sub_res),
                "back_populates": parsed.resource,
                "_from_sub_table": True,
            }
        )
    return {
        "true": True,
        "false": False,
        "parsed": parsed,
        "resource": parsed.resource,
        "resource_plural": parsed.resource_plural,
        "module": parsed.module,
        "display_name": parsed.display_name,
        "display_name_en": parsed.display_name_en,
        "model": model_dict,
        "fields": parsed.fields,
        "relations": merged_relations,
        "sub_tables": parsed.sub_tables or [],
        "endpoints": parsed.endpoints or [],
        "workflow": parsed.workflow,
        "actions": parsed.actions or [],
        "batch": parsed.batch,
        "detail": parsed.detail,
        "clone": parsed.clone,
        "scenario": scenario,
        "workflow_states_derived": support.derive_workflow_states(parsed.workflow),
        "admin_ep": admin_ep,
        "tenant_ep": tenant_ep,
        "admin_only_eps": admin_only_eps,
        "tenant_only_eps": tenant_only_eps,
        "has_admin_only": bool(admin_only_eps),
        "has_tenant_only": bool(tenant_only_eps),
        "toggle_field": toggle_field,
        "has_toggle": has_toggle,
    }


__all__ = ["build_generation_context"]
