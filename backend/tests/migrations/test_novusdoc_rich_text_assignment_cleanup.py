"""
Test type: structural
Scope: NovusDoc rich-text AI legacy assignment cleanup migration.
Real dependencies: migration source file.
Mocked dependencies: none.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    BACKEND_DIR
    / "migrations"
    / "versions"
    / "20260506_0028_drop_novusdoc_rich_text_assignment.py"
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "novusdoc_rich_text_assignment_cleanup_migration",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_feature_codes_are_stable() -> None:
    module = _load_migration()

    assert module.revision == "20260506_0028_drop_novus_rich"
    assert len(module.revision) <= 32
    assert module.down_revision == "20260505_0027_novusdoc_richai"
    assert module.LEGACY_FEATURE_CODE == "plugin.novusdoc.rich_text_ai"
    assert module.RUNTIME_FEATURE_CODE == "system.ai_writing"


def test_upgrade_deletes_only_the_global_legacy_plugin_assignment_row() -> None:
    module = _load_migration()
    upgrade_source = inspect.getsource(module.upgrade)

    assert "DELETE FROM system_agent_assignments" in upgrade_source
    assert "WHERE feature_code = :legacy_feature_code" in upgrade_source
    assert "tenant_id IS NULL" in upgrade_source
    assert "is_deleted = false" in upgrade_source
    assert ":runtime_feature_code" not in upgrade_source


def test_downgrade_restores_catalog_row_without_runtime_config() -> None:
    module = _load_migration()
    downgrade_source = inspect.getsource(module.downgrade)

    assert "INSERT INTO system_agent_assignments" in downgrade_source
    assert "runtime_assignment.agent_id" in downgrade_source
    assert "NULL," in downgrade_source
    assert "config" in downgrade_source
    assert "WHERE feature_code = :runtime_feature_code" in downgrade_source
    assert "WHERE feature_code = :legacy_feature_code" in downgrade_source
