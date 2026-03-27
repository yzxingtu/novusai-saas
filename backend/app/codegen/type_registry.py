"""
类型注册中心 / Type Registry

CRUD 代码生成器字段类型映射：YAML type -> Python/SQLAlchemy/TS 类型
Field type mapping for CRUD codegen: YAML type -> Python/SQLAlchemy/TS types.
"""

from __future__ import annotations

import re
from typing import Any

# SQLAlchemy 类型用于 reverse_map / SQLAlchemy types for reverse_map
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

try:
    from sqlalchemy import Time

    _HAS_TIME = True
except ImportError:
    _HAS_TIME = False

try:
    from sqlalchemy.dialects.postgresql import INTERVAL

    _HAS_INTERVAL = True
except ImportError:
    _HAS_INTERVAL = False

# 基础类型映射（不含参数） / Base type mapping (no params)
_TYPE_MAP: dict[str, dict[str, Any]] = {
    "String": {
        "python_type": "str",
        "sqlalchemy_type": "String",
        "ts_type": "string",
        "default_form_component": "input",
        "default_search_type": "input",
        "default_cell_render": None,
        "default_filter_op": "ilike",
    },
    "Text": {
        "python_type": "str",
        "sqlalchemy_type": "Text",
        "ts_type": "string",
        "default_form_component": "textarea",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": None,
    },
    "Integer": {
        "python_type": "int",
        "sqlalchemy_type": "Integer",
        "ts_type": "number",
        "default_form_component": "number",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
    "BigInteger": {
        "python_type": "int",
        "sqlalchemy_type": "BigInteger",
        "ts_type": "number",
        "default_form_component": "number",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
    "Float": {
        "python_type": "float",
        "sqlalchemy_type": "Float",
        "ts_type": "number",
        "default_form_component": "number",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
    "Boolean": {
        "python_type": "bool",
        "sqlalchemy_type": "Boolean",
        "ts_type": "boolean",
        "default_form_component": "switch",
        "default_search_type": "status_select",
        "default_cell_render": "CellSwitch",
        "default_filter_op": "eq",
    },
    "DateTime": {
        "python_type": "datetime",
        "sqlalchemy_type": "DateTime(timezone=True)",
        "ts_type": "string",
        "default_form_component": "date",
        "default_search_type": "date_range",
        "default_cell_render": "formatDate",
        "default_filter_op": "between",
    },
    "Date": {
        "python_type": "date",
        "sqlalchemy_type": "Date",
        "ts_type": "string",
        "default_form_component": "date",
        "default_search_type": "date_range",
        "default_cell_render": "formatDate",
        "default_filter_op": "between",
    },
    "JSON": {
        "python_type": "dict",
        "sqlalchemy_type": "JSON",
        "ts_type": "Record<string, unknown>",
        "default_form_component": "CodeEditor",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": None,
    },
    "Enum": {
        "python_type": "str",
        "sqlalchemy_type": "String(50)",
        "ts_type": "string",
        "default_form_component": "select",
        "default_search_type": "select",
        "default_cell_render": "CellTag",
        "default_filter_op": "eq",
    },
    "Decimal": {
        "python_type": "Decimal",
        "sqlalchemy_type": "Numeric(10,2)",
        "ts_type": "number",
        "default_form_component": "number",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
    "UUID": {
        "python_type": "str",
        "sqlalchemy_type": "String(36)",
        "ts_type": "string",
        "default_form_component": "input",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
    "ForeignKey": {
        "python_type": "int",
        "sqlalchemy_type": "Integer",
        "ts_type": "number",
        "default_form_component": "ApiSelect",
        "default_search_type": "ApiSelect",
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
    # 高级组件 / Advanced components
    "ImageUpload": {
        "python_type": "str",
        "sqlalchemy_type": "String(500)",
        "ts_type": "string",
        "default_form_component": "ImageUpload",
        "default_search_type": None,
        "default_cell_render": "CellImage",
        "default_filter_op": None,
    },
    "RichText": {
        "python_type": "str",
        "sqlalchemy_type": "Text",
        "ts_type": "string",
        "default_form_component": "RichText",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": None,
    },
    "FilePicker": {
        "python_type": "dict",
        "sqlalchemy_type": "JSON",
        "ts_type": "Record<string, unknown>[]",
        "default_form_component": "FilePicker",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": None,
    },
    "CronPicker": {
        "python_type": "str",
        "sqlalchemy_type": "String(100)",
        "ts_type": "string",
        "default_form_component": "CronPicker",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": None,
    },
    "IconPicker": {
        "python_type": "str",
        "sqlalchemy_type": "String(100)",
        "ts_type": "string",
        "default_form_component": "IconPicker",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": None,
    },
    "CodeEditor": {
        "python_type": "dict",
        "sqlalchemy_type": "JSON",
        "ts_type": "Record<string, unknown>",
        "default_form_component": "CodeEditor",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": None,
    },
    "Images": {
        "python_type": "list",
        "sqlalchemy_type": "JSON",
        "ts_type": "string[]",
        "default_form_component": "ImageUpload",
        "default_search_type": None,
        "default_cell_render": "CellImage",
        "default_filter_op": None,
    },
    "Image": {
        "python_type": "str",
        "sqlalchemy_type": "String(500)",
        "ts_type": "string",
        "default_form_component": "ImageUpload",
        "default_search_type": None,
        "default_cell_render": "CellImage",
        "default_filter_op": None,
    },
    "File": {
        "python_type": "str",
        "sqlalchemy_type": "String(500)",
        "ts_type": "string",
        "default_form_component": "FilePicker",
        "default_search_type": None,
        "default_cell_render": "CellLink",
        "default_filter_op": None,
    },
    "Files": {
        "python_type": "list",
        "sqlalchemy_type": "JSON",
        "ts_type": "string[]",
        "default_form_component": "FilePicker",
        "default_search_type": None,
        "default_cell_render": "CellLink",
        "default_filter_op": None,
    },
    # 扩充表单组件 / Extended form components (P1a)
    "TreeSelect": {
        "python_type": "int",
        "sqlalchemy_type": "Integer",
        "ts_type": "number",
        "default_form_component": "ApiTreeSelect",
        "default_search_type": "ApiSelect",
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
    "Cascader": {
        "python_type": "str",
        "sqlalchemy_type": "String(200)",
        "ts_type": "string",
        "default_form_component": "Cascader",
        "default_search_type": None,
        "default_cell_render": None,
        "default_filter_op": None,
    },
    "UserSelect": {
        "python_type": "int",
        "sqlalchemy_type": "Integer",
        "ts_type": "number",
        "default_form_component": "ApiSelect",
        "default_search_type": "ApiSelect",
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
    "DeptSelect": {
        "python_type": "int",
        "sqlalchemy_type": "Integer",
        "ts_type": "number",
        "default_form_component": "ApiTreeSelect",
        "default_search_type": "ApiSelect",
        "default_cell_render": None,
        "default_filter_op": "eq",
    },
}

# reverse_map: SQLAlchemy 列类型 -> YAML type / SA column type -> YAML type
_REVERSE_MAP: dict[type, str] = {
    String: "String",
    Text: "Text",
    Integer: "Integer",
    BigInteger: "BigInteger",
    Float: "Float",
    Boolean: "Boolean",
    DateTime: "DateTime",
    Date: "Date",
    Numeric: "Decimal",
    JSONB: "JSON",
}
# 尝试导入 JSON（非 PostgreSQL 使用）/ Try import JSON (non-Pg)
try:
    from sqlalchemy import JSON

    _REVERSE_MAP[JSON] = "JSON"
except ImportError:
    pass

# PostgreSQL 扩展类型 / PostgreSQL extension types
_REVERSE_MAP[ARRAY] = "JSON"  # ARRAY 退化为 JSON 存储 / ARRAY fallback to JSON
if _HAS_TIME:
    _REVERSE_MAP[Time] = "String"  # Time 退化为 String / Time fallback to String
if _HAS_INTERVAL:
    _REVERSE_MAP[INTERVAL] = "String"  # Interval 退化为 String / Interval fallback to String


def _parse_type(yaml_type: str) -> tuple[str, dict[str, Any]]:
    """
    解析 YAML type 字符串，返回 (base_type, params)。
    Parse YAML type string, return (base_type, params).

    支持 / Supports: String(100), Decimal(10,2), ForeignKey(users)
    """
    base = yaml_type
    params: dict[str, Any] = {}

    # String(N) / 定长字符串类型
    m = re.match(r"^String\s*\(\s*(\d+)\s*\)$", yaml_type, re.I)
    if m:
        return "String", {"length": int(m.group(1))}

    # Decimal(P,S) / 定点小数精度与标度
    m = re.match(r"^Decimal\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)$", yaml_type, re.I)
    if m:
        return "Decimal", {"precision": int(m.group(1)), "scale": int(m.group(2))}

    # ForeignKey(table) / 外键引用表名
    m = re.match(r"^ForeignKey\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)$", yaml_type, re.I)
    if m:
        return "ForeignKey", {"table": m.group(1)}

    # Enum(a, b, c) - 保留 values 参数 / Enum(a,b,c) - retain values
    em = re.match(r"^Enum\s*\(\s*(.+)\s*\)\s*$", yaml_type, re.I)
    if em:
        vals_str = em.group(1).strip()
        params["values"] = [v.strip().strip("'\"").strip() for v in vals_str.split(",") if v.strip()]
        return "Enum", params

    return base, params


class TypeRegistry:
    """
    类型注册中心 / Type registry.

    模块级单例，映射 YAML 字段类型到各端类型及默认组件
    Module-level singleton, maps YAML field types to platform types and default components.
    """

    _instance: TypeRegistry | None = None

    def __new__(cls) -> TypeRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_type_map(self) -> dict[str, dict[str, Any]]:
        """
        获取类型映射表（供 API/外部查询）/ Get type map for API or external inspection.
        """
        return _TYPE_MAP

    def is_type_registered(self, yaml_type: str) -> bool:
        """检查类型是否已注册 / Check if type is registered (base in _TYPE_MAP)."""
        base, _ = _parse_type(str(yaml_type or ""))
        return base in _TYPE_MAP

    def get_type_info(self, yaml_type: str) -> dict[str, Any]:
        """
        获取类型完整信息 / Get full type info.

        Args:
            yaml_type: YAML 中的 type 字符串，如 String(100), Boolean

        Returns:
            包含 python_type, sqlalchemy_type, ts_type, default_* 的字典
        """
        base, params = _parse_type(yaml_type)
        info = _TYPE_MAP.get(base)
        if not info:
            # 未知类型回退到 String / Unknown falls back to String
            info = _TYPE_MAP["String"].copy()
        else:
            info = info.copy()

        if base == "String" and "length" in params:
            info["sqlalchemy_type"] = f"String({params['length']})"
        elif base == "Decimal" and "precision" in params:
            p, s = params["precision"], params.get("scale", 2)
            info = {
                "python_type": "Decimal",
                "sqlalchemy_type": f"Numeric({p},{s})",
                "ts_type": "number",
                "default_form_component": "number",
                "default_search_type": None,
                "default_cell_render": None,
                "default_filter_op": "eq",
            }

        return info

    def get_mapped_annotation(self, yaml_type: str, nullable: bool = False) -> str:
        """
        生成 Mapped[] 注解字符串 / Generate Mapped[] annotation string.

        Args:
            yaml_type: YAML 类型
            nullable: 是否可空

        Returns:
            如 Mapped[str] 或 Mapped[str | None]
        """
        info = self.get_type_info(yaml_type)
        py = info["python_type"]
        if nullable:
            return f"Mapped[{py} | None]"
        return f"Mapped[{py}]"

    def get_mapped_column_args(
        self,
        field_config: dict[str, Any],
        yaml_type: str | None = None,
    ) -> str:
        """
        生成 mapped_column() 参数字符串 / Generate mapped_column() args string.

        Args:
            field_config: 字段配置，含 type, nullable, default, unique, index, comment 等
            yaml_type: 若未在 field_config 中则使用此参数

        Returns:
            参数字符串，如 String(100), nullable=False, comment="..."
        """
        t = yaml_type or field_config.get("type", "String")
        info = self.get_type_info(t)
        sa_type = info["sqlalchemy_type"]

        parts = [sa_type]
        nullable = field_config.get("nullable", not field_config.get("required", True))
        parts.append(f"nullable={nullable}")

        if field_config.get("unique"):
            parts.append("unique=True")
        if field_config.get("index"):
            parts.append("index=True")
        if "comment" in field_config and field_config["comment"]:
            c = repr(str(field_config["comment"]))
            parts.append(f"comment={c}")
        if "db_default" in field_config and field_config["db_default"] is not None:
            # server_default 需根据类型处理 / server_default by type
            dv = field_config["db_default"]
            if isinstance(dv, str) and dv.startswith("'"):
                parts.append(f"server_default={dv}")
            else:
                parts.append(f"server_default={repr(dv)}")
        elif "default" in field_config and field_config["default"] is not None:
            dv = field_config["default"]
            if isinstance(dv, bool):
                parts.append(f"default={str(dv)}")
            elif isinstance(dv, (int, float)):
                parts.append(f"default={dv}")
            else:
                parts.append(f"default={repr(dv)}")

        return ", ".join(parts)

    def reverse_map(self, sa_column: Any) -> str | None:
        """
        从 SQLAlchemy 列类型反推 YAML type / Infer YAML type from SA column type.

        供 DB 反射使用 / For DB introspection.

        Args:
            sa_column: SQLAlchemy Column 或 ColumnProperty

        Returns:
            YAML type 字符串，无法推断时返回 None
        """
        if sa_column is None:
            return None
        # 获取底层类型 / Get underlying type
        if hasattr(sa_column, "type"):
            col_type = sa_column.type
        else:
            return None

        type_class = type(col_type)
        if type_class in _REVERSE_MAP:
            base = _REVERSE_MAP[type_class]
            if isinstance(col_type, String) and hasattr(col_type, "length") and col_type.length:
                return f"String({col_type.length})"
            return base
        return None

    def get_ts_type(self, yaml_type: str) -> str:
        """获取 TypeScript 类型 / Get TypeScript type."""
        return self.get_type_info(yaml_type)["ts_type"]

    def get_form_component(self, field_config: dict[str, Any]) -> str:
        """
        获取表单组件名 / Get form component name.

        字段级 form.component 覆盖 > 类型默认
        Field form.component overrides > type default.
        """
        form = field_config.get("form") or {}
        if isinstance(form, dict) and form.get("component"):
            return str(form["component"])
        comp = field_config.get("form_component")  # 简写 / shorthand
        if comp:
            return str(comp)
        t = field_config.get("type", "String")
        info = self.get_type_info(t)
        return info.get("default_form_component") or "input"

    def get_search_component(self, field_config: dict[str, Any]) -> str | None:
        """
        获取搜索组件 / Get search component.

        FK + search.enabled 时返回 ApiSelect；否则返回类型默认
        Returns ApiSelect for FK + search.enabled; otherwise type default.
        """
        t = field_config.get("type", "String")
        base = _parse_type(t)[0]
        search = field_config.get("search") or {}
        if isinstance(search, dict) and not search.get("enabled", True):
            return None
        if base == "ForeignKey":
            return "ApiSelect"
        return self.get_type_info(t).get("default_search_type")

    def get_cell_render(self, field_config: dict[str, Any]) -> str | None:
        """
        获取列渲染方式 / Get cell render for column.

        字段级 column.cell_render 覆盖 > 类型默认
        """
        col = field_config.get("column") or {}
        if isinstance(col, dict) and col.get("cell_render"):
            return str(col["cell_render"])
        t = field_config.get("type", "String")
        return self.get_type_info(t).get("default_cell_render")

    def get_filter_op(self, field_config: dict[str, Any]) -> str | None:
        """获取默认过滤操作符 / Get default filter operator."""
        if field_config.get("filter_op"):
            return str(field_config["filter_op"])
        t = field_config.get("type", "String")
        return self.get_type_info(t).get("default_filter_op")


# 模块级实例 / Module-level instance
type_registry = TypeRegistry()

__all__ = ["TypeRegistry", "type_registry", "_parse_type"]
