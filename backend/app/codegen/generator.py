"""
代码生成器 / Code Generator

Jinja2 模板渲染引擎，根据 ParsedConfig 生成代码文件
Jinja2 template engine, generates code files from ParsedConfig.
"""

from __future__ import annotations

import json as _json
import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.codegen.config_parser import ParsedConfig
from app.codegen.type_registry import type_registry
from app.core.logging import LogManager

logger = LogManager.get_logger("codegen")

# 模板目录 / Templates directory
_TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass
class GeneratedFile:
    """生成文件描述 / Generated file descriptor."""

    path: str
    content: str
    action: str  # create | create_if_missing | append | merge_json | register_route / 写盘动作
    appended_content: str | None = None  # for append / 追加模式下的片段
    insert_before_last_marker: str | None = (
        None  # for append: insert before last occurrence instead of EOF / 追加时在末标记前插入而非 EOF
    )
    merged_keys: list[str] | None = None  # for merge_json / merge_json 要合并的键
    route_meta: dict | None = (
        None  # for register_route: {scope, resource} / 注册路由元数据
    )
    model_meta: dict | None = (
        None  # for register_model: {module, resource} / 注册模型元数据
    )


@dataclass
class GenerateResult:
    """生成结果（含文件列表与渲染异常）/ Generate result (files + render errors)."""

    files: list[GeneratedFile]
    errors: list[str]


def _detect_scenario(parsed: ParsedConfig) -> str:
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
    # has_admin and has_tenant but not cross_tenant -> dual tenant-isolated / 含 admin 与 tenant 且非跨租户 → 双端租户隔离
    if has_admin and has_tenant:
        return "D"
    return "A"


class CodeGenerator:
    """
    代码生成器 / Code generator.

    Jinja2 模板渲染，根据 step 分步生成
    Jinja2 template rendering, step-wise generation.
    """

    def __init__(self, templates_dir: Path | None = None):
        """
        Args:
            templates_dir: 模板目录，默认 app/codegen/templates
        """
        tmpl = templates_dir or _TEMPLATES_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(tmpl)),
            autoescape=select_autoescape(enabled_extensions=("html", "xml")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.globals["type_registry"] = type_registry
        self.env.filters["pascal"] = self._pascal
        self.env.filters["fk_ref"] = self._fk_ref
        self.env.filters["model_to_table"] = self._model_to_table
        self.env.filters["model_to_fk"] = self._model_to_fk
        self.env.filters["camel"] = self._camel
        self.env.filters["pluralize"] = self._pluralize
        self.env.filters["to_python_literal"] = self._to_python_literal
        self.env.filters["string_max_length"] = self._string_max_length
        self.env.filters["path_no_leading_slash"] = self._path_no_leading_slash
        self.env.globals["get_column_args"] = self._get_column_args

    @staticmethod
    def _path_no_leading_slash(s: str) -> str:
        """Strip leading slashes only; preserve multi-segment paths. /foo/bar -> foo/bar."""
        if not s:
            return s or ""
        return str(s).lstrip("/")

    @staticmethod
    def _string_max_length(yaml_type: str) -> int | None:
        """Extract max length from String(N) type, e.g. String(50) -> 50."""
        if not yaml_type or "String" not in str(yaml_type):
            return None
        m = re.search(r"String\s*\(\s*(\d+)\s*\)", str(yaml_type), re.I)
        return int(m.group(1)) if m else None

    @staticmethod
    def _to_python_literal(val: str) -> str:
        """Convert JSON-style true/false/null in string to Python literals (for embedding in Python source)."""
        if not val:
            return val
        s = str(val)
        # Replace JSON tokens (not inside strings) - use regex word boundaries / 替换 JSON 字面量（非字符串内），用单词边界正则
        s = re.sub(r"\btrue\b", "True", s)
        s = re.sub(r"\bfalse\b", "False", s)
        s = re.sub(r"\bnull\b", "None", s)
        return s

    @staticmethod
    def _camel(s: str) -> str:
        """snake_case 转 camelCase：created_at -> createdAt / snake_case -> camelCase."""
        if not s:
            return s
        parts = str(s).replace("-", "_").split("_")
        return parts[0].lower() + "".join(w.capitalize() for w in parts[1:])

    @staticmethod
    def _get_column_args(field: dict, reg=None) -> str:
        """生成 mapped_column 参数字符串，含 ForeignKey 时自动插入 / Gen mapped_column args with FK when needed."""
        from app.codegen.type_registry import type_registry as _tr

        registry = reg or _tr
        base = registry.get_mapped_column_args(field)
        fk = CodeGenerator._fk_ref(field.get("type", ""))
        if fk and base.startswith("Integer, "):
            return f"Integer, {fk}, {base[9:]}"
        return base

    @staticmethod
    def _pascal(s: str) -> str:
        """snake_case / 单数 -> PascalCase: department -> Department, tenant_plan -> TenantPlan"""
        if not s:
            return s
        return "".join(w.capitalize() for w in str(s).replace("-", "_").split("_"))

    @staticmethod
    def _fk_ref(yaml_type: str) -> str | None:
        """
        ForeignKey(table) 转为 mapped_column 的 ForeignKey("table.id") / ForeignKey(table) -> 'ForeignKey("table.id")'.
        其他类型返回 None / Other types -> None.
        """
        m = re.match(
            r"^ForeignKey\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)$",
            str(yaml_type or ""),
            re.I,
        )
        if m:
            table = m.group(1)
            return f'ForeignKey("{table}.id")'
        return None

    @staticmethod
    def _model_to_table(model_name: str) -> str:
        """Permission -> permissions, TenantPlan -> tenant_plans / Model class name to table name."""
        if not model_name:
            return ""
        s = re.sub(r"(?<!^)(?=[A-Z])", "_", str(model_name)).lower()
        if s.endswith(("s", "x", "ch", "sh")):
            return s + "es"
        if s.endswith("y") and len(s) > 1 and s[-2] not in "aeiou":
            return s[:-1] + "ies"
        return s + "s"

    @staticmethod
    def _pluralize(word: str) -> str:
        """单数->复数: category->categories, tag->tags, bus->buses / Singular to plural."""
        if not word:
            return word
        w = str(word)
        # 已是复数：-ies, -es；不以 -us/-as/-is/-os 结尾的 -s 不视为复数，避免 bus/status 误判
        if w.endswith("ies") or w.endswith("es"):
            return w
        if w.endswith("s") and not w.endswith("ss"):
            # -us/-as/-is/-os 结尾多为单数：bus, status, canvas, focus
            if w.endswith(("us", "as", "is", "os")) and len(w) > 2:
                return w + "es"
            # 其他 -s 视为已复数（如 tags, items）
            return w
        if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
            return w[:-1] + "ies"
        if w.endswith(("s", "x", "ch", "sh")):
            return w + "es"
        return w + "s"

    @staticmethod
    def _singularize(table_name: str) -> str:
        """复数表名->单数: categories->category, addresses->address / Plural table name to singular."""
        if not table_name or len(table_name) < 2:
            return table_name
        t = str(table_name)
        if t.endswith("ies") and len(t) > 3 and t[-4] not in "aeiou":
            return t[:-3] + "y"  # categories -> category / -ies 变 -y
        if t.endswith("es") and len(t) > 2:
            # addresses -> address, boxes -> box / 去 -es 类尾缀
            if (
                t.endswith("ses")
                or t.endswith("xes")
                or t.endswith("ches")
                or t.endswith("shes")
            ):
                return t[:-2]  # boxes -> box, addresses -> address / 去掉末尾 es
            if t.endswith("ies"):  # already handled / 已由 -ies 分支处理
                pass
        if t.endswith("s") and not t.endswith("ss"):
            return t[:-1]  # tags -> tag, permissions -> permission / 去尾单 s
        return t

    @staticmethod
    def _model_to_fk(model_name: str) -> str:
        """Permission -> permission_id, Category -> category_id / Model to FK column name."""
        if not model_name:
            return "_id"
        t = CodeGenerator._model_to_table(model_name)
        singular = CodeGenerator._singularize(t)
        return singular + "_id"

    @staticmethod
    def _derive_workflow_states(workflow: dict | None) -> list[dict]:
        """Derive states from workflow.states or transitions. / 从 states 或 transitions 推导状态."""
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

    def build_context(self, parsed: ParsedConfig) -> dict:
        """
        构建 Jinja2 模板上下文 / Build Jinja2 template context.

        Args:
            parsed: 解析后的配置

        Returns:
            模板上下文 dict
        """
        scenario = _detect_scenario(parsed)
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
        admin_only_eps = [
            e for e in admin_eps if (e or {}).get("scope") == "admin_only"
        ]
        tenant_only_eps = [
            e for e in tenant_eps if (e or {}).get("scope") == "tenant_only"
        ]
        admin_ep = admin_eps[0] if admin_eps else {}
        tenant_ep = tenant_eps[0] if tenant_eps else {}
        toggle_field = ""
        for f in parsed.fields or []:
            if f.get("toggle_api"):
                toggle_field = f.get("toggle_field") or f.get("name", "")
                break
        has_toggle = bool(toggle_field)
        # 兼容前端 __delete_deps__ (string[]) -> model.delete_deps (object[]) 供模板使用 / Adapt __delete_deps__ for template
        model_dict = dict(parsed.model or {})
        raw_deps = model_dict.get("__delete_deps__") or model_dict.get("delete_deps")
        if raw_deps and isinstance(raw_deps, list):
            deps_out = []
            for item in raw_deps:
                if isinstance(item, dict) and item.get("model"):
                    deps_out.append(item)
                elif isinstance(item, str) and item.strip():
                    # "tenant" -> Tenant, tenant_id / 模型名 PascalCase + 外键列
                    pascal = "".join(
                        w.capitalize()
                        for w in item.strip().replace("-", "_").split("_")
                    )
                    fk_col = CodeGenerator._model_to_fk(pascal)
                    deps_out.append(
                        {"model": pascal, "fk_field": fk_col, "strategy": "BLOCK"}
                    )
            model_dict = {**model_dict, "delete_deps": deps_out}

        # 合并 sub_tables 到 relations (one_to_many) 供 model 模板使用 / Merge sub_tables for model template
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
                        w.capitalize()
                        for w in str(sub_res).replace("-", "_").split("_")
                    ),
                    "foreign_key": fk,
                    "name": CodeGenerator._pluralize(sub_res),
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
            "workflow_states_derived": CodeGenerator._derive_workflow_states(
                parsed.workflow
            ),
            "admin_ep": admin_ep,
            "tenant_ep": tenant_ep,
            "admin_only_eps": admin_only_eps,
            "tenant_only_eps": tenant_only_eps,
            "has_admin_only": bool(admin_only_eps),
            "has_tenant_only": bool(tenant_only_eps),
            "toggle_field": toggle_field,
            "has_toggle": has_toggle,
        }

    def generate(
        self, parsed_config: ParsedConfig, step: str | None = None
    ) -> GenerateResult:
        """
        生成代码文件列表 / Generate code file list.

        Args:
            parsed_config: 解析后的配置
            step: None=全量, "model"=Model+Schema, "controller"=Controller, "frontend"=前端

        Returns:
            GenerateResult(files, errors) 渲染异常会收集到 errors 中
        """
        ctx = self.build_context(parsed_config)
        files: list[GeneratedFile] = []
        errors: list[str] = []
        resource = parsed_config.resource
        module = parsed_config.module

        if step in (None, "model"):
            try:
                tpl = self.env.get_template("backend/model.py.j2")
                content = tpl.render(**ctx)
                files.append(
                    GeneratedFile(
                        path=f"backend/app/models/{module}/{resource}.py",
                        content=content,
                        action="create",
                    )
                )
                # 首次新 module 时补齐 __init__.py / ensure module __init__ exists for new modules
                files.append(
                    GeneratedFile(
                        path=f"backend/app/models/{module}/__init__.py",
                        content="# Codegen module init\n",
                        action="create_if_missing",
                    )
                )
                # 自动注册模型，便于 alembic autogenerate 发现 / auto-register model for alembic
                pascal = "".join(
                    w.capitalize() for w in resource.replace("-", "_").split("_")
                )
                files.append(
                    GeneratedFile(
                        path=f"backend/app/models/{module}/__init__.py",
                        content="",
                        action="register_model",
                        model_meta={
                            "module": module,
                            "resource": resource,
                            "pascal": pascal,
                            "target": "module",
                        },
                    )
                )
                files.append(
                    GeneratedFile(
                        path="backend/app/models/__init__.py",
                        content="",
                        action="register_model",
                        model_meta={
                            "module": module,
                            "resource": resource,
                            "pascal": pascal,
                            "target": "root",
                        },
                    )
                )
                files.append(
                    GeneratedFile(
                        path="backend/migrations/env.py",
                        content="",
                        action="register_model",
                        model_meta={
                            "module": module,
                            "resource": resource,
                            "pascal": pascal,
                            "target": "env",
                        },
                    )
                )
            except Exception as e:
                err_msg = f"model: {e!s}"
                logger.warning("codegen template render failed: %s", e)
                errors.append(err_msg)
            for st in ctx.get("sub_tables") or []:
                sub_res = st.get("resource", "")
                if not sub_res:
                    continue
                sub_plural = CodeGenerator._pluralize(sub_res)
                main_fk = st.get("foreign_key") or f"{resource}_id"
                sub_ctx = {
                    **ctx,
                    "sub_resource": sub_res,
                    "sub_resource_plural": sub_plural,
                    "main_resource": resource,
                    "main_resource_plural": parsed_config.resource_plural,
                    "main_fk": main_fk,
                    "sub_fields": st.get("fields") or [],
                    "sub_display_name": st.get("display_name")
                    or sub_res.replace("_", " ").title(),
                    "sub_display_name_en": st.get("display_name_en")
                    or sub_res.replace("_", " ").title(),
                }
                try:
                    tpl = self.env.get_template("backend/model_sub.py.j2")
                    content = tpl.render(**sub_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"backend/app/models/{module}/{sub_res}.py",
                            content=content,
                            action="create",
                        )
                    )
                    sub_pascal = "".join(
                        w.capitalize() for w in sub_res.replace("-", "_").split("_")
                    )
                    for tgt in ("module", "root", "env"):
                        path_map = {
                            "module": f"backend/app/models/{module}/__init__.py",
                            "root": "backend/app/models/__init__.py",
                            "env": "backend/migrations/env.py",
                        }
                        files.append(
                            GeneratedFile(
                                path=path_map[tgt],
                                content="",
                                action="register_model",
                                model_meta={
                                    "module": module,
                                    "resource": sub_res,
                                    "pascal": sub_pascal,
                                    "target": tgt,
                                },
                            )
                        )
                except Exception as e:
                    err_msg = f"sub_model:{sub_res}: {e!s}"
                    logger.warning("codegen sub model template render failed: %s", e)
                    errors.append(err_msg)
            files.append(
                GeneratedFile(
                    path=f"backend/app/schemas/{module}/__init__.py",
                    content="# Codegen module init\n",
                    action="create_if_missing",
                )
            )
            try:
                tpl = self.env.get_template("backend/schema.py.j2")
                content = tpl.render(**ctx)
                files.append(
                    GeneratedFile(
                        path=f"backend/app/schemas/{module}/{resource}.py",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"schema: {e!s}"
                logger.warning("codegen template render failed: %s", e)
                errors.append(err_msg)
            files.append(
                GeneratedFile(
                    path=f"backend/app/repositories/{module}/__init__.py",
                    content="# Codegen module init\n",
                    action="create_if_missing",
                )
            )
            try:
                tpl = self.env.get_template("backend/repository.py.j2")
                content = tpl.render(**ctx)
                files.append(
                    GeneratedFile(
                        path=f"backend/app/repositories/{module}/{resource}_repository.py",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"repository: {e!s}"
                logger.warning("codegen template render failed: %s", e)
                errors.append(err_msg)
            files.append(
                GeneratedFile(
                    path=f"backend/app/services/{module}/__init__.py",
                    content="# Codegen module init\n",
                    action="create_if_missing",
                )
            )
            try:
                tpl = self.env.get_template("backend/service.py.j2")
                content = tpl.render(**ctx)
                files.append(
                    GeneratedFile(
                        path=f"backend/app/services/{module}/{resource}_service.py",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"service: {e!s}"
                logger.warning("codegen template render failed: %s", e)
                errors.append(err_msg)
            # 后端 i18n 自动合并 / Backend i18n auto-merge
            display_name = (
                parsed_config.display_name or resource.replace("_", " ").title()
            )
            display_name_en = (
                parsed_config.display_name_en or resource.replace("_", " ").title()
            )
            res_name = resource.replace(
                "_", "-"
            )  # 与 Controller @permission_resource(resource=...) 一致
            i18n_zh = {
                module: {
                    resource: {
                        "not_found": f"{display_name}不存在",
                        "created": f"{display_name}创建成功",
                        "updated": f"{display_name}更新成功",
                    }
                },
                "action": {
                    res_name: {
                        "list": f"查看{display_name}",
                        "create": f"创建{display_name}",
                        "update": f"更新{display_name}",
                        "delete": f"删除{display_name}",
                    }
                },
            }
            i18n_en = {
                module: {
                    resource: {
                        "not_found": f"{display_name_en} not found",
                        "created": f"{display_name_en} created successfully",
                        "updated": f"{display_name_en} updated successfully",
                    }
                },
                "action": {
                    res_name: {
                        "list": f"View {display_name_en}",
                        "create": f"Create {display_name_en}",
                        "update": f"Update {display_name_en}",
                        "delete": f"Delete {display_name_en}",
                    }
                },
            }
            merged_keys = [f"{module}.{resource}", f"action.{res_name}"]
            files.append(
                GeneratedFile(
                    path="backend/app/locales/zh_CN/messages.json",
                    content=_json.dumps(i18n_zh, ensure_ascii=False),
                    action="merge_json",
                    merged_keys=merged_keys,
                )
            )
            files.append(
                GeneratedFile(
                    path="backend/app/locales/en/messages.json",
                    content=_json.dumps(i18n_en, ensure_ascii=False),
                    action="merge_json",
                    merged_keys=merged_keys,
                )
            )

        if step in (None, "controller"):
            admin_eps = [
                e
                for e in (parsed_config.endpoints or [])
                if (e or {}).get("scope") in ("admin", "admin_only")
            ]
            if admin_eps:
                try:
                    tpl = self.env.get_template("backend/controller_admin.py.j2")
                    content = tpl.render(**ctx)
                    files.append(
                        GeneratedFile(
                            path=f"backend/app/api/admin/{resource}.py",
                            content=content,
                            action="create",
                        )
                    )
                    # 3c: 自动注册路由 / auto-register route
                    files.append(
                        GeneratedFile(
                            path="backend/app/api/admin/__init__.py",
                            content="",
                            action="register_route",
                            route_meta={"scope": "admin", "resource": resource},
                        )
                    )
                except Exception as e:
                    err_msg = f"controller_admin: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
            tenant_eps = [
                e
                for e in (parsed_config.endpoints or [])
                if (e or {}).get("scope") in ("tenant", "tenant_only")
            ]
            if tenant_eps:
                try:
                    tpl = self.env.get_template("backend/controller_tenant.py.j2")
                    content = tpl.render(**ctx)
                    files.append(
                        GeneratedFile(
                            path=f"backend/app/api/tenant/{resource}.py",
                            content=content,
                            action="create",
                        )
                    )
                    # 3c: 自动注册路由 / auto-register route
                    files.append(
                        GeneratedFile(
                            path="backend/app/api/tenant/__init__.py",
                            content="",
                            action="register_route",
                            route_meta={"scope": "tenant", "resource": resource},
                        )
                    )
                except Exception as e:
                    err_msg = f"controller_tenant: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)

        if step in (None, "test"):
            try:
                tpl = self.env.get_template("backend/test_service.py.j2")
                content = tpl.render(**ctx)
                files.append(
                    GeneratedFile(
                        path=f"backend/tests/services/{module}/test_{resource}_service.py",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"test_service: {e!s}"
                logger.warning("codegen template render failed: %s", e)
                errors.append(err_msg)

        if step in (None, "frontend"):
            frontend_root = "frontend/apps/web-antd/src"
            admin_ep = ctx.get("admin_ep") or {}
            tenant_ep = ctx.get("tenant_ep") or {}
            mode = (
                (admin_ep.get("frontend") or {}).get("mode")
                or (tenant_ep.get("frontend") or {}).get("mode")
                or "table"
            )

            if admin_ep:
                _menu_path = (admin_ep.get("permission") or {}).get("menu") or {}
                _raw_path = (
                    _menu_path.get("path")
                    or f"/{module.replace('_', '-')}/{resource.replace('_', '-')}s"
                )
                _list_path = _raw_path.lstrip("/")
                render_ctx = {
                    **ctx,
                    "api_scope": "admin",
                    "i18n_prefix": f"admin.{module}.{resource}",
                    "list_path": _list_path,
                }
                try:
                    tpl = self.env.get_template("frontend/api_admin.ts.j2")
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/api/admin/{resource}.ts",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"api_admin: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                try:
                    tpl = self.env.get_template(
                        "frontend/data_table.ts.j2"
                        if mode == "table"
                        else "frontend/data_card.ts.j2"
                    )
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/views/admin/{module}/{resource}/data.ts",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"data_admin: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                try:
                    tpl = self.env.get_template(
                        "frontend/index_table.vue.j2"
                        if mode == "table"
                        else "frontend/index_card.vue.j2"
                    )
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/views/admin/{module}/{resource}/index.vue",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"index_admin: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                try:
                    tpl = self.env.get_template("frontend/form.vue.j2")
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/views/admin/{module}/{resource}/modules/form.vue",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"form_admin: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                if (ctx.get("detail") or {}).get("enabled"):
                    detail_cfg = ctx.get("detail") or {}
                    detail_mode = detail_cfg.get("mode") or "drawer"
                    try:
                        if detail_mode == "page":
                            tpl = self.env.get_template("frontend/detail_page.vue.j2")
                            content = tpl.render(**render_ctx)
                            files.append(
                                GeneratedFile(
                                    path=f"{frontend_root}/views/admin/{module}/{resource}/detail.vue",
                                    content=content,
                                    action="create",
                                )
                            )
                            # 追加前端路由 / Append frontend route
                            route_block = (
                                "    // Codegen auto-registered: {resource} detail\n"
                                "    {{\n"
                                "      name: 'Admin{resource_pascal}Detail',\n"
                                "      path: '{list_path}/:id',\n"
                                "      component: () => import('#/views/admin/{module}/{resource}/detail.vue'),\n"
                                "      meta: {{\n"
                                "        hideInMenu: true,\n"
                                "        title: $t('admin.{module}.{resource}.detail'),\n"
                                "        activePath: '/admin/{list_path}',\n"
                                "      }},\n"
                                "    }},\n"
                            ).format(
                                resource=resource,
                                resource_pascal="".join(
                                    w.capitalize()
                                    for w in resource.replace("-", "_").split("_")
                                ),
                                list_path=_list_path,
                                module=module,
                            )
                            files.append(
                                GeneratedFile(
                                    path=f"{frontend_root}/router/routes/admin/index.ts",
                                    content="",
                                    action="append",
                                    appended_content=route_block.strip(),
                                    insert_before_last_marker="  ],",
                                )
                            )
                        else:
                            tpl = self.env.get_template("frontend/detail.vue.j2")
                            content = tpl.render(**render_ctx)
                            files.append(
                                GeneratedFile(
                                    path=f"{frontend_root}/views/admin/{module}/{resource}/modules/detail.vue",
                                    content=content,
                                    action="create",
                                )
                            )
                    except Exception as e:
                        err_msg = f"detail_admin: {e!s}"
                        logger.warning("codegen detail template render failed: %s", e)
                        errors.append(err_msg)
                try:
                    tpl = self.env.get_template("frontend/i18n_zh.json.j2")
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/locales/langs/zh-CN/admin/{module}/{resource}.json",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"i18n_zh_admin: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                try:
                    tpl = self.env.get_template("frontend/i18n_en.json.j2")
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/locales/langs/en-US/admin/{module}/{resource}.json",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"i18n_en_admin: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)

            if tenant_ep:
                _menu_path_tenant = (tenant_ep.get("permission") or {}).get(
                    "menu"
                ) or {}
                _raw_path_tenant = (
                    _menu_path_tenant.get("path")
                    or f"/{module.replace('_', '-')}/{resource.replace('_', '-')}s"
                )
                _list_path_tenant = _raw_path_tenant.lstrip("/")
                render_ctx = {
                    **ctx,
                    "api_scope": "tenant",
                    "i18n_prefix": f"tenant.{module}.{resource}",
                    "list_path": _list_path_tenant,
                }
                try:
                    tpl = self.env.get_template("frontend/api_tenant.ts.j2")
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/api/tenant/{resource}.ts",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"api_tenant: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                try:
                    tpl = self.env.get_template(
                        "frontend/data_table.ts.j2"
                        if mode == "table"
                        else "frontend/data_card.ts.j2"
                    )
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/views/tenant/{module}/{resource}/data.ts",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"data_tenant: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                try:
                    tpl = self.env.get_template(
                        "frontend/index_table.vue.j2"
                        if mode == "table"
                        else "frontend/index_card.vue.j2"
                    )
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/views/tenant/{module}/{resource}/index.vue",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"index_tenant: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                try:
                    tpl = self.env.get_template("frontend/form.vue.j2")
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/views/tenant/{module}/{resource}/modules/form.vue",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"form_tenant: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                if (ctx.get("detail") or {}).get("enabled"):
                    detail_cfg = ctx.get("detail") or {}
                    detail_mode = detail_cfg.get("mode") or "drawer"
                    try:
                        if detail_mode == "page":
                            tpl = self.env.get_template("frontend/detail_page.vue.j2")
                            content = tpl.render(**render_ctx)
                            files.append(
                                GeneratedFile(
                                    path=f"{frontend_root}/views/tenant/{module}/{resource}/detail.vue",
                                    content=content,
                                    action="create",
                                )
                            )
                            route_block = (
                                "    // Codegen auto-registered: {resource} detail\n"
                                "    {{\n"
                                "      name: 'Tenant{resource_pascal}Detail',\n"
                                "      path: '{list_path}/:id',\n"
                                "      component: () => import('#/views/tenant/{module}/{resource}/detail.vue'),\n"
                                "      meta: {{\n"
                                "        hideInMenu: true,\n"
                                "        title: $t('tenant.{module}.{resource}.detail'),\n"
                                "        activePath: '/tenant/{list_path}',\n"
                                "      }},\n"
                                "    }},\n"
                            ).format(
                                resource=resource,
                                resource_pascal="".join(
                                    w.capitalize()
                                    for w in resource.replace("-", "_").split("_")
                                ),
                                list_path=_list_path_tenant,
                                module=module,
                            )
                            files.append(
                                GeneratedFile(
                                    path=f"{frontend_root}/router/routes/tenant/index.ts",
                                    content="",
                                    action="append",
                                    appended_content=route_block.strip(),
                                    insert_before_last_marker="  ],",
                                )
                            )
                        else:
                            tpl = self.env.get_template("frontend/detail.vue.j2")
                            content = tpl.render(**render_ctx)
                            files.append(
                                GeneratedFile(
                                    path=f"{frontend_root}/views/tenant/{module}/{resource}/modules/detail.vue",
                                    content=content,
                                    action="create",
                                )
                            )
                    except Exception as e:
                        err_msg = f"detail_tenant: {e!s}"
                        logger.warning("codegen detail template render failed: %s", e)
                        errors.append(err_msg)
                try:
                    tpl = self.env.get_template("frontend/i18n_zh.json.j2")
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/locales/langs/zh-CN/tenant/{module}/{resource}.json",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"i18n_zh_tenant: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)
                try:
                    tpl = self.env.get_template("frontend/i18n_en.json.j2")
                    content = tpl.render(**render_ctx)
                    files.append(
                        GeneratedFile(
                            path=f"{frontend_root}/locales/langs/en-US/tenant/{module}/{resource}.json",
                            content=content,
                            action="create",
                        )
                    )
                except Exception as e:
                    err_msg = f"i18n_en_tenant: {e!s}"
                    logger.warning("codegen template render failed: %s", e)
                    errors.append(err_msg)

        if step in (None, "controller"):
            display_name = (
                parsed_config.display_name or resource.replace("_", " ").title()
            )
            display_name_en = (
                parsed_config.display_name_en or resource.replace("_", " ").title()
            )
            admin_ep = ctx.get("admin_ep") or {}
            tenant_ep = ctx.get("tenant_ep") or {}
            menu_zh: dict[str, dict[str, str]] = {}
            menu_en: dict[str, dict[str, str]] = {}
            if admin_ep:
                menu_zh.setdefault("admin", {})[resource] = display_name
                menu_en.setdefault("admin", {})[resource] = display_name_en
            if tenant_ep:
                menu_zh.setdefault("tenant", {})[resource] = display_name
                menu_en.setdefault("tenant", {})[resource] = display_name_en
            if menu_zh:
                merged_keys_list = []
                if admin_ep:
                    merged_keys_list.append(f"menu.admin.{resource}")
                if tenant_ep:
                    merged_keys_list.append(f"menu.tenant.{resource}")
                files.append(
                    GeneratedFile(
                        path="backend/app/locales/zh_CN/menu.json",
                        content=_json.dumps({"menu": menu_zh}, ensure_ascii=False),
                        action="merge_json",
                        merged_keys=merged_keys_list,
                    )
                )
                files.append(
                    GeneratedFile(
                        path="backend/app/locales/en/menu.json",
                        content=_json.dumps({"menu": menu_en}, ensure_ascii=False),
                        action="merge_json",
                        merged_keys=merged_keys_list,
                    )
                )

        return GenerateResult(files=files, errors=errors)


__all__ = ["CodeGenerator", "GeneratedFile", "GenerateResult"]
