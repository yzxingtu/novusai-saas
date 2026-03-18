"""
数据库表反射器 / DB Introspector

从数据库元数据反射表结构，供代码生成器导入使用
Reflects table structure from DB metadata for codegen import.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from sqlalchemy import String, Text, inspect
from sqlalchemy.engine import Engine

from app.core.database import sync_engine
from app.core.base_model import Base
from app.codegen.type_registry import type_registry

# BaseModel 基类字段（反射时排除）/ BaseModel base fields (exclude from introspection)
_BASE_MODEL_FIELDS = frozenset(
    {"id", "created_at", "updated_at", "is_deleted", "deleted_at", "delete_level", "remark", "sort_order"}
)
# TenantModel 额外字段 / TenantModel extra fields
_TENANT_MODEL_FIELDS = frozenset({"tenant_id"})


@dataclass
class ColumnInfo:
    """列信息 / Column info."""

    name: str
    type: str
    nullable: bool
    default: str | None
    primary_key: bool
    foreign_keys: list[dict[str, Any]]
    unique: bool
    comment: str | None
    suggested_config: dict[str, Any]


@dataclass
class FKInfo:
    """外键信息 / Foreign key info."""

    name: str
    constrained_columns: list[str]
    referred_table: str
    referred_columns: list[str]


@dataclass
class UniqueConstraintInfo:
    """唯一约束信息 / Unique constraint info."""

    name: str
    columns: list[str]


class DbIntrospector:
    """
    数据库表反射器 / DB table introspector.

    使用 sqlalchemy.inspect() 获取表结构
    Uses sqlalchemy.inspect() to get table structure.
    """

    def __init__(self, engine: Engine | None = None):
        """
        Args:
            engine: 同步数据库引擎，默认使用 sync_engine
        """
        self.engine = engine or sync_engine

    def get_table_names(self) -> list[str]:
        """
        获取所有表名 / Get all table names.

        Returns:
            表名列表
        """
        inspector = inspect(self.engine)
        return inspector.get_table_names()

    def get_row_count_estimate(self, table_name: str) -> int:
        """
        获取表行数估算（pg_class.reltuples）/ Get estimated row count from pg_class.

        Args:
            table_name: 表名

        Returns:
            估算行数，无法获取时返回 0
        """
        try:
            from sqlalchemy import text

            with self.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT reltuples::bigint FROM pg_class WHERE relname = :name"),
                    {"name": table_name},
                ).fetchone()
                if row and row[0] is not None:
                    return max(0, int(row[0]))
        except Exception:
            pass
        return 0

    def get_columns(self, table_name: str) -> list[ColumnInfo]:
        """
        获取表的列定义 / Get column definitions for table.

        排除 BaseModel/TenantModel 基类字段
        Excludes BaseModel/TenantModel base fields.

        Args:
            table_name: 表名

        Returns:
            ColumnInfo 列表，含 suggested_config（供 YAML 导入）
        """
        inspector = inspect(self.engine)
        excluded = _BASE_MODEL_FIELDS | _TENANT_MODEL_FIELDS

        raw_columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name) or {}
        pk_cols = {c for c in (pk_constraint.get("constrained_columns") or [])}
        unique_cols: set[str] = set()
        for uq in inspector.get_unique_constraints(table_name):
            cols = uq.get("column_names") or []
            if len(cols) == 1:
                unique_cols.add(cols[0])
        fks = inspector.get_foreign_keys(table_name)
        fk_map: dict[str, list[dict[str, Any]]] = {}
        for fk in fks:
            for col in fk.get("constrained_columns") or []:
                fk_map.setdefault(col, []).append(
                    {
                        "referred_table": fk.get("referred_table", ""),
                        "referred_columns": fk.get("referred_columns") or [],
                    }
                )

        result: list[ColumnInfo] = []
        for col in raw_columns:
            name = col["name"]
            if name in excluded:
                continue
            sa_type = col.get("type")
            col_wrapper = SimpleNamespace(type=sa_type) if sa_type else None
            yaml_type = (type_registry.reverse_map(col_wrapper) or "String") if col_wrapper else "String"
            if yaml_type == "String" and sa_type and hasattr(sa_type, "length") and getattr(sa_type, "length", None):
                yaml_type = f"String({sa_type.length})"
            elif not yaml_type:
                yaml_type = "String"

            nullable = col.get("nullable", True)
            default = str(col["default"]) if col.get("default") is not None else None
            pk = name in pk_cols
            uq = name in unique_cols
            fk_list = fk_map.get(name, [])
            comment = col.get("comment")

            suggested: dict[str, Any] = {
                "type": yaml_type,
                "filterable": True,
                "filter_op": "ilike" if isinstance(sa_type, (String, Text)) else "eq",
            }
            if fk_list:
                ref_table = (fk_list[0].get("referred_table") or "").strip()
                suggested["type"] = f"ForeignKey({ref_table or 'unknown'})"
                suggested["form_component"] = "ApiSelect"
            if uq:
                suggested["unique"] = True
            if "String" in yaml_type and "(" in yaml_type:
                m = re.match(r"String\((\d+)\)", yaml_type)
                if m:
                    suggested["length"] = int(m.group(1))
            suggested["searchable"] = suggested.get("filterable", False)
            suggested["column"] = {"visible": True}

            result.append(
                ColumnInfo(
                    name=name,
                    type=str(sa_type) if sa_type else "VARCHAR",
                    nullable=nullable,
                    default=default,
                    primary_key=pk,
                    foreign_keys=fk_list,
                    unique=uq,
                    comment=comment,
                    suggested_config=suggested,
                )
            )
        return result

    def get_foreign_keys(self, table_name: str) -> list[FKInfo]:
        """获取外键 / Get foreign keys."""
        inspector = inspect(self.engine)
        result: list[FKInfo] = []
        for fk in inspector.get_foreign_keys(table_name):
            result.append(
                FKInfo(
                    name=fk.get("name", ""),
                    constrained_columns=fk.get("constrained_columns") or [],
                    referred_table=fk.get("referred_table", ""),
                    referred_columns=fk.get("referred_columns") or [],
                )
            )
        return result

    def get_unique_constraints(self, table_name: str) -> list[UniqueConstraintInfo]:
        """获取唯一约束 / Get unique constraints."""
        inspector = inspect(self.engine)
        result: list[UniqueConstraintInfo] = []
        for uq in inspector.get_unique_constraints(table_name):
            result.append(
                UniqueConstraintInfo(
                    name=uq.get("name", ""),
                    columns=uq.get("column_names") or [],
                )
            )
        return result

    def has_model(self, table_name: str) -> bool:
        """
        判断表是否已有 ORM 模型 / Check if table has ORM model.

        通过 Base.metadata.tables 检查
        """
        return table_name in Base.metadata.tables

    def get_table_rows(
        self,
        table_name: str,
        value_field: str,
        display_field: str,
        limit: int = 200,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取表行数据（用于关联下拉预览）/ Get table rows for relation select preview.

        仅返回 value_field 和 display_field 列，白名单校验列名
        Returns only value_field and display_field, validates column names against schema.

        Args:
            table_name: 表名
            value_field: 值列（默认 id）
            display_field: 显示列（下拉展示用）
            limit: 最多返回行数
            search: 可选，对 display_field 做 ILIKE 过滤

        Returns:
            [{"value": ..., "label": ...}, ...]
        """
        from sqlalchemy import text

        # 白名单校验：表名和列名必须存在于表定义中（用原始列名，含 id 等基字段）
        if table_name not in self.get_table_names():
            return []
        inspector = inspect(self.engine)
        raw_cols = inspector.get_columns(table_name)
        valid_cols = {c["name"] for c in raw_cols}
        if value_field not in valid_cols or display_field not in valid_cols:
            return []

        # 使用参数化避免 SQL 注入，列名/表名已白名单校验
        # 若表有 is_deleted 列则过滤软删除
        all_col_names = valid_cols
        has_is_deleted = "is_deleted" in all_col_names

        cols = [value_field, display_field]
        col_list = ", ".join(f'"{c}"' for c in cols)
        q = f'SELECT {col_list} FROM "{table_name}"'
        params: dict[str, Any] = {"limit": min(limit, 500)}
        conditions: list[str] = []
        if has_is_deleted:
            conditions.append('"is_deleted" = false')
        if search and search.strip():
            conditions.append(f'"{display_field}"::text ILIKE :search')
            params["search"] = f"%{search.strip()}%"
        if conditions:
            q += " WHERE " + " AND ".join(conditions)
        q += " ORDER BY 2 LIMIT :limit"

        with self.engine.connect() as conn:
            rows = conn.execute(text(q), params).fetchall()

        return [
            {"value": row[0], "label": str(row[1]) if row[1] is not None else ""}
            for row in rows
        ]


__all__ = ["DbIntrospector", "ColumnInfo", "FKInfo", "UniqueConstraintInfo"]
