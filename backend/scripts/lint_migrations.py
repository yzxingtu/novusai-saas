#!/usr/bin/env python3
"""
Migration safety linter — detect dangerous patterns in Alembic migration files.

Checks:
  [PERM-RENAME]      REPLACE on permissions table without DELETE guard
  [RAW-FSTRING]      f-string SQL (text(f"..."))
  [BARE-EXCEPT]      try/except pass around SQL execution
  [UNIQUE-REPLACE]   REPLACE on likely unique columns without DELETE guard
  [NON-REVISION]     Non-revision Python file under versions/
  [UNBOUNDED-STRING] sa.Column(..., sa.String()) without explicit length
  [SQL-EXCEPT]       execute() wrapped in swallowed Exception handler without savepoint
  [DYNAMIC-SQL]      text(sql) fed from string concatenation / formatting

Usage:
  cd backend
  python scripts/lint_migrations.py                    # scan all
  python scripts/lint_migrations.py --since HEAD~5     # only files changed in last 5 commits
  python scripts/lint_migrations.py path/to/file.py    # scan specific file

Exit code 0 = clean, 1 = warnings found.
"""

from __future__ import annotations

import argparse
import ast
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
# Regex rules
# ──────────────────────────────────────────────────────────────

_RULES: list[tuple[str, str, re.Pattern[str], re.Pattern[str] | None]] = []


def _add_rule(
    code: str,
    message: str,
    trigger: str,
    suppress: str | None = None,
) -> None:
    _RULES.append(
        (
            code,
            message,
            re.compile(trigger, re.IGNORECASE),
            re.compile(suppress, re.IGNORECASE) if suppress else None,
        )
    )


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
        rel = (
            self.path.relative_to(_BACKEND_DIR)
            if self.path.is_relative_to(_BACKEND_DIR)
            else self.path
        )
        return f"  {rel}:{self.line}: [{self.code}] {self.message}"


def _load_content(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def _extract_revision_literal_from_tree(tree: ast.AST) -> str | None:
    for node in getattr(tree, "body", []):
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


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_attr(node: ast.AST, base: str, attr: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == base
        and node.attr == attr
    )


def _is_text_call(node: ast.Call) -> bool:
    return _is_name(node.func, "text") or _is_attr(node.func, "sa", "text")


def _is_column_call(node: ast.Call) -> bool:
    return _is_name(node.func, "Column") or _is_attr(node.func, "sa", "Column")


def _is_execute_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "execute"


def _is_begin_nested_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "begin_nested"


def _is_unbounded_string_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if not (_is_name(node.func, "String") or _is_attr(node.func, "sa", "String")):
        return False
    return not node.args and not node.keywords


def _is_dynamic_sql_expr(node: ast.AST) -> bool:
    return isinstance(node, ast.JoinedStr | ast.BinOp) or (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    )


def _contains_execute(nodes: list[ast.stmt]) -> bool:
    return any(
        isinstance(inner, ast.Call) and _is_execute_call(inner)
        for node in nodes
        for inner in ast.walk(node)
    )


def _contains_begin_nested(nodes: list[ast.stmt]) -> bool:
    return any(
        isinstance(inner, ast.Call) and _is_begin_nested_call(inner)
        for node in nodes
        for inner in ast.walk(node)
    )


def _contains_raise(nodes: list[ast.stmt]) -> bool:
    return any(
        isinstance(inner, ast.Raise) for node in nodes for inner in ast.walk(node)
    )


def _is_broad_exception_handler(node: ast.ExceptHandler) -> bool:
    if node.type is None:
        return True
    return isinstance(node.type, ast.Name) and node.type.id == "Exception"


def _collect_assignments(tree: ast.AST) -> dict[str, list[ast.Assign | ast.AnnAssign]]:
    assignments: dict[str, list[ast.Assign | ast.AnnAssign]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignments.setdefault(node.target.id, []).append(node)
    return assignments


def _latest_assignment_before(
    assignments: list[ast.Assign | ast.AnnAssign],
    lineno: int,
) -> ast.AST | None:
    candidates = [
        node
        for node in assignments
        if getattr(node, "lineno", 0) < lineno
        and getattr(node, "value", None) is not None
    ]
    if not candidates:
        return None
    latest = max(candidates, key=lambda node: getattr(node, "lineno", 0))
    return latest.value


def _lint_ast(path: Path, content: str) -> list[Warning]:
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError:
        return []

    warnings: list[Warning] = []

    if path.parent.name == "versions":
        revision = _extract_revision_literal_from_tree(tree)
        if not revision:
            warnings.append(
                Warning(
                    path,
                    1,
                    "NON-REVISION",
                    "Python file under versions/ must declare a string `revision = ...` literal",
                )
            )

    assignments = _collect_assignments(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_column_call(node):
            for arg in node.args[1:]:
                if _is_unbounded_string_call(arg):
                    warnings.append(
                        Warning(
                            path,
                            getattr(arg, "lineno", getattr(node, "lineno", 1)),
                            "UNBOUNDED-STRING",
                            "sa.Column(..., sa.String()) must use an explicit length",
                        )
                    )
                    break

        if isinstance(node, ast.Call) and _is_text_call(node) and node.args:
            sql_expr = node.args[0]
            if isinstance(sql_expr, ast.Name):
                resolved = _latest_assignment_before(
                    assignments.get(sql_expr.id, []),
                    getattr(node, "lineno", 0),
                )
                if resolved is not None:
                    sql_expr = resolved
            if _is_dynamic_sql_expr(sql_expr):
                warnings.append(
                    Warning(
                        path,
                        getattr(node, "lineno", 1),
                        "DYNAMIC-SQL",
                        "text(...) should not be fed from concatenated / formatted SQL identifiers",
                    )
                )

        if (
            isinstance(node, ast.Try)
            and _contains_execute(node.body)
            and not _contains_begin_nested(node.body)
        ):
            for handler in node.handlers:
                if _is_broad_exception_handler(handler) and not _contains_raise(
                    handler.body
                ):
                    warnings.append(
                        Warning(
                            path,
                            getattr(handler, "lineno", getattr(node, "lineno", 1)),
                            "SQL-EXCEPT",
                            "execute() inside try/except must use begin_nested() or re-raise on failure",
                        )
                    )
                    break

    return warnings


def lint_file(path: Path) -> list[Warning]:
    content = _load_content(path)
    if content is None:
        return []

    warnings: list[Warning] = []

    for code, message, trigger, suppress in _RULES:
        if suppress and suppress.search(content):
            continue
        for i, raw_line in enumerate(content.splitlines(), start=1):
            if trigger.search(raw_line):
                warnings.append(Warning(path, i, code, message))

    warnings.extend(_lint_ast(path, content))
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
                capture_output=True,
                text=True,
                check=True,
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
        print(
            f"[lint_migrations] {len(all_warnings)} warning(s) in {len(files)} file(s):\n"
        )
        for w in all_warnings:
            print(w)
        print(
            "\n  Tip: use `migrations.helpers.safe_rename_permission_resource()` "
            "or `safe_rename_unique_column_value()` for safe renames."
        )
        sys.exit(1)

    print(f"[lint_migrations] OK — {len(files)} file(s) checked, no issues.")


if __name__ == "__main__":
    main()
