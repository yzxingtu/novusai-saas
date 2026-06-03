"""中文: 退役 AI 技能目录过滤器。

EN: Retired AI skill catalog filters.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, or_

from app.schemas.ai.invalid_ai_runtime_input import (
    RETIRED_ONLINE_SEARCH_CATALOG_PHRASES,
    RETIRED_ONLINE_SEARCH_CATALOG_TOKENS,
    is_retired_online_search_catalog_reference,
    normalize_ai_runtime_token,
)

_RETIRED_ONLINE_SEARCH_SQL_PATTERNS = tuple(
    dict.fromkeys(
        f"%{str(value).lower()}%"
        for value in (
            *RETIRED_ONLINE_SEARCH_CATALOG_TOKENS,
            *RETIRED_ONLINE_SEARCH_CATALOG_PHRASES,
        )
    )
)
_RETIRED_ONLINE_SEARCH_NORMALIZED_SQL_PATTERNS = tuple(
    dict.fromkeys(
        f"%{normalize_ai_runtime_token(value)}%"
        for value in (
            *RETIRED_ONLINE_SEARCH_CATALOG_TOKENS,
            *RETIRED_ONLINE_SEARCH_CATALOG_PHRASES,
        )
        if normalize_ai_runtime_token(value)
    )
)


def _normalized_text_column(column: Any) -> Any:
    value = func.lower(func.coalesce(column, ""))
    for separator in ("-", " ", ".", ":", "/", "\\"):
        value = func.replace(value, separator, "_")
    for _ in range(4):
        value = func.replace(value, "__", "_")
    return value


def _retired_text_column_condition(column: Any) -> Any:
    value = func.lower(func.coalesce(column, ""))
    normalized = _normalized_text_column(column)
    return or_(
        *(value.like(pattern) for pattern in _RETIRED_ONLINE_SEARCH_SQL_PATTERNS),
        *(
            normalized.like(pattern)
            for pattern in _RETIRED_ONLINE_SEARCH_NORMALIZED_SQL_PATTERNS
        ),
    )


def not_retired_skill_package_condition(package_model: Any) -> Any:
    """中文: SQL 条件，隐藏退役联网搜索技能包。

    EN: SQL condition hiding retired online-search skill packages.
    """
    return and_(
        ~_retired_text_column_condition(package_model.name),
        ~_retired_text_column_condition(package_model.source_plugin),
    )


def not_retired_skill_condition(skill_model: Any) -> Any:
    """中文: SQL 条件，隐藏退役联网搜索技能。

    EN: SQL condition hiding retired online-search skills.
    """
    return and_(
        ~_retired_text_column_condition(skill_model.name),
        ~_retired_text_column_condition(skill_model.key),
        ~_retired_text_column_condition(skill_model.source_ref),
    )


def is_retired_package_instance(package: Any) -> bool:
    if package is None:
        return False
    return any(
        is_retired_online_search_catalog_reference(value)
        for value in (
            getattr(package, "name", None),
            getattr(package, "source_plugin", None),
        )
    )


def is_retired_skill_instance(skill: Any) -> bool:
    if skill is None:
        return False
    if any(
        is_retired_online_search_catalog_reference(value)
        for value in (
            getattr(skill, "name", None),
            getattr(skill, "key", None),
            getattr(skill, "source_ref", None),
        )
    ):
        return True
    return is_retired_package_instance(getattr(skill, "package", None))


__all__ = [
    "is_retired_package_instance",
    "is_retired_skill_instance",
    "not_retired_skill_condition",
    "not_retired_skill_package_condition",
]
