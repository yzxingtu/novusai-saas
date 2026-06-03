"""
Type Registry 单元测试 / Type registry unit tests.

Coverage:
- 基础类型映射
- 高级组件
- reverse_map
- 字段级覆盖
- get_form_component, get_search_component
"""

from sqlalchemy import Boolean, Column, Integer, String, Text

from app.codegen.type_registry import type_registry

# ============================================================
# test_basic_types
# ============================================================


def test_string_type() -> None:
    """String 类型映射."""
    info = type_registry.get_type_info("String")
    assert info["python_type"] == "str"
    assert "String" in info["sqlalchemy_type"]
    assert info["ts_type"] == "string"
    assert info["default_form_component"] == "input"


def test_string_with_length() -> None:
    """String(100) 参数解析."""
    info = type_registry.get_type_info("String(100)")
    assert info["sqlalchemy_type"] == "String(100)"


def test_boolean_type() -> None:
    """Boolean 类型映射."""
    info = type_registry.get_type_info("Boolean")
    assert info["python_type"] == "bool"
    assert info["default_form_component"] == "switch"
    assert info["default_cell_render"] == "CellSwitch"


def test_integer_float_types() -> None:
    """Integer, Float 类型."""
    for t in ("Integer", "Float", "BigInteger"):
        info = type_registry.get_type_info(t)
        assert info["ts_type"] == "number"


def test_datetime_date_types() -> None:
    """DateTime, Date 类型."""
    for t in ("DateTime", "Date"):
        info = type_registry.get_type_info(t)
        assert info["default_form_component"] == "date"
        assert info["default_cell_render"] == "formatDate"


def test_enum_type() -> None:
    """Enum 类型映射."""
    info = type_registry.get_type_info("Enum")
    assert info["default_form_component"] == "select"
    assert info["default_cell_render"] == "CellTag"


def test_foreign_key_type() -> None:
    """ForeignKey 类型."""
    info = type_registry.get_type_info("ForeignKey(users)")
    assert info["default_form_component"] == "ApiSelect"
    assert info["default_search_type"] == "ApiSelect"


# ============================================================
# test_advanced_components
# ============================================================


def test_advanced_components() -> None:
    """6 种高级组件映射."""
    components = [
        "ImageUpload",
        "RichText",
        "FilePicker",
        "CronPicker",
        "IconPicker",
        "CodeEditor",
    ]
    for comp in components:
        info = type_registry.get_type_info(comp)
        assert info["default_form_component"] == comp
        assert "python_type" in info
        assert "sqlalchemy_type" in info


# ============================================================
# test_reverse_map
# ============================================================


def test_reverse_map_string() -> None:
    """String 列反推."""
    col = Column("x", String(50))
    yaml_type = type_registry.reverse_map(col)
    assert yaml_type == "String(50)" or yaml_type == "String"


def test_reverse_map_integer() -> None:
    """Integer 列反推."""
    col = Column("x", Integer())
    yaml_type = type_registry.reverse_map(col)
    assert yaml_type == "Integer"


def test_reverse_map_boolean() -> None:
    """Boolean 列反推."""
    col = Column("x", Boolean())
    yaml_type = type_registry.reverse_map(col)
    assert yaml_type == "Boolean"


def test_reverse_map_text() -> None:
    """Text 列反推."""
    col = Column("x", Text())
    yaml_type = type_registry.reverse_map(col)
    assert yaml_type == "Text"


# ============================================================
# test_field_override
# ============================================================


def test_field_override_form_component() -> None:
    """字段级 form.component 覆盖类型默认."""
    field = {"type": "String", "form": {"component": "textarea"}}
    comp = type_registry.get_form_component(field)
    assert comp == "textarea"


def test_field_override_cell_render() -> None:
    """字段级 column.cell_render 覆盖."""
    field = {"type": "String", "column": {"cell_render": "CellLink"}}
    render = type_registry.get_cell_render(field)
    assert render == "CellLink"


# ============================================================
# test_fk_search_api_select
# ============================================================


def test_fk_search_enabled_returns_api_select() -> None:
    """ForeignKey + search.enabled 返回 ApiSelect."""
    field = {"type": "ForeignKey(departments)", "search": {"enabled": True}}
    comp = type_registry.get_search_component(field)
    assert comp == "ApiSelect"


def test_get_ts_type() -> None:
    """get_ts_type 返回正确类型."""
    assert type_registry.get_ts_type("String") == "string"
    assert type_registry.get_ts_type("Integer") == "number"
    assert type_registry.get_ts_type("Boolean") == "boolean"


def test_get_mapped_annotation() -> None:
    """get_mapped_annotation 生成 Mapped 注解."""
    assert "Mapped[str]" in type_registry.get_mapped_annotation("String")
    assert "None" in type_registry.get_mapped_annotation("String", nullable=True)
