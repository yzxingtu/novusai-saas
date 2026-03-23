from __future__ import annotations

import re
from typing import Any

from sqlalchemy import asc, desc

DEFAULT_PAGE_NUMBER = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
FILTER_RE = re.compile(r"^filter\[(?P<field>[a-zA-Z0-9_]+)\]\[(?P<operator>[a-z]+)\]$")


def parse_page(query_params: Any) -> tuple[int, int]:
    try:
        page = int(query_params.get("page[number]") or query_params.get("page") or DEFAULT_PAGE_NUMBER)
    except (TypeError, ValueError):
        page = DEFAULT_PAGE_NUMBER
    try:
        page_size = int(query_params.get("page[size]") or query_params.get("page_size") or DEFAULT_PAGE_SIZE)
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    return max(1, page), max(1, min(page_size, MAX_PAGE_SIZE))


def parse_filters(query_params: Any, allowed_fields: set[str]) -> list[tuple[str, str, str]]:
    filters: list[tuple[str, str, str]] = []
    for key, value in query_params.items():
        matched = FILTER_RE.match(str(key))
        if not matched:
            continue
        field = matched.group("field")
        operator = matched.group("operator")
        if field not in allowed_fields:
            continue
        filters.append((field, operator, str(value)))
    return filters


def apply_filters(statement: Any, model_cls: type[Any], filters: list[tuple[str, str, str]]) -> Any:
    for field, operator, raw_value in filters:
        column = getattr(model_cls, field, None)
        if column is None:
            continue
        if operator == "eq":
            statement = statement.where(column == raw_value)
        elif operator == "ilike":
            statement = statement.where(column.ilike(f"%{raw_value}%"))
        elif operator == "in":
            values = [item.strip() for item in raw_value.split(",") if item.strip()]
            if values:
                statement = statement.where(column.in_(values))
        elif operator == "gte":
            statement = statement.where(column >= raw_value)
        elif operator == "lte":
            statement = statement.where(column <= raw_value)
    return statement


def parse_sort(query_params: Any, allowed_fields: set[str], default_sort: str = "-updated_at") -> list[tuple[str, bool]]:
    raw = str(query_params.get("sort") or default_sort or "").strip()
    if not raw:
        return []
    result: list[tuple[str, bool]] = []
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        is_desc = token.startswith("-")
        field = token[1:] if is_desc else token
        if field not in allowed_fields:
            continue
        result.append((field, is_desc))
    return result


def apply_sort(statement: Any, model_cls: type[Any], sorts: list[tuple[str, bool]]) -> Any:
    order_clauses = []
    for field, is_desc in sorts:
        column = getattr(model_cls, field, None)
        if column is None:
            continue
        order_clauses.append(desc(column) if is_desc else asc(column))
    if order_clauses:
        statement = statement.order_by(*order_clauses)
    return statement
