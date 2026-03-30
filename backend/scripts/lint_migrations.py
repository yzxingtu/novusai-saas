#!/usr/bin/env python3
"""
Migration safety linter — detect dangerous patterns in Alembic migration files.

Checks:
  [PERM-RENAME]  REPLACE on permissions table without DELETE guard
  [RAW-FSTRING]  f-string SQL (text(f"..."))
  [BARE-EXCEPT]  try/except pass around SQL execution

Usage:
  cd backend
  python scripts/lint_migrations.py                    # scan all
  python scripts/lint_migrations.py --since HEAD~5     # only files changed in last 5 commits
  python scripts/lint_migrations.py path/to/file.py    # scan specific file

Exit code 0 = clean, 1 = warnings found.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_MIGRATION_DIRS = [
    _BACKEND_DIR / "migrations" / "versions",
    *(_BACKEND_DIR / "plugins").glob("*/backend/migrations/versions"),
]

# ──────────────────────────────────────────────────────────────
# Rules
# ──────────────────────────────────────────────────────────────

_RULES: list[tuple[str, str, re.Pattern[str], re.Pattern[str] | None]] = []


def _add_rule(
    code: str,
    message: str,
    trigger: str,
    suppress: str | None = None,
) -> None:
    _RULES.append((
        code,
        message,
        re.compile(trigger, re.IGNORECASE),
        re.compile(suppress, re.IGNORECASE) if suppress else None,
    ))


_add_rule(
    "PERM-RENAME",
    "REPLACE on `permissions` without DELETE guard — use "
    "`migrations.helpers.safe_rename_permission_resource()` instead",
    r"""REPLACE\s*\(\s*(?:code|permissions\.code)\s*,""",
    r"""safe_rename_permission_resource|DELETE\s+FROM\s+permissions""",
)

_add_rule(
    "RAW-FSTRING",
    "f-string SQL detected — use text(...).bindparams(...) or migration helpers",
    r"""text\s*\(\s*f["']""",
    None,
)

_add_rule(
    "BARE-EXCEPT",
    "Bare except around SQL may hide InFailedSqlTransaction — use begin_nested()",
    r"""except\s*(?:Exception)?\s*:\s*\n\s*pass""",
    r"""begin_nested""",
)

_add_rule(
    "UNIQUE-REPLACE",
    "REPLACE on a column with likely unique constraint without DELETE guard — "
    "use `migrations.helpers.safe_rename_unique_column_value()`",
    r"""UPDATE\s+\w+\s+SET\s+\w+\s*=\s*REPLACE\s*\(""",
    r"""safe_rename_unique_column_value|safe_rename_permission_resource|DELETE\s+FROM""",
)


# ──────────────────────────────────────────────────────────────
# Scanner
# ──────────────────────────────────────────────────────────────

class Warning:
    __slots__ = ("path", "line", "code", "message")

    def __init__(self, path: Path, line: int, code: str, message: str):
        self.path = path
        self.line = line
        self.code = code
        self.message = message

    def __str__(self) -> str:
        rel = self.path.relative_to(_BACKEND_DIR) if self.path.is_relative_to(_BACKEND_DIR) else self.path
        return f"  {rel}:{self.line}: [{self.code}] {self.message}"


def lint_file(path: Path) -> list[Warning]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    warnings: list[Warning] = []

    for code, message, trigger, suppress in _RULES:
        if suppress and suppress.search(content):
            continue
        for i, raw_line in enumerate(content.splitlines(), start=1):
            if trigger.search(raw_line):
                warnings.append(Warning(path, i, code, message))

    return warnings


def collect_files(
    paths: list[str] | None = None,
    since: str | None = None,
) -> list[Path]:
    if paths:
        return [Path(p).resolve() for p in paths if p.endswith(".py")]

    if since:
        try:
            r = subprocess.run(
                ["git", "diff", "--name-only", since, "--", "migrations/", "plugins/"],
                capture_output=True, text=True, check=True,
                cwd=str(_BACKEND_DIR),
            )
            return [
                _BACKEND_DIR / line.strip()
                for line in r.stdout.splitlines()
                if line.strip().endswith(".py") and "versions" in line
            ]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    result: list[Path] = []
    for d in _MIGRATION_DIRS:
        if d.is_dir():
            result.extend(sorted(d.glob("*.py")))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint Alembic migration files")
    parser.add_argument("files", nargs="*", help="Specific files to check")
    parser.add_argument("--since", help="Git ref to diff against (e.g. HEAD~3, main)")
    args = parser.parse_args()

    files = collect_files(args.files or None, args.since)
    if not files:
        print("[lint_migrations] No migration files to check.")
        return

    all_warnings: list[Warning] = []
    for f in files:
        all_warnings.extend(lint_file(f))

    if all_warnings:
        print(f"[lint_migrations] {len(all_warnings)} warning(s) in {len(files)} file(s):\n")
        for w in all_warnings:
            print(w)
        print(
            "\n  Tip: use `migrations.helpers.safe_rename_permission_resource()` "
            "or `safe_rename_unique_column_value()` for safe renames."
        )
        sys.exit(1)
    else:
        print(f"[lint_migrations] OK — {len(files)} file(s) checked, no issues.")


if __name__ == "__main__":
    main()
