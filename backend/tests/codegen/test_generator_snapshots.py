"""
Generator snapshot 测试 / Generator snapshot tests.

使用 presets/ 下的 YAML 作为输入，验证生成的文件列表和内容结构。
Uses presets/ YAML as input, verifies generated file list and content structure.
"""

from pathlib import Path

import pytest
import yaml

from app.codegen.config_parser import ConfigParser
from app.codegen.generator import CodeGenerator, GeneratedFile


def _load_preset(name: str) -> dict:
    """加载预设配置 / Load preset config."""
    presets_dir = Path(__file__).resolve().parent.parent.parent / "app" / "codegen" / "templates" / "presets"
    path = presets_dir / f"{name}.yaml"
    if not path.exists():
        pytest.skip(f"Preset {name} not found")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _generate(name: str) -> list[GeneratedFile]:
    """解析预设并生成 / Parse preset and generate."""
    config = _load_preset(name)
    parser = ConfigParser()
    parsed = parser.parse(config)
    gen = CodeGenerator()
    result = gen.generate(parsed, step=None)
    return result.files


# ============================================================
# simple preset
# ============================================================


def test_simple_generates_model_schema_repo() -> None:
    """simple 预设生成 Model、Schema、Repository."""
    files = _generate("simple")

    paths = [f.path for f in files]
    assert any("models" in p and "category" in p and p.endswith(".py") for p in paths)
    assert any("schemas" in p and "category" in p and p.endswith(".py") for p in paths)
    assert any("repositories" in p and "category" in p and p.endswith(".py") for p in paths)


def test_simple_generates_controller() -> None:
    """simple 预设生成 Controller."""
    files = _generate("simple")

    paths = [f.path for f in files]
    assert any("api" in p and "category" in p and p.endswith(".py") for p in paths)


def test_simple_generates_frontend() -> None:
    """simple 预设生成前端文件."""
    files = _generate("simple")

    paths = [f.path for f in files]
    assert any("frontend" in p and "api" in p and "category" in p and p.endswith(".ts") for p in paths)
    assert any("frontend" in p and "views" in p and "category" in p and "data.ts" in p for p in paths)
    assert any("frontend" in p and "category" in p and "index.vue" in p for p in paths)


def test_simple_files_have_content() -> None:
    """生成文件包含非空内容."""
    files = _generate("simple")
    skip_actions = {"register_model", "register_route"}  # 元动作，内容由 FileWriter 写入
    for f in files:
        if f.action in skip_actions:
            continue
        assert isinstance(f.content, str), f"{f.path} should have content"
        assert len(f.content) > 20, f"{f.path} content too short"


# ============================================================
# tree preset
# ============================================================


def test_tree_generates_with_tree_config() -> None:
    """tree 预设生成包含树形相关逻辑."""
    config = _load_preset("tree")
    assert config["model"]["base_class"] == "BaseModel"

    files = _generate("tree")

    paths = [f.path for f in files]
    assert any("department" in p for p in paths)
    # 树形 model 应有 parent_id 等
    model_files = [f for f in files if "models" in f.path and f.path.endswith(".py")]
    assert len(model_files) >= 1
    model_content = model_files[0].content
    assert "parent" in model_content.lower() or "parent_id" in model_content.lower()


# ============================================================
# dual_scope preset
# ============================================================


def test_dual_scope_generates_admin_and_tenant() -> None:
    """dual_scope 预设生成 admin 和 tenant 端."""
    files = _generate("dual_scope")

    paths = [f.path for f in files]
    admin_api = [p for p in paths if "api" in p and "admin" in p]
    tenant_api = [p for p in paths if "api" in p and "tenant" in p]
    assert len(admin_api) >= 1
    assert len(tenant_api) >= 1


# ============================================================
# workflow preset
# ============================================================


def test_workflow_generates_with_workflow_config() -> None:
    """workflow 预设生成包含状态工作流."""
    files = _generate("workflow")

    paths = [f.path for f in files]
    assert any("approval" in p for p in paths)
    # 检查 enum status 字段
    schema_files = [f for f in files if "schemas" in f.path and "approval" in f.path]
    if schema_files:
        content = schema_files[0].content
        assert "status" in content.lower()


# ============================================================
# step parameter
# ============================================================


def test_generate_step_model_only() -> None:
    """step=model 仅生成 model/service 相关."""
    config = _load_preset("simple")
    parser = ConfigParser()
    parsed = parser.parse(config)
    gen = CodeGenerator()

    result = gen.generate(parsed, step="model")
    files = result.files

    paths = [f.path for f in files]
    for p in paths:
        assert "backend" in p
        # model 步骤包含 models/schemas/repositories/services、migrations、locales（后端 i18n）
        assert any(
            x in p
            for x in ("models", "schemas", "repositories", "services", "migrations", "locales")
        )


def test_generate_step_controller() -> None:
    """step=controller 生成 Controller."""
    config = _load_preset("simple")
    parser = ConfigParser()
    parsed = parser.parse(config)
    gen = CodeGenerator()

    result = gen.generate(parsed, step="controller")
    files = result.files

    paths = [f.path for f in files]
    api_files = [p for p in paths if "api" in p and p.endswith(".py")]
    assert len(api_files) >= 1


def test_card_mode_template_includes_permissions_and_recycle_bin() -> None:
    """card 模板生成的页面应包含回收站入口和编辑/删除权限控制."""
    config = {
        "module": "system",
        "resource": "library",
        "display_name": "知识库",
        "display_name_en": "Knowledge Base",
        "model": {"base_class": "BaseModel"},
        "fields": [
            {
                "name": "name",
                "type": "String(100)",
                "required": True,
                "filterable": True,
                "comment": "名称",
            },
            {
                "name": "description",
                "type": "Text",
                "nullable": True,
                "comment": "描述",
            },
        ],
        "endpoints": [
            {
                "scope": "admin",
                "data_mode": "independent",
                "route_prefix": "/libraries",
                "frontend": {
                    "mode": "card",
                    "recycle_bin": True,
                },
                "permission": {
                    "scope": "admin_only",
                    "parent_resource": "system_config",
                    "menu": {
                        "icon": "lucide:book-open",
                        "path": "/system/libraries",
                        "component": "system/library/index",
                        "parent": "system_mgmt",
                        "sort_order": 40,
                    },
                },
            }
        ],
    }

    parser = ConfigParser()
    parsed = parser.parse(config)
    gen = CodeGenerator()

    result = gen.generate(parsed, step="frontend")
    index_file = next(
        f
        for f in result.files
        if f.path.endswith("frontend/apps/web-antd/src/views/admin/system/library/index.vue")
    )

    assert "RecycleBinDrawer" in index_file.content
    assert "recycleBinPermission" in index_file.content
    assert 'v-access:code="[updatePermission]"' in index_file.content
    assert 'v-access:code="[deletePermission]"' in index_file.content


def test_table_template_preserves_string_query_type() -> None:
    """表格模板应保留字符串字段的 queryType 配置。"""
    config = {
        "module": "system",
        "resource": "article",
        "display_name": "文章",
        "display_name_en": "Article",
        "model": {"base_class": "BaseModel"},
        "fields": [
            {
                "name": "title",
                "type": "String(120)",
                "filterable": True,
                "form": {"queryType": "like"},
                "comment": "标题",
            },
        ],
        "endpoints": [
            {
                "scope": "admin",
                "data_mode": "independent",
                "route_prefix": "/articles",
                "frontend": {"mode": "table"},
            }
        ],
    }

    parser = ConfigParser()
    parsed = parser.parse(config)
    gen = CodeGenerator()

    result = gen.generate(parsed, step="frontend")
    data_file = next(
        f
        for f in result.files
        if f.path.endswith(
            "frontend/apps/web-antd/src/views/admin/system/article/data.ts",
        )
    )

    assert "searchInput('title'" in data_file.content
    assert "op: 'like'" in data_file.content


def test_card_template_supports_configured_quick_search_fields() -> None:
    """card 模板应支持 quick_search 多字段配置与 defaultField 别名。"""
    config = {
        "module": "system",
        "resource": "library",
        "display_name": "知识库",
        "display_name_en": "Knowledge Base",
        "model": {"base_class": "BaseModel"},
        "fields": [
            {
                "name": "name",
                "type": "String(100)",
                "filterable": True,
                "comment": "名称",
            },
            {
                "name": "code",
                "type": "String(50)",
                "filterable": True,
                "form": {"queryType": "like"},
                "comment": "编码",
            },
        ],
        "endpoints": [
            {
                "scope": "admin",
                "data_mode": "independent",
                "route_prefix": "/libraries",
                "frontend": {
                    "mode": "card",
                    "quick_search": {
                        "fields": [
                            {"fieldName": "name", "label": "名称"},
                            {"fieldName": "code", "placeholder": "搜索编码"},
                        ],
                        "defaultField": "code",
                    },
                },
            }
        ],
    }

    parser = ConfigParser()
    parsed = parser.parse(config)
    gen = CodeGenerator()

    result = gen.generate(parsed, step="frontend")
    index_file = next(
        f
        for f in result.files
        if f.path.endswith(
            "frontend/apps/web-antd/src/views/admin/system/library/index.vue",
        )
    )

    assert "resolvedQuickSearchOptions.length > 1" in index_file.content
    assert "rawQuickSearch.default_field || rawQuickSearch.defaultField" in index_file.content
    assert "override?.placeholder ?? option.placeholder" in index_file.content
