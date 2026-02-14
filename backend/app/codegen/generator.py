"""
CRUD 代码生成器 — Generator 核心

从 CrudConfig 生成全部文件内容（dict[filepath, content]）。
- 加载 Jinja2 模板
- 构建渲染上下文
- 按 scope/layout 选择模板
- 输出 {相对路径: 文件内容} 字典
"""

from __future__ import annotations

import os
import re
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError

from app.core.logging import LogManager

logger = LogManager.get_logger("app")

from app.codegen.batch_deps import resolve_generation_order
from app.codegen.schemas import (
    BatchCrudProject,
    CrudConfig,
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

        if filename == "api.ts":
            return f"{base}/api/{scope}/{module_kebab}s.ts"
        elif filename == "data.ts":
            return f"{base}/views/{scope}/{parent}/{module_kebab}s/data.ts"
        elif filename.startswith("index"):
            return f"{base}/views/{scope}/{parent}/{module_kebab}s/index.vue"
        elif filename == "form.vue":
            return f"{base}/views/{scope}/{parent}/{module_kebab}s/modules/form.vue"
        return f"{base}/views/{scope}/{parent}/{module_kebab}s/{filename}"

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
            files[f"backend/app/api/{scope}/{module_snake}s.py"] = content

            # Test scaffold
            content = self._render("backend/test_api.py.j2", ctx)
            files[f"backend/tests/api/test_{scope}_{module_snake}s.py"] = content

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
            ctx = self._build_context(config, scope)

            # 前端中文 i18n
            content = self._render("i18n/source_zh.json.j2", ctx)
            files[self._i18n_path(config, scope, "source_zh.json")] = content

            # 前端英文 i18n
            content = self._render("i18n/source_en.json.j2", ctx)
            files[self._i18n_path(config, scope, "source_en.json")] = content

        # 后端 messages（只生成一份）
        ctx = self._build_context(config, scopes[0])
        content = self._render("i18n/backend_messages_zh.json.j2", ctx)
        module_snake = config.module.replace("-", "_")
        files[f"backend/app/locales/zh_CN/_{module_snake}.json"] = content

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

    # ---- 主入口 ----

    def generate(self, config: CrudConfig) -> dict[str, str]:
        """从 CrudConfig 生成全部文件

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

        # DDL 预览（作为特殊文件）
        files["__ddl_preview__.sql"] = self.generate_ddl_preview(config)

        return files

    # ================================================================
    # 多表批量生成
    # ================================================================

    @staticmethod
    def _inject_cross_relations(project: BatchCrudProject) -> None:
        """将 cross_relations 注入到对应实体的 CrudConfig.relations"""
        entity_map = {e.module: e for e in project.entities}

        for rel in project.cross_relations:
            source = entity_map.get(rel.source_entity)
            target = entity_map.get(rel.target_entity)
            if not source or not target:
                logger.warning(
                    "cross_relation references unknown entity: %s → %s",
                    rel.source_entity,
                    rel.target_entity,
                )
                continue

            # 避免重复注入
            existing_names = {r.name for r in source.relations}
            if rel.target_entity in existing_names:
                continue

            target_model = _pascal_filter(target.module.replace("-", "_"))
            source.relations.append(RelationConfig(
                name=rel.target_entity.replace("-", "_"),
                type=rel.relation_type,
                target_model=target_model,
                target_table=target.table_name,
                foreign_key=rel.foreign_key,
                nullable=rel.nullable,
            ))

    def _merge_i18n_files(
        self,
        all_files: dict[str, str],
        entity_files: dict[str, str],
    ) -> None:
        """合并 i18n JSON 文件（同路径的 JSON 做深合并）"""
        import json as _json

        for path, content in entity_files.items():
            if path not in all_files:
                all_files[path] = content
                continue

            # 仅对 JSON 文件做合并
            if not path.endswith(".json"):
                all_files[path] = content
                continue

            try:
                existing = _json.loads(all_files[path])
                new = _json.loads(content)
                if isinstance(existing, dict) and isinstance(new, dict):
                    merged = self._deep_merge_overlay(existing, new)
                    all_files[path] = _json.dumps(
                        merged, ensure_ascii=False, indent=2
                    )
                else:
                    all_files[path] = content
            except (ValueError, TypeError):
                all_files[path] = content

    @staticmethod
    def _deep_merge_overlay(base: dict, overlay: dict) -> dict:
        """深度合并字典，overlay 的叶子值覆盖 base

        与 writer._deep_merge (base 优先) 语义不同，此处 overlay 优先，
        用于批量生成时逐实体累积 i18n 数据。
        """
        result = dict(base)
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = CrudGenerator._deep_merge_overlay(result[key], value)
            else:
                result[key] = value
        return result

    def generate_batch(self, project: BatchCrudProject) -> dict[str, str]:
        """从 BatchCrudProject 批量生成全部文件

        处理：
        1. 注入跨表关联到各实体 relations
        2. 按依赖顺序逐实体调用 generate()
        3. 合并 i18n JSON（同路径深合并）
        4. 生成联合 DDL 预览

        Returns:
            dict[str, str]: {相对路径: 文件内容}
            附带元数据 __entity_file_map__（JSON）记录每个文件属于哪个实体
        """
        # 1. 注入跨表关联
        self._inject_cross_relations(project)

        # 2. 按依赖排序（使用拓扑排序引擎）
        resolved_modules = resolve_generation_order(project)
        entity_map = {e.module: e for e in project.entities}
        ordered = [entity_map[m] for m in resolved_modules if m in entity_map]

        # 3. 逐实体生成并合并
        all_files: dict[str, str] = {}
        entity_file_map: dict[str, str] = {}  # path → entity module
        ddl_parts: list[str] = []

        for entity in ordered:
            entity_files = self.generate(entity)

            # 提取并移除单表 DDL
            entity_ddl = entity_files.pop("__ddl_preview__.sql", "")
            if entity_ddl:
                ddl_parts.append(
                    f"-- ========== {entity.display_name} ({entity.table_name}) ==========\n"
                    + entity_ddl
                )

            # 记录文件归属
            for path in entity_files:
                entity_file_map[path] = entity.module

            # 合并（i18n 做深合并，其他直接覆盖）
            self._merge_i18n_files(all_files, entity_files)

        # 4. 联合 DDL 预览
        if ddl_parts:
            header = (
                f"-- 联合 DDL 预览 ({len(ordered)} tables)\n"
                f"-- 按依赖顺序排列\n\n"
            )
            all_files["__ddl_preview__.sql"] = header + "\n\n".join(ddl_parts)

        # 5. 元数据（供 Writer 按实体分组预览）
        import json as _json
        all_files["__entity_file_map__.json"] = _json.dumps(
            entity_file_map, ensure_ascii=False
        )

        return all_files
