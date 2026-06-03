"""中文: 清退已升级环境中的联网搜索技能执行负载。

EN: Retire online-search executable skill payloads in upgraded environments.

Revision ID: 20260508_0037_search_payload
Revises: 20260508_0036_task_contract
Create Date: 2026-05-08

"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20260508_0037_search_payload"
down_revision: str | Sequence[str] | None = "20260508_0036_task_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TOKEN_SEPARATOR_RE = re.compile(r"[\s.\-:/\\]+")

RETIRED_ONLINE_SEARCH_TERMS = (
    "fetch url",
    "fetch-url",
    "fetch_url",
    "hosted web search",
    "hosted-web-search",
    "hosted_web_search",
    "internet search",
    "internet-search",
    "internet_search",
    "native web search",
    "native-web-search",
    "native_web_search",
    "online search",
    "online-search",
    "online_search",
    "response.web_search_call",
    "response_web_search_call",
    "search provider",
    "search-provider",
    "search_provider",
    "SearchProvider",
    "searchprovider",
    "web research",
    "web-research",
    "web_research",
    "web search",
    "web-search",
    "web_search",
    "web search call",
    "web-search-call",
    "web_search_call",
    "websearch",
    "上网搜索",
    "上网查询",
    "在线搜索",
    "网络搜索",
    "网页搜索",
    "联网搜索",
)


def _normalize_retired_token(value: object) -> str:
    text_value = str(value or "").strip().lower()
    return _TOKEN_SEPARATOR_RE.sub("_", text_value).strip("_")


RETIRED_ONLINE_SEARCH_RAW_PATTERNS = tuple(
    dict.fromkeys(f"%{str(value).lower()}%" for value in RETIRED_ONLINE_SEARCH_TERMS)
)
RETIRED_ONLINE_SEARCH_NORMALIZED_PATTERNS = tuple(
    dict.fromkeys(
        f"%{normalized}%"
        for value in RETIRED_ONLINE_SEARCH_TERMS
        if (normalized := _normalize_retired_token(value))
    )
)


def _retired_pattern_params() -> dict[str, list[str]]:
    return {
        "retired_raw_patterns": list(RETIRED_ONLINE_SEARCH_RAW_PATTERNS),
        "retired_normalized_patterns": list(RETIRED_ONLINE_SEARCH_NORMALIZED_PATTERNS),
    }


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _has_columns(
    bind: sa.Connection,
    table_name: str,
    column_names: tuple[str, ...],
) -> bool:
    existing = _columns(bind, table_name)
    return all(name in existing for name in column_names)


def _retire_agent_skill_grants_by_skill_payloads(bind: sa.Connection) -> None:
    if not _has_columns(
        bind,
        "agent_skill_grants",
        (
            "skill_id",
            "enabled",
            "is_deleted",
            "deleted_at",
            "delete_level",
            "recycle_stage",
            "promoted_to_global_at",
            "updated_at",
        ),
    ):
        return
    if not _has_columns(
        bind,
        "skills",
        (
            "id",
            "config",
            "toolkit_content",
            "toolkit_meta",
            "skill_md",
        ),
    ):
        return
    bind.execute(
        text("""
            WITH candidate_skills AS (
                SELECT
                    skill.id,
                    LOWER(COALESCE(CAST(skill.config AS TEXT), '')) AS raw_config,
                    LOWER(COALESCE(CAST(skill.toolkit_content AS TEXT), '')) AS raw_toolkit_content,
                    LOWER(COALESCE(CAST(skill.toolkit_meta AS TEXT), '')) AS raw_toolkit_meta,
                    LOWER(COALESCE(CAST(skill.skill_md AS TEXT), '')) AS raw_skill_md,
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(COALESCE(CAST(skill.config AS TEXT), '')), '-', '_'), ' ', '_'), '.', '_'), ':', '_'), '/', '_'), CHR(92), '_'), '__', '_'), '__', '_'), '__', '_'), '__', '_') AS normalized_config,
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(COALESCE(CAST(skill.toolkit_content AS TEXT), '')), '-', '_'), ' ', '_'), '.', '_'), ':', '_'), '/', '_'), CHR(92), '_'), '__', '_'), '__', '_'), '__', '_'), '__', '_') AS normalized_toolkit_content,
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(COALESCE(CAST(skill.toolkit_meta AS TEXT), '')), '-', '_'), ' ', '_'), '.', '_'), ':', '_'), '/', '_'), CHR(92), '_'), '__', '_'), '__', '_'), '__', '_'), '__', '_') AS normalized_toolkit_meta,
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(COALESCE(CAST(skill.skill_md AS TEXT), '')), '-', '_'), ' ', '_'), '.', '_'), ':', '_'), '/', '_'), CHR(92), '_'), '__', '_'), '__', '_'), '__', '_'), '__', '_') AS normalized_skill_md
                FROM skills AS skill
            ),
            retired_skills AS (
                SELECT skill.id
                FROM candidate_skills AS skill
                WHERE skill.raw_config LIKE ANY(:retired_raw_patterns)
                   OR skill.raw_toolkit_content LIKE ANY(:retired_raw_patterns)
                   OR skill.raw_toolkit_meta LIKE ANY(:retired_raw_patterns)
                   OR skill.raw_skill_md LIKE ANY(:retired_raw_patterns)
                   OR skill.normalized_config LIKE ANY(:retired_normalized_patterns)
                   OR skill.normalized_toolkit_content LIKE ANY(:retired_normalized_patterns)
                   OR skill.normalized_toolkit_meta LIKE ANY(:retired_normalized_patterns)
                   OR skill.normalized_skill_md LIKE ANY(:retired_normalized_patterns)
            )
            UPDATE agent_skill_grants AS skill_grant
            SET enabled = false,
                is_deleted = true,
                deleted_at = NOW(),
                delete_level = 'admin',
                recycle_stage = 'module',
                promoted_to_global_at = NULL,
                updated_at = NOW()
            WHERE skill_grant.skill_id IN (SELECT id FROM retired_skills)
              AND skill_grant.is_deleted = false
            """),
        _retired_pattern_params(),
    )


def _retire_skills_by_skill_payloads(bind: sa.Connection) -> None:
    required_skill_columns = (
        "id",
        "config",
        "toolkit_content",
        "toolkit_meta",
        "skill_md",
        "is_active",
        "is_deleted",
        "deleted_at",
        "delete_level",
        "recycle_stage",
        "promoted_to_global_at",
        "updated_at",
    )
    if not _has_columns(bind, "skills", required_skill_columns):
        return
    status_assignment = (
        "status = 'disabled'," if "status" in _columns(bind, "skills") else ""
    )
    bind.execute(
        text(
            """
            WITH candidate_skills AS (
                SELECT
                    skill.id,
                    LOWER(COALESCE(CAST(skill.config AS TEXT), '')) AS raw_config,
                    LOWER(COALESCE(CAST(skill.toolkit_content AS TEXT), '')) AS raw_toolkit_content,
                    LOWER(COALESCE(CAST(skill.toolkit_meta AS TEXT), '')) AS raw_toolkit_meta,
                    LOWER(COALESCE(CAST(skill.skill_md AS TEXT), '')) AS raw_skill_md,
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(COALESCE(CAST(skill.config AS TEXT), '')), '-', '_'), ' ', '_'), '.', '_'), ':', '_'), '/', '_'), CHR(92), '_'), '__', '_'), '__', '_'), '__', '_'), '__', '_') AS normalized_config,
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(COALESCE(CAST(skill.toolkit_content AS TEXT), '')), '-', '_'), ' ', '_'), '.', '_'), ':', '_'), '/', '_'), CHR(92), '_'), '__', '_'), '__', '_'), '__', '_'), '__', '_') AS normalized_toolkit_content,
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(COALESCE(CAST(skill.toolkit_meta AS TEXT), '')), '-', '_'), ' ', '_'), '.', '_'), ':', '_'), '/', '_'), CHR(92), '_'), '__', '_'), '__', '_'), '__', '_'), '__', '_') AS normalized_toolkit_meta,
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LOWER(COALESCE(CAST(skill.skill_md AS TEXT), '')), '-', '_'), ' ', '_'), '.', '_'), ':', '_'), '/', '_'), CHR(92), '_'), '__', '_'), '__', '_'), '__', '_'), '__', '_') AS normalized_skill_md
                FROM skills AS skill
            ),
            retired_skills AS (
                SELECT skill.id
                FROM candidate_skills AS skill
                WHERE skill.raw_config LIKE ANY(:retired_raw_patterns)
                   OR skill.raw_toolkit_content LIKE ANY(:retired_raw_patterns)
                   OR skill.raw_toolkit_meta LIKE ANY(:retired_raw_patterns)
                   OR skill.raw_skill_md LIKE ANY(:retired_raw_patterns)
                   OR skill.normalized_config LIKE ANY(:retired_normalized_patterns)
                   OR skill.normalized_toolkit_content LIKE ANY(:retired_normalized_patterns)
                   OR skill.normalized_toolkit_meta LIKE ANY(:retired_normalized_patterns)
                   OR skill.normalized_skill_md LIKE ANY(:retired_normalized_patterns)
            )
            UPDATE skills AS skill
            SET is_active = false,
                __STATUS_ASSIGNMENT__
                is_deleted = true,
                deleted_at = NOW(),
                delete_level = 'admin',
                recycle_stage = 'module',
                promoted_to_global_at = NULL,
                updated_at = NOW()
            WHERE skill.id IN (SELECT id FROM retired_skills)
              AND skill.is_deleted = false
            """.replace("__STATUS_ASSIGNMENT__", status_assignment)
        ),
        _retired_pattern_params(),
    )


def upgrade() -> None:
    bind = op.get_bind()
    _retire_agent_skill_grants_by_skill_payloads(bind)
    _retire_skills_by_skill_payloads(bind)


def downgrade() -> None:
    pass
