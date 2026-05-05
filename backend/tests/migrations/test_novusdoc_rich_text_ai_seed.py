"""
Test type: structural
Scope: NovusDoc rich-text AI seed migration visibility and runtime contract.
Real dependencies: migration source file and plugin manifest text.
Mocked dependencies: none.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    BACKEND_DIR
    / "migrations"
    / "versions"
    / "20260505_0027_seed_novusdoc_rich_text_ai.py"
)
PLUGIN_MANIFEST_PATH = BACKEND_DIR / "plugins" / "novusdoc" / "plugin.yaml"


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "novusdoc_rich_text_ai_seed_migration",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_feature_code_are_stable() -> None:
    module = _load_migration()

    assert module.revision == "20260505_0027_novusdoc_richai"
    assert len(module.revision) <= 32
    assert module.down_revision == "20260502_0026_admin_ai_enabled"
    assert module.FEATURE_CODE == "system.ai_writing"
    assert module.INTERNAL_COMPAT_FEATURE_CODE == "plugin.novusdoc.rich_text_ai"
    assert module.MANIFEST_FEATURE_CODE == "rich_text_ai"
    assert not hasattr(module, "CATALOG_FEATURE_CODE")
    assert not hasattr(module, "LEGACY_FEATURE_CODE")
    assert not hasattr(module, "_AI_FEATURE")
    assert not hasattr(module, "_CATALOG_FEATURE")


def test_default_action_config_is_system_runtime_only() -> None:
    module = _load_migration()

    config = module.default_action_config()
    actions = {item["code"]: item for item in config["actions"]}

    assert config["feature_code"] == "system.ai_writing"
    assert "catalog_feature_code" not in config
    assert "runtime_feature_code" not in config
    assert "legacy_runtime_feature_code" not in config
    assert "fallback_policy" not in config
    assert "plugin.novusdoc.rich_text_ai" not in str(config)
    assert set(actions) == {
        "continue",
        "rewrite",
        "insert",
        "format",
        "optimize",
        "proofread",
        "translate",
        "summarize",
        "expand",
        "custom",
        "chat",
    }
    assert actions["continue"]["operation"] == "insert_after_cursor"
    assert actions["insert"]["operation"] == "insert_at_cursor"
    assert actions["format"]["format_instruction_supported"] is True
    assert actions["rewrite"]["requires_selection"] is True
    assert config["security"] == {
        "page_context_allowed": False,
        "dom_runtime_allowed": False,
        "allowed_data_source": "explicit_editor_payload",
    }


def test_manifest_exposes_no_rich_text_catalog_or_ai_feature() -> None:
    module = _load_migration()
    manifest_text = PLUGIN_MANIFEST_PATH.read_text(encoding="utf-8")

    assert "ai_requirements:" in manifest_text
    assert "required_model_types:" in manifest_text
    assert "min_context_window: 4096" in manifest_text
    assert "features: []" in manifest_text
    assert "code: rich_text_ai" not in manifest_text
    assert "feature_code: rich_text_ai" not in manifest_text
    assert "runtime_feature_code:" not in manifest_text
    assert "legacy_runtime_feature_code:" not in manifest_text
    assert "fallback_policy:" not in manifest_text
    assert "plugin.novusdoc.rich_text_ai" not in manifest_text

    assert module.AI_REQUIREMENTS == {
        "features": [],
        "required_model_types": ["chat"],
        "min_context_window": 4096,
    }


def test_migration_removes_plugin_catalog_and_hides_default_skill_package() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    source_lines = set(source.splitlines())

    assert 'FEATURE_CODE = "system.ai_writing"' in source_lines
    assert (
        'INTERNAL_COMPAT_FEATURE_CODE = "plugin.novusdoc.rich_text_ai"' in source_lines
    )
    assert 'FEATURE_CODE = "plugin.novusdoc.rich_text_ai"' not in source_lines
    assert "feature_code=FEATURE_CODE" in source
    assert "feature_code=INTERNAL_COMPAT_FEATURE_CODE" not in source
    assert "_delete_unbound_legacy_plugin_assignment(bind)" in source
    assert "feature_code = :internal_compat_feature_code" in source
    assert "_cleanup_system_assignment_config(bind)" in source
    assert "catalog_feature_code" in source
    assert "- 'catalog_feature_code'" in source
    assert "_hide_default_rich_text_skill_package(bind)" in source
    assert 'RICH_TEXT_PACKAGE_NAME = "NovusDoc Rich Text AI"' in source
    assert 'RICH_TEXT_SKILL_KEY = "novusdoc.rich_text_ai.actions"' in source
    assert "UPDATE skill_packages" in source
    assert "UPDATE skills" in source
    assert "is_deleted = true" in source
    assert "is_recommended = false" in source
    assert "status = 'disabled'" in source
    assert "feature ->> 'code'" in source
    assert "<> :manifest_feature_code" in source
    assert "jsonb_build_array(CAST(:catalog_feature_json" not in source
    assert "LEGACY_FEATURE_CODE" not in source
    assert "_AI_FEATURE" not in source
    assert "- 'legacy_runtime_feature_code'" in source
    assert "- 'fallback_policy'" in source
    assert '"legacy_runtime_feature_code":' not in source
    assert '"fallback_policy":' not in source
    assert "legacy_only_when_primary_row_missing" not in source
    assert 'HIDE_MARKER_KEY = "hidden_by_20260505_0027"' in source
    assert 'HIDE_MARKER_PATH = "{hidden_by_20260505_0027}"' in source
    assert "CAST(:hide_marker_path AS text[])" in source
    assert "_restore_hidden_default_rich_text_skill_package(bind)" in source
    assert "COALESCE(skill.config::jsonb" in source
    assert "COALESCE(pkg.valves_config::jsonb" in source
