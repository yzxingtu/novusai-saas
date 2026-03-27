"""
Config Parser 单元测试 / Config parser unit tests.

Coverage:
- parse: 最简配置、含 V2 节点
- shorthand expansion: searchable/column/form
- validation: BaseModel+tenant_only, missing fields, invalid types
- enum_values, workflow, relations
"""

import pytest

from app.codegen.config_parser import ConfigParser, ParsedConfig, ValidationError

# ============================================================
# test_parse_simple_yaml
# ============================================================


def test_parse_simple_yaml() -> None:
    """最简配置解析 / Parse minimal config."""
    config = {
        "module": "system",
        "resource": "category",
        "display_name": "分类",
        "display_name_en": "Category",
        "model": {"base_class": "BaseModel"},
        "fields": [
            {"name": "name", "type": "String(100)", "comment": "名称"},
        ],
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    assert parsed.module == "system"
    assert parsed.resource == "category"
    assert parsed.resource_plural == "categories"
    assert parsed.display_name == "分类"
    assert len(parsed.fields) == 1
    assert parsed.fields[0]["name"] == "name"
    assert parsed.model["base_class"] == "BaseModel"
    assert parsed.model["table_name"] == "categories"


# ============================================================
# test_shorthand_expansion
# ============================================================


def test_shorthand_expansion_searchable() -> None:
    """searchable:true 展开为 filterable + search.enabled + filter_op."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [{"name": "f1", "type": "String", "searchable": True}],
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    f = parsed.fields[0]
    assert f.get("filterable") is True
    assert f.get("search", {}).get("enabled") is True
    assert f.get("filter_op") == "ilike"


def test_shorthand_expansion_column() -> None:
    """column:true 展开为 column.visible=true."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [{"name": "f1", "type": "String", "column": True}],
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    f = parsed.fields[0]
    assert f.get("column", {}).get("visible") is True


def test_shorthand_expansion_form() -> None:
    """form: input 展开为 form.component=input."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [{"name": "f1", "type": "String", "form": "input"}],
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    f = parsed.fields[0]
    assert f.get("form", {}).get("component") == "input"


def test_shorthand_expansion_comment_en_split() -> None:
    """comment "中文 / English" 自动拆分为 comment 和 comment_en."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [{"name": "title", "type": "String", "comment": "标题 / Title"}],
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    f = parsed.fields[0]
    assert f.get("comment") == "标题"
    assert f.get("comment_en") == "Title"


# ============================================================
# test_validation_errors
# ============================================================


def test_validation_errors_base_model_tenant_only() -> None:
    """BaseModel + tenant_only 端点非法."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "model": {"base_class": "BaseModel"},
        "fields": [{"name": "f1", "type": "String"}],
        "endpoints": [{"scope": "tenant_only", "route_prefix": "/r"}],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    codes = [e.code for e in errors]
    assert "invalid_base_tenant" in codes or any("tenant" in e.code for e in errors)


def test_validation_errors_base_model_cross_tenant() -> None:
    """BaseModel + cross_tenant 非法."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "model": {"base_class": "BaseModel"},
        "fields": [{"name": "f1", "type": "String"}],
        "endpoints": [{"scope": "admin", "data_mode": "cross_tenant"}],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    codes = [e.code for e in errors]
    assert "invalid_base_cross_tenant" in codes


def test_validation_errors_missing_fields() -> None:
    """fields 为空时报错."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert any(e.code == "missing_fields" for e in errors)


def test_validation_errors_field_no_name() -> None:
    """字段缺少 name 报错."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [{"type": "String"}],  # no name
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert any(e.code == "field_no_name" for e in errors)


def test_validation_errors_invalid_base_class() -> None:
    """base_class 非法值报错."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "model": {"base_class": "InvalidModel"},
        "fields": [{"name": "f1", "type": "String"}],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert any(e.code == "invalid_base_class" for e in errors)


def test_validation_errors_invalid_scope() -> None:
    """endpoint scope 非法值报错."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [{"name": "f1", "type": "String"}],
        "endpoints": [{"scope": "invalid_scope"}],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert any(e.code == "invalid_scope" for e in errors)


def test_validation_errors_invalid_data_mode() -> None:
    """endpoint data_mode 非法值报错."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [{"name": "f1", "type": "String"}],
        "endpoints": [{"scope": "admin", "data_mode": "invalid_mode"}],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert any(e.code == "invalid_data_mode" for e in errors)


def test_validation_errors_invalid_sub_table_mode() -> None:
    """sub_table mode 非法值报错."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [{"name": "f1", "type": "String"}],
        "sub_tables": [{"resource": "line", "mode": "invalid_mode", "fields": [{"name": "x", "type": "String"}]}],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert any(e.code == "invalid_sub_table_mode" for e in errors)


# ============================================================
# test_enum_values_parsing
# ============================================================


def test_enum_values_parsing() -> None:
    """enum_values 解析."""
    config = {
        "module": "x",
        "resource": "r",
        "display_name": "D",
        "fields": [
            {
                "name": "status",
                "type": "Enum",
                "enum_values": [
                    {"value": "draft", "label_zh": "草稿", "label_en": "Draft", "color": "default"},
                    {"value": "active", "label_zh": "启用", "label_en": "Active", "color": "success"},
                ],
            },
        ],
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    f = parsed.fields[0]
    assert f.get("enum_values") is not None
    assert len(f["enum_values"]) == 2
    assert f["enum_values"][0]["value"] == "draft"
    assert f["enum_values"][0]["label_zh"] == "草稿"


# ============================================================
# test_workflow_parsing
# ============================================================


def test_workflow_parsing() -> None:
    """workflow 节点解析."""
    config = {
        "module": "x",
        "resource": "approval",
        "display_name": "审批",
        "model": {"base_class": "TenantModel"},
        "fields": [
            {"name": "status", "type": "Enum", "enum_values": [{"value": "draft"}, {"value": "approved"}]},
        ],
        "workflow": {
            "status_field": "status",
            "transitions": [{"from": "draft", "to": "approved", "action": "submit"}],
        },
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    assert parsed.workflow is not None
    assert parsed.workflow.get("status_field") == "status"
    assert len(parsed.workflow.get("transitions", [])) == 1
    assert parsed.workflow["transitions"][0]["action"] == "submit"


# ============================================================
# test_parse_with_all_v2_nodes
# ============================================================


def test_parse_with_all_v2_nodes() -> None:
    """含 V2 节点配置解析."""
    config = {
        "module": "system",
        "resource": "department",
        "display_name": "部门",
        "display_name_en": "Department",
        "model": {
            "base_class": "TenantModel",
            "tree": {"enabled": True},
            "selectable": {"label": "name", "value": "id"},
            "unique_together": [{"fields": ["code"], "name": "uq_code"}],
        },
        "fields": [
            {"name": "name", "type": "String(100)", "required": True},
            {"name": "parent_id", "type": "Integer", "nullable": True},
        ],
        "endpoints": [{"scope": "admin", "route_prefix": "/departments"}],
        "detail": {"enabled": True, "groups": [{"title_zh": "基本信息", "fields": ["name"]}]},
        "clone": {"enabled": True},
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    assert parsed.model.get("tree", {}).get("enabled") is True
    assert parsed.model.get("selectable") is not None
    assert parsed.detail is not None
    assert parsed.detail.get("enabled") is True
    assert parsed.clone is not None
    assert parsed.clone.get("enabled") is True


# ============================================================
# test_parse_yaml_string
# ============================================================


def test_parse_yaml_string() -> None:
    """从 YAML 字符串解析."""
    yaml_str = """
module: system
resource: category
display_name: 分类
display_name_en: Category
model:
  base_class: BaseModel
fields:
  - name: name
    type: String(100)
"""
    parser = ConfigParser()
    parsed = parser.parse(yaml_str)

    assert parsed.module == "system"
    assert parsed.resource == "category"
    assert len(parsed.fields) == 1


def test_expand_defaults_frontend_search_config() -> None:
    """frontend 搜索配置默认值应自动补全。"""
    config = {
        "module": "system",
        "resource": "category",
        "display_name": "分类",
        "fields": [{"name": "name", "type": "String", "filterable": True}],
        "endpoints": [{"scope": "admin"}],
    }
    parser = ConfigParser()
    parsed = parser.parse(config)

    frontend = parsed.endpoints[0]["frontend"]
    assert frontend["search_default_open"] is False
    assert frontend["quick_search"] is True


def test_validation_errors_invalid_quick_search_field() -> None:
    """quick_search 字段引用无效候选项时应报错。"""
    config = {
        "module": "system",
        "resource": "category",
        "display_name": "分类",
        "fields": [
            {"name": "name", "type": "String", "filterable": True},
            {"name": "is_active", "type": "Boolean", "filterable": True},
        ],
        "endpoints": [
            {
                "scope": "admin",
                "frontend": {
                    "quick_search": {
                        "fields": ["is_active"],
                        "default_field": "is_active",
                    }
                },
            }
        ],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert any(e.code == "unknown_quick_search_field" for e in errors)
    assert any(e.code == "unknown_quick_search_default_field" for e in errors)


def test_validation_errors_invalid_search_default_open() -> None:
    """search_default_open 必须是布尔值。"""
    config = {
        "module": "system",
        "resource": "category",
        "display_name": "分类",
        "fields": [{"name": "name", "type": "String", "filterable": True}],
        "endpoints": [
            {
                "scope": "admin",
                "frontend": {
                    "search_default_open": "yes",
                },
            }
        ],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert any(e.code == "invalid_search_default_open" for e in errors)


def test_validation_accepts_object_quick_search_fields() -> None:
    """quick_search.fields 支持对象写法。"""
    config = {
        "module": "system",
        "resource": "category",
        "display_name": "分类",
        "fields": [
            {"name": "name", "type": "String", "filterable": True},
            {"name": "code", "type": "String", "filterable": True},
        ],
        "endpoints": [
            {
                "scope": "admin",
                "frontend": {
                    "quick_search": {
                        "fields": [
                            {"fieldName": "name", "label": "名称"},
                            {"fieldName": "code", "placeholder": "搜索编码"},
                        ],
                        "defaultField": "code",
                    }
                },
            }
        ],
    }
    parser = ConfigParser()
    errors = parser.validate(config)

    assert errors == []
