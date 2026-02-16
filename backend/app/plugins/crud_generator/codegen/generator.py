"""
CRUD 代码生成器 — Generator 核心

从 CrudConfig 生成全部文件内容（dict[filepath, content]）。
- 加载 Jinja2 模板
- 构建渲染上下文
- 按 scope/layout 选择模板
- 输出 {相对路径: 文件内容} 字典
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any  # retained for Jinja2 template context (arbitrary values)

from jinja2 import Environment, FileSystemLoader, TemplateError

from app.core.logging import LogManager

logger = LogManager.get_logger("app")

from app.plugins.crud_generator.codegen.schemas import (
    CrudConfig,
    FieldConfig,
    LayoutVariant,
    RelationConfig,
    ScopeType,
)

__all__ = ["CrudGenerator"]

# ============================================================
# 常量
# ============================================================

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# 布局变体 → 前端 index 模板映射
_LAYOUT_TEMPLATE_MAP: dict[str, str] = {
    LayoutVariant.STANDARD: "index.vue.j2",
    LayoutVariant.CARD_LIST: "index_card.vue.j2",
    LayoutVariant.MASTER_DETAIL: "index_split.vue.j2",
    LayoutVariant.KANBAN: "index_kanban.vue.j2",
}


# ============================================================
# Jinja2 自定义过滤器
# ============================================================


def _snake_filter(name: str) -> str:
    """PascalCase / camelCase → snake_case"""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _pascal_filter(name: str) -> str:
    """snake_case / kebab-case → PascalCase"""
    return "".join(w.capitalize() for w in re.split(r"[_\-]", name))


def _camel_filter(name: str) -> str:
    """snake_case / kebab-case → camelCase"""
    pascal = _pascal_filter(name)
    return pascal[0].lower() + pascal[1:] if pascal else ""


def _capitalize_filter(s: str) -> str:
    """首字母大写"""
    return s[0].upper() + s[1:] if s else s


def _kebab_filter(name: str) -> str:
    """snake_case / PascalCase → kebab-case"""
    return _snake_filter(name).replace("_", "-")


# ============================================================
# 复数化
# ============================================================

_IRREGULAR_PLURALS: dict[str, str] = {
    "person": "people",
    "child": "children",
    "man": "men",
    "woman": "women",
    "mouse": "mice",
    "goose": "geese",
    "tooth": "teeth",
    "foot": "feet",
    "ox": "oxen",
    "leaf": "leaves",
    "life": "lives",
    "knife": "knives",
    "wife": "wives",
    "half": "halves",
    "self": "selves",
    "shelf": "shelves",
}

_UNCOUNTABLE: set[str] = {
    "data", "info", "information", "media", "metadata",
    "feedback", "software", "hardware", "equipment",
    "sheep", "fish", "deer", "species", "series",
    "news", "mathematics", "physics", "economics",
}


def _pluralize(word: str) -> str:
    """英文名词复数化（支持不规则名词和常见规则）

    处理 kebab-case 和 snake_case：只复数化最后一个单词。
    """
    if not word:
        return word

    # 分割复合词（kebab-case 或 snake_case）
    for sep in ("-", "_"):
        if sep in word:
            parts = word.rsplit(sep, 1)
            return parts[0] + sep + _pluralize(parts[1])

    lower = word.lower()

    # 不可数名词
    if lower in _UNCOUNTABLE:
        return word

    # 不规则复数
    if lower in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[lower]

    # 规则变化
    if lower.endswith(("s", "x", "z", "sh", "ch")):
        return word + "es"
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return word[:-1] + "ies"
    if lower.endswith("f"):
        return word[:-1] + "ves"
    if lower.endswith("fe"):
        return word[:-2] + "ves"

    return word + "s"


def _to_json(data: dict[str, object]) -> str:
    """将字典序列化为格式化 JSON 字符串（确保中文不被转义）"""
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


# ============================================================
# Generator
# ============================================================


class CrudGenerator:
    """CRUD 代码生成器核心引擎

    用法::

        gen = CrudGenerator()
        files = gen.generate(config)
        # files: dict[str, str]  {相对路径: 文件内容}
    """

    def __init__(self) -> None:
        self._env = self._create_env()

    # ---- Jinja2 环境 ----

    @staticmethod
    def _create_env() -> Environment:
        env = Environment(
            loader=FileSystemLoader(_TEMPLATES_DIR),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        env.filters["snake"] = _snake_filter
        env.filters["pascal"] = _pascal_filter
        env.filters["camel"] = _camel_filter
        env.filters["capitalize"] = _capitalize_filter
        env.filters["kebab"] = _kebab_filter
        env.filters["pluralize"] = _pluralize
        return env

    # ---- 上下文构建 ----

    @staticmethod
    def _build_context(config: CrudConfig, scope: str) -> dict[str, Any]:
        """为单个 scope 构建模板渲染上下文"""
        module_snake = config.module.replace("-", "_")
        model_class = _pascal_filter(module_snake)
        scope_dir = scope

        return {
            "config": config,
            "model_class": model_class,
            "module": config.module,
            "module_snake": module_snake,
            "scope": scope,
            "scope_dir": scope_dir,
            "table_name": config.table_name,
            "display_name": config.display_name,
            "display_name_en": config.display_name_en,
            "description": config.description or "",
            "fields": config.fields,
            "relations": config.relations,
            "enums": config.enums,
            "selectable": config.selectable,
            "indexes": config.indexes,
            "has_status_toggle": config.has_status_toggle,
            "recyclable": config.recyclable,
            "parent_menu": config.parent_menu,
            "permissions": config.permissions,
            "hooks": config.hooks,
            "search_config": config.search_config,
            "i18n_prefix": f"{scope_dir}.{module_snake}",
        }

    # ---- 路径计算 ----

    @staticmethod
    def _frontend_path(config: CrudConfig, scope: str, filename: str) -> str:
        """前端文件相对路径"""
        module_kebab = config.module.replace("_", "-")
        base = f"frontend/apps/web-antd/src"
        parent = config.parent_menu

        module_plural = _pluralize(module_kebab)

        if filename == "api.ts":
            return f"{base}/api/{scope}/{module_plural}.ts"
        elif filename == "data.ts":
            return f"{base}/views/{scope}/{parent}/{module_plural}/data.ts"
        elif filename.startswith("index"):
            return f"{base}/views/{scope}/{parent}/{module_plural}/index.vue"
        elif filename == "form.vue":
            return f"{base}/views/{scope}/{parent}/{module_plural}/modules/form.vue"
        return f"{base}/views/{scope}/{parent}/{module_plural}/{filename}"

    @staticmethod
    def _i18n_path(config: CrudConfig, scope: str, filename: str) -> str:
        """i18n 文件相对路径"""
        module_snake = config.module.replace("-", "_")
        base = "frontend/apps/web-antd/src/locales/langs"

        if filename == "source_zh.json":
            return f"{base}/zh-CN/{scope}/{module_snake}.json"
        elif filename == "source_en.json":
            return f"{base}/en-US/{scope}/{module_snake}.json"
        elif filename == "backend_messages_zh.json":
            return f"backend/app/locales/zh_CN/_{module_snake}.json"
        return f"{base}/{scope}/{filename}"

    # ---- 模板选择 ----

    def _get_index_template(self, config: CrudConfig) -> str:
        """根据 LayoutVariant 选择前端 index 模板"""
        variant = config.layout.variant
        template_name = _LAYOUT_TEMPLATE_MAP.get(variant, "index.vue.j2")
        return f"frontend/{template_name}"

    # ---- 渲染单个模板 ----

    def _render(self, template_path: str, ctx: dict[str, Any]) -> str:
        try:
            tmpl = self._env.get_template(template_path)
            return tmpl.render(**ctx)
        except TemplateError as e:
            logger.error("Template render failed: %s — %s", template_path, e)
            raise

    # ---- 生成后端文件 ----

    def _generate_backend(
        self,
        config: CrudConfig,
        scopes: list[str],
        files: dict[str, str],
    ) -> None:
        module_snake = config.module.replace("-", "_")

        # 枚举（不区分 scope）
        if config.enums:
            ctx = self._build_context(config, scopes[0])
            content = self._render("backend/enum.py.j2", ctx)
            files[f"backend/app/enums/{module_snake}.py"] = content

        for scope in scopes:
            ctx = self._build_context(config, scope)

            # Model（只生成一份，不按 scope 区分）
            if scope == scopes[0]:
                content = self._render("backend/model.py.j2", ctx)
                category = config.parent_menu
                files[f"backend/app/models/{category}/{module_snake}.py"] = content

                # Schema
                content = self._render("backend/schema.py.j2", ctx)
                files[f"backend/app/schemas/{category}/{module_snake}.py"] = content

                # Repository
                content = self._render("backend/repository.py.j2", ctx)
                files[f"backend/app/repositories/{category}/{module_snake}_repository.py"] = content

                # Service
                content = self._render("backend/service.py.j2", ctx)
                files[f"backend/app/services/{category}/{module_snake}_service.py"] = content

            # Controller（按 scope 生成）
            content = self._render("backend/controller.py.j2", ctx)
            module_plural = _pluralize(module_snake)
            files[f"backend/app/api/{scope}/{module_plural}.py"] = content

            # Test scaffold
            content = self._render("backend/test_api.py.j2", ctx)
            files[f"backend/tests/api/test_{scope}_{module_plural}.py"] = content

    # ---- 生成前端文件 ----

    def _generate_frontend(
        self,
        config: CrudConfig,
        scopes: list[str],
        files: dict[str, str],
    ) -> None:
        index_template = self._get_index_template(config)

        for scope in scopes:
            ctx = self._build_context(config, scope)

            # api.ts
            content = self._render("frontend/api.ts.j2", ctx)
            files[self._frontend_path(config, scope, "api.ts")] = content

            # data.ts
            content = self._render("frontend/data.ts.j2", ctx)
            files[self._frontend_path(config, scope, "data.ts")] = content

            # index.vue (layout variant)
            content = self._render(index_template, ctx)
            files[self._frontend_path(config, scope, "index.vue")] = content

            # form.vue
            content = self._render("frontend/form.vue.j2", ctx)
            files[self._frontend_path(config, scope, "form.vue")] = content

    # ---- 生成 i18n 文件 ----

    def _generate_i18n(
        self,
        config: CrudConfig,
        scopes: list[str],
        files: dict[str, str],
    ) -> None:
        for scope in scopes:
            # 前端中文 i18n
            data_zh = self._build_frontend_i18n_zh(config)
            files[self._i18n_path(config, scope, "source_zh.json")] = _to_json(data_zh)

            # 前端英文 i18n
            data_en = self._build_frontend_i18n_en(config)
            files[self._i18n_path(config, scope, "source_en.json")] = _to_json(data_en)

        # 后端 messages（只生成一份，中文 + 英文）
        module_snake = config.module.replace("-", "_")
        files[f"backend/app/locales/zh_CN/_{module_snake}.json"] = _to_json(
            self._build_backend_messages_zh(config)
        )
        files[f"backend/app/locales/en_US/_{module_snake}.json"] = _to_json(
            self._build_backend_messages_en(config)
        )

    @staticmethod
    def _build_frontend_i18n_zh(config: CrudConfig) -> dict[str, object]:
        dn = config.display_name
        data: dict[str, object] = {
            "title": f"{dn}管理",
            "pageDesc": f"管理{dn}数据，支持新建、编辑、删除等操作。",
            "create": f"新建{dn}",
            "edit": f"编辑{dn}",
            "detail": f"{dn}详情",
            "search": f"搜索{dn}",
            "selectToView": "请选择一条记录查看详情",
            "confirmDelete": f"确认删除此{dn}？",
        }

        # field labels
        field_map: dict[str, str] = {}
        for f in config.fields:
            field_map[f.name] = f.label_zh
        if config.has_status_toggle:
            field_map["isActive"] = "是否启用"
        if config.drag_sort:
            field_map["sortOrder"] = "排序"
        data["field"] = field_map

        # placeholders
        ph: dict[str, str] = {}
        for f in config.fields:
            if f.searchable:
                ph[f"search{_capitalize_filter(f.name)}"] = f"请输入{f.label_zh}"
            elif f.in_form:
                ft = f.type.value
                if ft in ("string", "text"):
                    ph[f"input{_capitalize_filter(f.name)}"] = f"请输入{f.label_zh}"
                elif ft == "enum" or f.form_component.value == "Select":
                    ph[f"select{_capitalize_filter(f.name)}"] = f"请选择{f.label_zh}"
        data["placeholder"] = ph

        # enums
        if config.enums:
            enum_map: dict[str, dict[str, str]] = {}
            for enum in config.enums:
                key = _snake_filter(enum.name)
                enum_map[key] = {opt.value: opt.label_zh for opt in enum.values}
            data["enum"] = enum_map

        # messages
        messages: dict[str, str] = {
            "createSuccess": f"{dn}创建成功",
            "updateSuccess": f"{dn}更新成功",
            "deleteSuccess": f"{dn}已删除",
        }
        if config.has_status_toggle:
            messages["toggleStatusSuccess"] = "状态切换成功"
        data["messages"] = messages

        return data

    @staticmethod
    def _build_frontend_i18n_en(config: CrudConfig) -> dict[str, object]:
        dn = config.display_name_en
        data: dict[str, object] = {
            "title": f"{dn} Management",
            "pageDesc": f"Manage {dn} data, including create, edit, and delete operations.",
            "create": f"Create {dn}",
            "edit": f"Edit {dn}",
            "detail": f"{dn} Details",
            "search": f"Search {dn}",
            "selectToView": "Select a record to view details",
            "confirmDelete": f"Are you sure you want to delete this {dn}?",
        }

        field_map: dict[str, str] = {}
        for f in config.fields:
            field_map[f.name] = f.label_en
        if config.has_status_toggle:
            field_map["isActive"] = "Active"
        if config.drag_sort:
            field_map["sortOrder"] = "Sort Order"
        data["field"] = field_map

        ph: dict[str, str] = {}
        for f in config.fields:
            if f.searchable:
                ph[f"search{_capitalize_filter(f.name)}"] = f"Search {f.label_en}"
            elif f.in_form:
                ft = f.type.value
                if ft in ("string", "text"):
                    ph[f"input{_capitalize_filter(f.name)}"] = f"Enter {f.label_en}"
                elif ft == "enum" or f.form_component.value == "Select":
                    ph[f"select{_capitalize_filter(f.name)}"] = f"Select {f.label_en}"
        data["placeholder"] = ph

        if config.enums:
            enum_map: dict[str, dict[str, str]] = {}
            for enum in config.enums:
                key = _snake_filter(enum.name)
                enum_map[key] = {opt.value: opt.label_en for opt in enum.values}
            data["enum"] = enum_map

        messages: dict[str, str] = {
            "createSuccess": f"{dn} created successfully",
            "updateSuccess": f"{dn} updated successfully",
            "deleteSuccess": f"{dn} deleted",
        }
        if config.has_status_toggle:
            messages["toggleStatusSuccess"] = "Status toggled successfully"
        data["messages"] = messages

        return data

    @staticmethod
    def _build_backend_messages_zh(config: CrudConfig) -> dict[str, object]:
        dn = config.display_name
        module_snake = config.module.replace("-", "_")
        error: dict[str, str] = {
            "not_found": f"{dn}不存在",
            "name_exists": f"{dn}名称已存在",
            "create_failed": f"{dn}创建失败",
            "update_failed": f"{dn}更新失败",
            "delete_failed": f"{dn}删除失败",
        }
        if config.has_status_toggle:
            error["toggle_failed"] = "状态切换失败"

        return {
            module_snake: {
                "not_found": f"{dn}不存在",
                "created": f"{dn}创建成功",
                "updated": f"{dn}更新成功",
                "deleted": f"{dn}删除成功",
                "error": error,
                "field": {f.name: f.label_zh for f in config.fields},
            }
        }

    @staticmethod
    def _build_backend_messages_en(config: CrudConfig) -> dict[str, object]:
        dn = config.display_name_en
        module_snake = config.module.replace("-", "_")
        error: dict[str, str] = {
            "not_found": f"{dn} not found",
            "name_exists": f"{dn} name already exists",
            "create_failed": f"Failed to create {dn}",
            "update_failed": f"Failed to update {dn}",
            "delete_failed": f"Failed to delete {dn}",
        }
        if config.has_status_toggle:
            error["toggle_failed"] = "Failed to toggle status"

        return {
            module_snake: {
                "not_found": f"{dn} not found",
                "created": f"{dn} created successfully",
                "updated": f"{dn} updated successfully",
                "deleted": f"{dn} deleted successfully",
                "error": error,
                "field": {f.name: f.label_en for f in config.fields},
            }
        }

    # ---- DDL 预览 ----

    @staticmethod
    def generate_ddl_preview(config: CrudConfig) -> str:
        """从 CrudConfig 推导 CREATE TABLE SQL（PostgreSQL 方言）"""
        module_snake = config.module.replace("-", "_")
        table_name = config.table_name

        type_map: dict[str, str] = {
            "string": "VARCHAR({length})",
            "text": "TEXT",
            "integer": "INTEGER",
            "float": "DOUBLE PRECISION",
            "decimal": "NUMERIC(10,2)",
            "boolean": "BOOLEAN NOT NULL DEFAULT FALSE",
            "datetime": "TIMESTAMP WITH TIME ZONE",
            "date": "DATE",
            "json": "JSONB",
            "enum": "VARCHAR(50)",
            "file": "VARCHAR(500)",
        }

        lines: list[str] = [f"CREATE TABLE {table_name} ("]
        lines.append("    id SERIAL PRIMARY KEY,")

        # tenant_id
        if config.scope in (ScopeType.TENANT, ScopeType.BOTH):
            lines.append(
                "    tenant_id INTEGER NOT NULL REFERENCES tenants(id),"
            )

        # 字段
        for field in config.fields:
            ft = field.type.value
            sql_type = type_map.get(ft, "VARCHAR(255)")
            if ft == "string":
                length = field.max_length or 255
                sql_type = sql_type.format(length=length)

            nullable = "" if field.nullable else " NOT NULL"
            default = ""
            if field.default is not None:
                if ft == "boolean":
                    default = f" DEFAULT {str(field.default).upper()}"
                elif ft in ("string", "text", "enum"):
                    default = f" DEFAULT '{field.default}'"
                else:
                    default = f" DEFAULT {field.default}"

            lines.append(f"    {field.name} {sql_type}{nullable}{default},")

        # 关联外键
        for rel in config.relations:
            if rel.type.value == "belongs_to":
                fk_name = rel.foreign_key or f"{rel.name}_id"
                not_null = " NOT NULL" if not rel.nullable else ""
                lines.append(
                    f"    {fk_name} INTEGER{not_null} REFERENCES {rel.target_table}(id),"
                )

        # is_active
        if config.has_status_toggle:
            lines.append("    is_active BOOLEAN NOT NULL DEFAULT TRUE,")

        # sort_order
        if config.drag_sort:
            lines.append("    sort_order INTEGER NOT NULL DEFAULT 0,")

        # 基础字段
        lines.append("    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,")
        lines.append("    deleted_at TIMESTAMP WITH TIME ZONE,")
        lines.append("    delete_level VARCHAR(20),")
        lines.append("    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),")
        lines.append("    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()")
        lines.append(");")

        # 索引
        if config.scope in (ScopeType.TENANT, ScopeType.BOTH):
            lines.append(
                f"\nCREATE INDEX ix_{table_name}_tenant_id ON {table_name}(tenant_id);"
            )
        lines.append(
            f"CREATE INDEX ix_{table_name}_is_deleted ON {table_name}(is_deleted);"
        )
        lines.append(
            f"CREATE INDEX ix_{table_name}_created_at ON {table_name}(created_at);"
        )

        for idx in config.indexes:
            idx_name = idx.name or f"ix_{table_name}_{'_'.join(idx.fields)}"
            unique = "UNIQUE " if idx.unique else ""
            cols = ", ".join(idx.fields)
            lines.append(f"CREATE {unique}INDEX {idx_name} ON {table_name}({cols});")

        return "\n".join(lines)

    # ---- Alembic 迁移脚本生成 ----

    @staticmethod
    def _generate_revision_id(module_snake: str) -> str:
        """生成 Alembic revision ID: 日期前缀 + 短随机后缀"""
        date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        short_hash = uuid.uuid4().hex[:12]
        return f"{date_prefix}_{short_hash}"

    @staticmethod
    def _field_to_sa_type(field: FieldConfig) -> str:
        """将 FieldConfig 映射为 SQLAlchemy 类型表达式字符串"""
        ft = field.type.value
        sa_map: dict[str, str] = {
            "string": f"sa.String(length={field.max_length or 255})",
            "text": "sa.Text()",
            "integer": "sa.Integer()",
            "float": "sa.Float()",
            "decimal": "sa.Numeric(precision=10, scale=2)",
            "boolean": "sa.Boolean()",
            "datetime": "sa.DateTime()",
            "date": "sa.Date()",
            "json": "sa.JSON()",
            "enum": "sa.String(length=50)",
            "file": "sa.String(length=500)",
        }
        return sa_map.get(ft, "sa.String(length=255)")

    def generate_migration(
        self,
        config: CrudConfig,
        *,
        down_revision: str | None = None,
    ) -> tuple[str, str]:
        """从 CrudConfig 生成 Alembic 迁移脚本（create table）

        Args:
            config: CRUD 配置
            down_revision: 上游 revision ID（None 表示新链）

        Returns:
            (relative_path, content) 元组
        """
        module_snake = config.module.replace("-", "_")
        scope = config.scope.value
        revision_id = self._generate_revision_id(module_snake)
        create_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        ctx = self._build_context(config, scope if scope != "both" else "tenant")
        ctx.update({
            "revision_id": revision_id,
            "down_revision": down_revision,
            "create_date": create_date,
        })

        content = self._render("backend/migration.py.j2", ctx)
        rel_path = f"backend/migrations/versions/crud/{revision_id}_create_{config.table_name}.py"
        return rel_path, content

    # ---- 增量迁移脚本生成 ----

    def generate_incremental_migration(
        self,
        old_config: CrudConfig,
        new_config: CrudConfig,
        *,
        down_revision: str | None = None,
    ) -> tuple[str, str]:
        """比较两个 CrudConfig，生成增量 Alembic 迁移脚本

        Args:
            old_config: 变更前的 CrudConfig
            new_config: 变更后的 CrudConfig
            down_revision: 上游 revision ID

        Returns:
            (relative_path, content) 元组
        """
        module_snake = new_config.module.replace("-", "_")
        revision_id = self._generate_revision_id(module_snake)
        create_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        old_fields = {f.name: f for f in old_config.fields}
        new_fields = {f.name: f for f in new_config.fields}

        added_columns: list[dict[str, object]] = []
        dropped_columns: list[dict[str, object]] = []
        altered_columns: list[dict[str, object]] = []

        # 新增字段
        for name, field in new_fields.items():
            if name not in old_fields:
                added_columns.append({
                    "name": name,
                    "sa_type": self._field_to_sa_type(field),
                    "nullable": not field.required,
                    "server_default": field.default or "",
                    "comment": field.label_en,
                })

        # 删除字段
        for name, field in old_fields.items():
            if name not in new_fields:
                dropped_columns.append({
                    "name": name,
                    "sa_type": self._field_to_sa_type(field),
                    "nullable": not field.required,
                    "server_default": field.default or "",
                    "comment": field.label_en,
                })

        # 变更字段（类型或 nullable 变化）
        for name in new_fields:
            if name in old_fields:
                old_f = old_fields[name]
                new_f = new_fields[name]
                old_type = self._field_to_sa_type(old_f)
                new_type = self._field_to_sa_type(new_f)
                old_nullable = not old_f.required
                new_nullable = not new_f.required
                if old_type != new_type or old_nullable != new_nullable:
                    altered_columns.append({
                        "name": name,
                        "old_type": old_type,
                        "new_type": new_type,
                        "old_nullable": old_nullable,
                        "new_nullable": new_nullable,
                    })

        # 索引差异
        old_idx = {(idx.name or "_".join(idx.fields)): idx for idx in old_config.indexes}
        new_idx = {(idx.name or "_".join(idx.fields)): idx for idx in new_config.indexes}

        added_indexes: list[dict[str, object]] = []
        dropped_indexes: list[dict[str, object]] = []

        for key, idx in new_idx.items():
            if key not in old_idx:
                idx_name = idx.name or f"ix_{new_config.table_name}_{'_'.join(idx.fields)}"
                added_indexes.append({
                    "name": idx_name,
                    "columns": idx.fields,
                    "unique": idx.unique,
                })

        for key, idx in old_idx.items():
            if key not in new_idx:
                idx_name = idx.name or f"ix_{old_config.table_name}_{'_'.join(idx.fields)}"
                dropped_indexes.append({
                    "name": idx_name,
                    "columns": idx.fields,
                    "unique": idx.unique,
                })

        # 无变更则返回空
        if not (added_columns or dropped_columns or altered_columns
                or added_indexes or dropped_indexes):
            return "", ""

        ctx = {
            "table_name": new_config.table_name,
            "module": new_config.module,
            "revision_id": revision_id,
            "down_revision": down_revision,
            "create_date": create_date,
            "added_columns": added_columns,
            "dropped_columns": dropped_columns,
            "altered_columns": altered_columns,
            "added_indexes": added_indexes,
            "dropped_indexes": dropped_indexes,
        }

        content = self._render("backend/migration_alter.py.j2", ctx)
        rel_path = f"backend/migrations/versions/crud/{revision_id}_alter_{new_config.table_name}.py"
        return rel_path, content

    # ---- 主入口 ----

    def generate(
        self,
        config: CrudConfig,
        *,
        down_revision: str | None = None,
    ) -> dict[str, str]:
        """从 CrudConfig 生成全部文件

        Args:
            config: CRUD 配置
            down_revision: Alembic 迁移上游 revision ID

        Returns:
            dict[str, str]: {相对路径: 文件内容}
        """
        # 确定生成范围
        if config.scope == ScopeType.BOTH:
            scopes = ["tenant", "admin"]
        elif config.scope == ScopeType.ADMIN:
            scopes = ["admin"]
        else:
            scopes = ["tenant"]

        files: dict[str, str] = {}

        self._generate_backend(config, scopes, files)
        self._generate_frontend(config, scopes, files)
        self._generate_i18n(config, scopes, files)

        # Alembic 迁移脚本（替代 DDL 预览）
        mig_path, mig_content = self.generate_migration(
            config, down_revision=down_revision,
        )
        files[mig_path] = mig_content

        # DDL 预览保留（向后兼容，前端预览可能仍需要）
        files["__ddl_preview__.sql"] = self.generate_ddl_preview(config)

        return files

