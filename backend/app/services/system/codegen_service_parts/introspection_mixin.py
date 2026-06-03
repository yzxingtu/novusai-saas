"""Introspection concerns for CodegenService. / CodegenService 数据反射职责。"""

from __future__ import annotations

from typing import Any

from app.codegen.db_introspector import DbIntrospector


class CodegenIntrospectionMixin:
    """Introspection mixin / 数据库反射混入。"""

    def get_table_names(self) -> list[str]:
        """获取所有表名（白名单校验用）/ Get all table names for whitelist validation."""
        intro = DbIntrospector()
        return intro.get_table_names()

    def introspect_tables(self) -> list[dict[str, Any]]:
        """列出数据库所有表 / List all DB tables."""
        intro = DbIntrospector()
        names = intro.get_table_names()
        result = []
        for name in names:
            result.append(
                {
                    "name": name,
                    "comment": None,
                    "row_count": intro.get_row_count_estimate(name),
                    "has_model": intro.has_model(name),
                }
            )
        return result

    def introspect_columns(self, table_name: str) -> list[dict[str, Any]]:
        """获取表的列定义 / Get table column definitions."""
        intro = DbIntrospector()
        cols = intro.get_columns(table_name)
        return [
            {
                "name": c.name,
                "type": c.type,
                "nullable": c.nullable,
                "default": c.default,
                "primary_key": c.primary_key,
                "unique": c.unique,
                "comment": c.comment,
                "foreign_keys": c.foreign_keys,
                "suggested_config": c.suggested_config,
            }
            for c in cols
        ]

    def introspect_rows(
        self,
        table_name: str,
        value_field: str = "id",
        display_field: str = "name",
        limit: int = 200,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        获取表行数据（供关联下拉预览）/ Get table rows for relation select preview.

        Returns:
            {"items": [{"value": ..., "label": ...}, ...], "total": int}
        """
        intro = DbIntrospector()
        items = intro.get_table_rows(
            table_name=table_name,
            value_field=value_field,
            display_field=display_field,
            limit=limit,
            search=search,
        )
        return {"items": items, "total": len(items)}

    def import_from_table(self, table_name: str) -> dict[str, Any]:
        """
        从 DB 表导入为配置 JSON / Import from DB table to config JSON.

        Returns:
            包含 module, resource, fields 等的配置片段
        """
        cols = self.introspect_columns(table_name)
        resource = table_name
        if len(table_name) > 1:
            if table_name.endswith("ies") and len(table_name) > 3:
                resource = table_name[:-3] + "y"
            elif table_name.endswith(("ses", "xes", "ches", "shes")):
                resource = table_name[:-2]
            elif table_name.endswith("s") and not table_name.endswith("ss"):
                resource = table_name[:-1]
        fields = []
        for c in cols:
            fields.append(
                {
                    "name": c["name"],
                    **c.get("suggested_config", {}),
                }
            )
        return {
            "resource": resource,
            "module": "system",
            "fields": fields,
        }
