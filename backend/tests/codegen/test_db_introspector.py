"""
DB 反射器测试 / DB Introspector tests.

测试 get_table_names、get_columns、基类字段排除、外键检测
Tests get_table_names, get_columns, base_field_exclusion, fk_detection.
"""

from unittest.mock import MagicMock, patch

from app.codegen.db_introspector import DbIntrospector, FKInfo


@patch("app.codegen.db_introspector.inspect")
def test_get_table_names(mock_inspect: MagicMock) -> None:
    """get_table_names 返回表名列表."""
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["users", "tenants", "categories"]
    mock_inspect.return_value = mock_inspector

    intro = DbIntrospector(engine=MagicMock())
    names = intro.get_table_names()

    assert names == ["users", "tenants", "categories"]


@patch("app.codegen.db_introspector.inspect")
def test_get_columns_base_field_exclusion(mock_inspect: MagicMock) -> None:
    """get_columns 排除 BaseModel 基类字段 id, created_at 等."""
    mock_inspector = MagicMock()
    mock_inspector.get_columns.return_value = [
        {"name": "id", "type": MagicMock(), "nullable": False, "default": None},
        {"name": "created_at", "type": MagicMock(), "nullable": True, "default": None},
        {
            "name": "name",
            "type": MagicMock(),
            "nullable": False,
            "default": None,
            "comment": None,
        },
    ]
    mock_inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
    mock_inspector.get_unique_constraints.return_value = []
    mock_inspector.get_foreign_keys.return_value = []
    mock_inspect.return_value = mock_inspector

    intro = DbIntrospector(engine=MagicMock())
    cols = intro.get_columns("users")

    names = [c.name for c in cols]
    assert "id" not in names
    assert "created_at" not in names
    assert "name" in names


@patch("app.codegen.db_introspector.inspect")
def test_get_columns_tenant_field_exclusion(mock_inspect: MagicMock) -> None:
    """get_columns 排除 tenant_id."""
    mock_inspector = MagicMock()
    mock_inspector.get_columns.return_value = [
        {"name": "tenant_id", "type": MagicMock(), "nullable": True, "default": None},
        {
            "name": "title",
            "type": MagicMock(),
            "nullable": False,
            "default": None,
            "comment": None,
        },
    ]
    mock_inspector.get_pk_constraint.return_value = {}
    mock_inspector.get_unique_constraints.return_value = []
    mock_inspector.get_foreign_keys.return_value = []
    mock_inspect.return_value = mock_inspector

    intro = DbIntrospector(engine=MagicMock())
    cols = intro.get_columns("notices")

    names = [c.name for c in cols]
    assert "tenant_id" not in names
    assert "title" in names


@patch("app.codegen.db_introspector.inspect")
@patch("app.codegen.db_introspector.type_registry")
def test_get_columns_fk_detection(mock_tr: MagicMock, mock_inspect: MagicMock) -> None:
    """外键列在 suggested_config 中得到 ForeignKey 类型和 ApiSelect."""
    mock_tr.reverse_map.return_value = "ForeignKey(tenants)"

    mock_inspector = MagicMock()
    mock_inspector.get_columns.return_value = [
        {"name": "tenant_id", "type": MagicMock(), "nullable": True, "default": None},
        {
            "name": "category_id",
            "type": MagicMock(),
            "nullable": True,
            "default": None,
            "comment": None,
        },
    ]
    mock_inspector.get_pk_constraint.return_value = {}
    mock_inspector.get_unique_constraints.return_value = []
    mock_inspector.get_foreign_keys.return_value = [
        {
            "constrained_columns": ["category_id"],
            "referred_table": "categories",
            "referred_columns": ["id"],
        }
    ]
    mock_inspect.return_value = mock_inspector

    intro = DbIntrospector(engine=MagicMock())
    cols = intro.get_columns("items")

    category_col = next(c for c in cols if c.name == "category_id")
    assert category_col.foreign_keys
    assert "ForeignKey" in category_col.suggested_config["type"]
    assert category_col.suggested_config.get("form_component") == "ApiSelect"


@patch("app.codegen.db_introspector.inspect")
def test_get_columns_unique_constraint(mock_inspect: MagicMock) -> None:
    """唯一约束列得到 unique: true."""
    mock_inspector = MagicMock()
    mock_inspector.get_columns.return_value = [
        {
            "name": "code",
            "type": MagicMock(),
            "nullable": False,
            "default": None,
            "comment": None,
        },
    ]
    mock_inspector.get_pk_constraint.return_value = {}
    mock_inspector.get_unique_constraints.return_value = [
        {"column_names": ["code"]},
    ]
    mock_inspector.get_foreign_keys.return_value = []
    mock_inspect.return_value = mock_inspector

    intro = DbIntrospector(engine=MagicMock())
    cols = intro.get_columns("categories")

    code_col = next(c for c in cols if c.name == "code")
    assert code_col.unique is True
    assert code_col.suggested_config.get("unique") is True


def test_get_foreign_keys() -> None:
    """get_foreign_keys 返回 FKInfo 列表."""
    mock_inspector = MagicMock()
    mock_inspector.get_foreign_keys.return_value = [
        {
            "name": "fk_category",
            "constrained_columns": ["category_id"],
            "referred_table": "categories",
            "referred_columns": ["id"],
        }
    ]
    with patch("app.codegen.db_introspector.inspect", return_value=mock_inspector):
        intro = DbIntrospector(engine=MagicMock())
        fks = intro.get_foreign_keys("items")

    assert len(fks) == 1
    assert isinstance(fks[0], FKInfo)
    assert fks[0].referred_table == "categories"
    assert fks[0].constrained_columns == ["category_id"]
