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
    for f in files:
        assert isinstance(f.content, str), f"{f.path} should have content"
        assert len(f.content) > 20, f"{f.path} content too short"


# ============================================================
# tree preset
# ============================================================


def test_tree_generates_with_tree_config() -> None:
    """tree 预设生成包含树形相关逻辑."""
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
        # model 步骤包含 models/schemas/repositories/services
        assert any(x in p for x in ("models", "schemas", "repositories", "services"))


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
