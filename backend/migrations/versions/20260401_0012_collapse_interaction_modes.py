"""Collapse legacy interaction modes to trusted_auto

Revision ID: 20260401_int_modes
Revises: 20260401_drop_ephem_docs
Create Date: 2026-04-01
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260401_int_modes"
down_revision: str | Sequence[str] | None = "20260401_drop_ephem_docs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_MODES = {"observe", "suggest"}
_REMOVED_MODES = {"confirm"}
_SUPPORTED_MODES = {"trusted_auto"}
_MODE_KEYS = {
    "interaction_mode",
    "interaction_mode_requested",
    "interaction_mode_effective",
    "downgraded_from",
}


def _normalize_mode(value: Any) -> Any:
    if value in _LEGACY_MODES or value in _REMOVED_MODES:
        return "trusted_auto"
    return value


def _normalize_json_payload(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        changed = False
        data: dict[str, Any] = {}
        for key, item in value.items():
            next_item, item_changed = _normalize_json_payload(item)
            data[key] = next_item
            changed = changed or item_changed

            if key in _MODE_KEYS:
                normalized = _normalize_mode(data[key])
                if normalized != data[key]:
                    data[key] = normalized
                    changed = True

            if key == "interaction_mode_effective" and data[key] not in _SUPPORTED_MODES:
                data[key] = "trusted_auto"
                changed = True

            if (
                key == "interaction_mode_requested"
                and data[key] is not None
                and data[key] not in _SUPPORTED_MODES
            ):
                data[key] = "trusted_auto"
                changed = True

            if key == "downgraded_from" and (
                data[key] in _LEGACY_MODES or data[key] in _REMOVED_MODES
            ):
                data[key] = "trusted_auto"
                changed = True

        return data, changed

    if isinstance(value, list):
        changed = False
        next_items: list[Any] = []
        for item in value:
            next_item, item_changed = _normalize_json_payload(item)
            next_items.append(next_item)
            changed = changed or item_changed
        return next_items, changed

    return value, False


def _normalize_dict_payload(value: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    normalized, changed = _normalize_json_payload(value)
    if not isinstance(normalized, dict):
        # Should not happen; fall back to identity to keep type stable
        return value, changed
    return normalized, changed


def upgrade() -> None:
    bind = op.get_bind()

    conversations = sa.table(
        "agent_conversations",
        sa.column("id", sa.Integer()),
        sa.column("metadata", sa.JSON()),
    )
    conversation_messages = sa.table(
        "conversation_messages",
        sa.column("id", sa.Integer()),
        sa.column("metadata", sa.JSON()),
        sa.column("tool_calls", sa.JSON()),
    )
    execution_decisions = sa.table(
        "execution_decisions",
        sa.column("id", sa.Integer()),
        sa.column("evidence", sa.JSON()),
    )

    rows = bind.execute(
        sa.select(conversations.c.id, conversations.c.metadata)
    ).fetchall()
    for row in rows:
        metadata = row.metadata
        if not isinstance(metadata, dict):
            continue
        normalized, changed = _normalize_json_payload(metadata)
        if not changed:
            continue
        bind.execute(
            conversations.update()
            .where(conversations.c.id == row.id)
            .values(metadata=normalized)
        )

    rows = bind.execute(
        sa.select(
            conversation_messages.c.id,
            conversation_messages.c.metadata,
            conversation_messages.c.tool_calls,
        )
    ).fetchall()
    for row in rows:
        updates: dict[str, Any] = {}
        if isinstance(row.metadata, dict):
            normalized_meta, meta_changed = _normalize_json_payload(row.metadata)
            if meta_changed:
                updates["metadata"] = normalized_meta
        normalized_tool_calls, tool_calls_changed = _normalize_json_payload(
            row.tool_calls
        )
        if tool_calls_changed:
            updates["tool_calls"] = normalized_tool_calls
        if not updates:
            continue
        bind.execute(
            conversation_messages.update()
            .where(conversation_messages.c.id == row.id)
            .values(**updates)
        )

    rows = bind.execute(
        sa.select(execution_decisions.c.id, execution_decisions.c.evidence)
    ).fetchall()
    for row in rows:
        evidence = row.evidence
        if not isinstance(evidence, dict):
            continue
        normalized, changed = _normalize_json_payload(evidence)
        if not changed:
            continue
        bind.execute(
            execution_decisions.update()
            .where(execution_decisions.c.id == row.id)
            .values(evidence=normalized)
        )


def downgrade() -> None:
    # The old values are intentionally not restored; downgrade keeps `trusted_auto`.
    # / 不恢复旧值；降级时保持 trusted_auto，避免重新引入已移除模式。
    return None
