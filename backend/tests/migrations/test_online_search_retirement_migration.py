"""Test type: structural
Scope: online-search retirement Alembic migration contract.
Mock strategy: no mocks; static migration source inspection only.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from app.schemas.ai.invalid_ai_runtime_input import normalize_ai_runtime_token

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260508_0033_retire_search.py"
)
FOLLOWUP_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260508_0037_search_payload.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "test_online_search_retirement_migration_module",
        MIGRATION,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_online_search_retirement_migration_targets_catalog_and_grants() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260508_0033_retire_search"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260507_0032_task_priority"'
        in source
    )
    for table_name in ("skill_packages", "skills", "agent_skill_grants"):
        assert table_name in source
    for token in (
        "web_search",
        "fetch_url",
        "web_research",
        "online_search",
        "baidu_public_search",
        "hosted_web_search_supported",
        "native_web_search_supported",
        "SearchProvider",
        "百度公开搜索",
        "联网搜索",
    ):
        assert token in source
    assert "enabled = false" in source
    assert "is_deleted = true" in source
    assert "def downgrade() -> None:\n    pass" in source


def test_online_search_retirement_migration_targets_executable_payloads() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for column_ref in (
        "skill.config",
        "skill.toolkit_content",
        "skill.toolkit_meta",
        "skill.skill_md",
    ):
        assert f"CAST({column_ref} AS TEXT)" in source
    assert "_retire_agent_skill_grants_by_skill_payloads" in source
    assert "_retire_skills_by_skill_payloads" in source
    assert "raw_toolkit_content LIKE ANY(:retired_raw_patterns)" in source
    assert "normalized_toolkit_content LIKE ANY(:retired_normalized_patterns)" in source


def test_online_search_payload_followup_migration_targets_already_upgraded_dbs() -> (
    None
):
    source = FOLLOWUP_MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260508_0037_search_payload"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260508_0036_task_contract"'
        in source
    )
    assert "_retire_agent_skill_grants_by_skill_payloads" in source
    assert "_retire_skills_by_skill_payloads" in source
    for column_ref in (
        "skill.config",
        "skill.toolkit_content",
        "skill.toolkit_meta",
        "skill.skill_md",
    ):
        assert f"CAST({column_ref} AS TEXT)" in source
    assert "web_search" in source
    assert "fetch_url" in source
    assert " AS grant" not in source
    assert "text(f" not in source


def test_online_search_retirement_migration_uses_parameterized_sql() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "text(f" not in source
    assert 'f"""' not in source
    assert " AS grant" not in source
    assert re.search(r"\bgrant\.", source) is None
    assert ":retired_raw_patterns" in source
    assert ":retired_normalized_patterns" in source
    assert "_has_columns" in source


def test_online_search_retirement_migration_matches_runtime_normalization() -> None:
    module = _load_migration_module()
    samples = (
        "web.search.options",
        "hosted:web:search:supported",
        "native/web/search/supported",
        r"native\web\search\supported",
        "web-search-preview",
        "web search runtime",
        "SearchProvider",
    )

    for sample in samples:
        normalized = normalize_ai_runtime_token(sample)
        assert module._normalize_retired_token(sample) == normalized
        assert f"%{normalized}%" in module.RETIRED_ONLINE_SEARCH_NORMALIZED_PATTERNS

    source = MIGRATION.read_text(encoding="utf-8")
    for sql_fragment in ("'.'", "':'", "'/'", "CHR(92)", "'-'", "' '"):
        assert sql_fragment in source
