"""
Shared SQL analysis helpers for AI runtime guards.
AI 运行时安全链路共享的 SQL 解析辅助工具。
"""

from __future__ import annotations  # noqa: I001

from dataclasses import dataclass
from collections.abc import Iterable

import sqlparse
from sqlparse.sql import (
    Function,
    Identifier,
    IdentifierList,
    Parenthesis,
    Statement,
    TokenList,
    Where,
)
from sqlparse.tokens import DML, Comment, Keyword, Newline, Whitespace

_SOURCE_KEYWORDS = {
    "FROM",
    "JOIN",
    "LEFT JOIN",
    "RIGHT JOIN",
    "INNER JOIN",
    "OUTER JOIN",
    "FULL JOIN",
    "CROSS JOIN",
}
_TRAILING_CLAUSE_KEYWORDS = {
    "GROUP BY",
    "ORDER BY",
    "LIMIT",
    "HAVING",
    "UNION",
    "EXCEPT",
    "INTERSECT",
}
_NON_TABLE_NAMES = {
    "select",
    "where",
    "and",
    "or",
    "not",
    "in",
    "lateral",
    "unnest",
    "generate_series",
}


@dataclass(frozen=True, slots=True)
class SQLTableReference:
    table_name: str
    alias: str | None = None
    schema_name: str | None = None


def parse_sql_statement(sql: str) -> Statement | None:
    parsed = sqlparse.parse(sql or "")
    return parsed[0] if parsed else None


def starts_with_select_or_cte(sql: str) -> bool:
    statement = parse_sql_statement(sql)
    return bool(statement and statement.get_type() == "SELECT")


def contains_sql_comments(sql: str) -> bool:
    statement = parse_sql_statement(sql)
    if statement is None:
        return False
    return any(token.ttype in Comment for token in statement.flatten())


def extract_called_functions(sql: str) -> set[str]:
    statement = parse_sql_statement(sql)
    if statement is None:
        return set()

    found: set[str] = set()

    def _walk(token: TokenList) -> None:
        if isinstance(token, Function):
            name = str(token.get_name() or "").strip().lower()
            if name:
                found.add(name)
        if hasattr(token, "tokens"):
            for child in token.tokens:
                if isinstance(child, TokenList):
                    _walk(child)

    _walk(statement)
    return found


def find_keyword_sequences(
    sql: str,
    sequences: Iterable[tuple[str, ...]],
) -> list[str]:
    statement = parse_sql_statement(sql)
    if statement is None:
        return []

    flat_keywords = [
        token.normalized.upper()
        for token in statement.flatten()
        if token.ttype in Keyword or token.ttype in DML
    ]
    if not flat_keywords:
        return []

    hits: list[str] = []
    for sequence in sequences:
        if not sequence:
            continue
        normalized_sequence = tuple(part.upper() for part in sequence if part)
        seq_len = len(normalized_sequence)
        if not seq_len:
            continue
        for index in range(0, len(flat_keywords) - seq_len + 1):
            if tuple(flat_keywords[index : index + seq_len]) == normalized_sequence:
                hits.append(" ".join(normalized_sequence))
                break
    return hits


def extract_table_references(sql: str) -> list[SQLTableReference]:
    statement = parse_sql_statement(sql)
    if statement is None:
        return []

    cte_names = _extract_cte_names(statement)
    refs: list[SQLTableReference] = []
    seen: set[tuple[str | None, str, str | None]] = set()

    def _walk(token_list: TokenList) -> None:
        expect_source = False
        for token in _iter_meaningful_tokens(token_list):
            normalized = (
                token.normalized.upper()
                if hasattr(token, "normalized")
                else str(token).upper()
            )
            if token.ttype in Keyword and normalized in _SOURCE_KEYWORDS:
                expect_source = True
                continue

            if expect_source and token.ttype in Keyword and normalized == "ONLY":
                continue

            if expect_source:
                for identifier in _iter_reference_identifiers(token):
                    table_name = str(
                        identifier.get_real_name() or identifier.get_name() or ""
                    ).strip()
                    if not table_name:
                        continue
                    lowered = table_name.lower()
                    if lowered in cte_names or lowered in _NON_TABLE_NAMES:
                        continue
                    alias = str(identifier.get_alias() or "").strip() or None
                    schema_name = (
                        str(identifier.get_parent_name() or "").strip() or None
                    )
                    key = (
                        schema_name.lower() if schema_name else None,
                        lowered,
                        alias.lower() if alias else None,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    refs.append(
                        SQLTableReference(
                            table_name=table_name,
                            alias=alias,
                            schema_name=schema_name,
                        )
                    )
                expect_source = False

            if isinstance(token, TokenList):
                _walk(token)

    _walk(statement)

    return refs


def extract_table_names(sql: str) -> set[str]:
    return {ref.table_name.lower() for ref in extract_table_references(sql)}


def extract_table_name_list(sql: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for ref in extract_table_references(sql):
        name = ref.table_name.lower()
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def extract_select_aggregates(sql: str) -> list[str]:
    expressions = _extract_top_level_clause_expressions(
        statement=parse_sql_statement(sql),
        start_keywords={"SELECT"},
        stop_keywords={"FROM"},
    )
    metrics: list[str] = []
    seen: set[str] = set()
    for expression in expressions:
        function_name, argument = _extract_leading_function_call(expression)
        if (
            function_name not in {"count", "sum", "avg", "min", "max"}
            or argument is None
        ):
            continue
        formatted = f"{function_name.upper()}({_normalize_inline_whitespace(argument)})"
        key = formatted.lower()
        if key in seen:
            continue
        seen.add(key)
        metrics.append(formatted)
    return metrics


def extract_group_by_expressions(
    sql: str, *, max_items: int | None = None
) -> list[str]:
    expressions = _extract_top_level_clause_expressions(
        statement=parse_sql_statement(sql),
        start_keywords={"GROUP BY"},
        stop_keywords=_TRAILING_CLAUSE_KEYWORDS,
    )
    normalized = [
        _normalize_inline_whitespace(item) for item in expressions if item.strip()
    ]
    if max_items is not None and max_items >= 0:
        return normalized[:max_items]
    return normalized


def has_top_level_limit(sql: str) -> bool:
    statement = parse_sql_statement(sql)
    if statement is None:
        return False
    for token in _iter_top_level_meaningful_tokens(statement):
        if token.ttype in Keyword and token.normalized.upper() == "LIMIT":
            return True
    return False


def inject_outer_where_conditions(sql: str, conditions: list[str]) -> str:
    if not conditions:
        return sql
    statement = parse_sql_statement(sql)
    if statement is None:
        return sql

    clause = " AND ".join(conditions)
    offsets = list(_iter_top_level_tokens_with_offsets(statement))
    where_token = next((item for item in offsets if isinstance(item[0], Where)), None)
    if where_token is not None:
        token, start, _ = where_token
        token_text = str(token)
        keyword_index = token_text.upper().find("WHERE")
        if keyword_index >= 0:
            insert_at = start + keyword_index + len("WHERE")
            return sql[:insert_at] + f" {clause} AND" + sql[insert_at:]

    insert_at = _find_trailing_clause_start(offsets)
    body, terminator = _split_sql_terminator(sql)
    if insert_at is None:
        return f"{body.rstrip()} WHERE {clause}{terminator}"
    prefix = sql[:insert_at].rstrip()
    suffix = sql[insert_at:]
    spacer = "" if suffix.startswith(" ") else " "
    return f"{prefix} WHERE {clause}{spacer}{suffix}"


def append_outer_where_conditions(sql: str, conditions: list[str]) -> str:
    if not conditions:
        return sql
    statement = parse_sql_statement(sql)
    if statement is None:
        return sql

    clause = " AND ".join(conditions)
    offsets = list(_iter_top_level_tokens_with_offsets(statement))
    where_token = next((item for item in offsets if isinstance(item[0], Where)), None)
    if where_token is None:
        return inject_outer_where_conditions(sql, conditions)

    insert_at = _find_trailing_clause_start(offsets)
    if insert_at is None:
        body, terminator = _split_sql_terminator(sql)
        return f"{body.rstrip()} AND {clause}{terminator}"
    prefix = sql[:insert_at].rstrip()
    suffix = sql[insert_at:]
    spacer = "" if suffix.startswith(" ") else " "
    return f"{prefix} AND {clause}{spacer}{suffix}"


def append_limit_clause(sql: str, max_rows: int) -> str:
    if max_rows <= 0:
        return sql
    if has_top_level_limit(sql):
        return sql.strip().rstrip(";")
    body, terminator = _split_sql_terminator(sql)
    return f"{body.rstrip()} LIMIT {max_rows}{terminator}"


def is_safe_sql_identifier(name: str | None) -> bool:
    raw = str(name or "")
    if not raw:
        return False
    first = raw[0]
    if not (first == "_" or "a" <= first <= "z"):
        return False
    for ch in raw[1:]:
        if ch == "_" or ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            continue
        return False
    return True


def _iter_reference_identifiers(token) -> Iterable[Identifier]:
    if isinstance(token, Identifier):
        if any(isinstance(child, Parenthesis) for child in token.tokens):
            return []
        return [token]
    if isinstance(token, IdentifierList):
        return [
            identifier
            for identifier in token.get_identifiers()
            if isinstance(identifier, Identifier)
            and not any(isinstance(child, Parenthesis) for child in identifier.tokens)
        ]
    return []


def _extract_cte_names(statement: Statement) -> set[str]:
    names: set[str] = set()
    saw_with = False
    for token in _iter_top_level_meaningful_tokens(statement):
        if not saw_with:
            if token.ttype in Keyword and token.normalized.upper() == "WITH":
                saw_with = True
            continue
        if token.ttype in DML and token.normalized.upper() == "SELECT":
            break
        for identifier in _iter_cte_identifiers(token):
            name = str(
                identifier.get_real_name() or identifier.get_name() or ""
            ).strip()
            if name:
                names.add(name.lower())
    return names


def _iter_cte_identifiers(token) -> Iterable[Identifier]:
    if isinstance(token, Identifier):
        return (
            [token]
            if any(isinstance(child, Parenthesis) for child in token.tokens)
            else []
        )
    if isinstance(token, IdentifierList):
        return [
            identifier
            for identifier in token.get_identifiers()
            if isinstance(identifier, Identifier)
            and any(isinstance(child, Parenthesis) for child in identifier.tokens)
        ]
    return []


def _iter_top_level_meaningful_tokens(statement: Statement):
    yield from _iter_meaningful_tokens(statement)


def _iter_meaningful_tokens(token_list: TokenList):
    for token in token_list.tokens:
        if token.is_whitespace or token.ttype in (Whitespace, Newline):
            continue
        yield token


def _iter_top_level_tokens_with_offsets(statement: Statement):
    offset = 0
    for token in statement.tokens:
        text = str(token)
        start = offset
        offset += len(text)
        yield token, start, offset


def _find_trailing_clause_start(offsets) -> int | None:
    for token, start, _ in offsets:
        if token.is_whitespace or token.ttype in (Whitespace, Newline):
            continue
        if (
            token.ttype in Keyword
            and token.normalized.upper() in _TRAILING_CLAUSE_KEYWORDS
        ):
            return start
    return None


def _extract_top_level_clause_expressions(
    *,
    statement: Statement | None,
    start_keywords: set[str],
    stop_keywords: set[str],
) -> list[str]:
    if statement is None:
        return []

    collecting = False
    parts: list[str] = []
    for token in _iter_top_level_meaningful_tokens(statement):
        normalized = (
            token.normalized.upper()
            if hasattr(token, "normalized")
            else str(token).upper()
        )
        if not collecting:
            if normalized in start_keywords:
                collecting = True
            continue
        if token.ttype in Keyword and normalized in stop_keywords:
            break
        parts.append(str(token))

    if not parts:
        return []
    return _split_top_level_csv(" ".join(parts).strip())


def _split_top_level_csv(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_single_quote = False
    in_double_quote = False
    escape_next = False

    for ch in text:
        if in_single_quote:
            current.append(ch)
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == "'":
                in_single_quote = False
            continue
        if in_double_quote:
            current.append(ch)
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_double_quote = False
            continue
        if ch == "'":
            in_single_quote = True
            current.append(ch)
            continue
        if ch == '"':
            in_double_quote = True
            current.append(ch)
            continue
        if ch == "(":
            depth += 1
            current.append(ch)
            continue
        if ch == ")" and depth > 0:
            depth -= 1
            current.append(ch)
            continue
        if ch == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
            continue
        current.append(ch)

    item = "".join(current).strip()
    if item:
        parts.append(item)
    return parts


def _extract_leading_function_call(expression: str) -> tuple[str | None, str | None]:
    raw = expression.strip()
    if not raw:
        return None, None

    idx = 0
    while idx < len(raw) and raw[idx].isspace():
        idx += 1
    start = idx
    while idx < len(raw) and (raw[idx].isalpha() or raw[idx] == "_"):
        idx += 1
    function_name = raw[start:idx].lower()
    while idx < len(raw) and raw[idx].isspace():
        idx += 1
    if not function_name or idx >= len(raw) or raw[idx] != "(":
        return None, None
    argument, end_idx = _extract_parenthesized_segment(raw, idx)
    if argument is None:
        return None, None
    return function_name, argument


def _extract_parenthesized_segment(
    text: str, start_index: int
) -> tuple[str | None, int]:
    depth = 0
    content: list[str] = []
    in_single_quote = False
    in_double_quote = False
    escape_next = False

    for index in range(start_index, len(text)):
        ch = text[index]
        if index == start_index:
            depth = 1
            continue
        if in_single_quote:
            content.append(ch)
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == "'":
                in_single_quote = False
            continue
        if in_double_quote:
            content.append(ch)
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_double_quote = False
            continue
        if ch == "'":
            in_single_quote = True
            content.append(ch)
            continue
        if ch == '"':
            in_double_quote = True
            content.append(ch)
            continue
        if ch == "(":
            depth += 1
            content.append(ch)
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                return "".join(content).strip(), index
            content.append(ch)
            continue
        content.append(ch)

    return None, len(text)


def _normalize_inline_whitespace(text: str) -> str:
    return " ".join(str(text or "").split())


def _split_sql_terminator(sql: str) -> tuple[str, str]:
    stripped = sql.rstrip()
    if stripped.endswith(";"):
        body = stripped[:-1].rstrip()
        trailing = sql[len(stripped) :]
        return body, ";" + trailing
    trailing = sql[len(stripped) :]
    return stripped, trailing


__all__ = [
    "SQLTableReference",
    "append_outer_where_conditions",
    "append_limit_clause",
    "contains_sql_comments",
    "extract_called_functions",
    "extract_group_by_expressions",
    "extract_select_aggregates",
    "extract_table_name_list",
    "extract_table_names",
    "extract_table_references",
    "find_keyword_sequences",
    "has_top_level_limit",
    "inject_outer_where_conditions",
    "is_safe_sql_identifier",
    "parse_sql_statement",
    "starts_with_select_or_cte",
]
