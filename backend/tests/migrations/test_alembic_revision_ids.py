"""Alembic revision id guards."""

from __future__ import annotations

import ast
from pathlib import Path

from app.cli import _BACKEND_DIR, _discover_plugin_migration_paths

_ALEMBIC_VERSION_NUM_MAX_LENGTH = 32


def _migration_version_dirs() -> list[Path]:
    roots = [_BACKEND_DIR / "migrations" / "versions"]
    roots.extend(Path(path) for path in _discover_plugin_migration_paths())
    return roots


def _extract_revision_literal(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "revision"
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    return node.value.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "revision"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value

    return None


def test_migration_version_dirs_only_contain_revision_scripts() -> None:
    """Version dirs should not contain helper modules such as __init__.py."""

    unexpected_files: list[Path] = []

    for root in _migration_version_dirs():
        for path in sorted(root.glob("*.py")):
            if not _extract_revision_literal(path):
                unexpected_files.append(path)

    assert unexpected_files == [], (
        "Migration version directories must only contain real revision scripts: "
        + ", ".join(str(path) for path in unexpected_files)
    )


def test_alembic_revision_ids_fit_version_table_and_are_unique() -> None:
    """Alembic version_num defaults to VARCHAR(32), so revision ids must fit."""

    seen: dict[str, Path] = {}

    for root in _migration_version_dirs():
        for path in sorted(root.glob("*.py")):
            revision = _extract_revision_literal(path)
            assert revision, f"Missing string revision literal in {path}"
            assert len(revision) <= _ALEMBIC_VERSION_NUM_MAX_LENGTH, (
                f"Revision '{revision}' in {path} exceeds "
                f"{_ALEMBIC_VERSION_NUM_MAX_LENGTH} characters"
            )
            assert revision not in seen, (
                f"Duplicate revision '{revision}' in {path} and {seen[revision]}"
            )
            seen[revision] = path
