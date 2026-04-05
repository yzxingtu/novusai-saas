"""
AI data intelligence package with lazy exports.
AI 数据智能包使用延迟导出，避免子模块循环导入。
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ai.data_intelligence.readonly_executor import (
        QueryResult,  # noqa: F401
        ReadOnlyExecutor,  # noqa: F401
    )
    from app.ai.data_intelligence.result_formatter import (
        FormattedResult,  # noqa: F401
        ResultFormatter,  # noqa: F401
    )
    from app.ai.data_intelligence.schema_provider import (
        ColumnSchema,  # noqa: F401
        SchemaProvider,  # noqa: F401
        TableSchema,  # noqa: F401
    )
    from app.ai.data_intelligence.sql_safety import (
        SQLSafetyValidator,  # noqa: F401
        SQLValidationResult,  # noqa: F401
        extract_table_names,  # noqa: F401
    )
    from app.ai.data_intelligence.tenant_isolation import (
        TenantIsolationError,  # noqa: F401
        TenantIsolationInjector,  # noqa: F401
    )
    from app.ai.data_intelligence.text_to_sql import (
        ConversationRound,  # noqa: F401
        GeneratedSQL,  # noqa: F401
        TextToSQLGenerator,  # noqa: F401
    )

_EXPORTS: dict[str, tuple[str, str]] = {
    "ColumnSchema": ("app.ai.data_intelligence.schema_provider", "ColumnSchema"),
    "TableSchema": ("app.ai.data_intelligence.schema_provider", "TableSchema"),
    "SchemaProvider": ("app.ai.data_intelligence.schema_provider", "SchemaProvider"),
    "SQLSafetyValidator": (
        "app.ai.data_intelligence.sql_safety",
        "SQLSafetyValidator",
    ),
    "SQLValidationResult": (
        "app.ai.data_intelligence.sql_safety",
        "SQLValidationResult",
    ),
    "extract_table_names": (
        "app.ai.data_intelligence.sql_safety",
        "extract_table_names",
    ),
    "TenantIsolationInjector": (
        "app.ai.data_intelligence.tenant_isolation",
        "TenantIsolationInjector",
    ),
    "TenantIsolationError": (
        "app.ai.data_intelligence.tenant_isolation",
        "TenantIsolationError",
    ),
    "QueryResult": ("app.ai.data_intelligence.readonly_executor", "QueryResult"),
    "ReadOnlyExecutor": (
        "app.ai.data_intelligence.readonly_executor",
        "ReadOnlyExecutor",
    ),
    "ConversationRound": (
        "app.ai.data_intelligence.text_to_sql",
        "ConversationRound",
    ),
    "GeneratedSQL": ("app.ai.data_intelligence.text_to_sql", "GeneratedSQL"),
    "TextToSQLGenerator": (
        "app.ai.data_intelligence.text_to_sql",
        "TextToSQLGenerator",
    ),
    "FormattedResult": (
        "app.ai.data_intelligence.result_formatter",
        "FormattedResult",
    ),
    "ResultFormatter": (
        "app.ai.data_intelligence.result_formatter",
        "ResultFormatter",
    ),
}

__all__ = [
    "ColumnSchema",
    "TableSchema",
    "SchemaProvider",
    "SQLSafetyValidator",
    "SQLValidationResult",
    "extract_table_names",
    "TenantIsolationInjector",
    "TenantIsolationError",
    "QueryResult",
    "ReadOnlyExecutor",
    "ConversationRound",
    "GeneratedSQL",
    "TextToSQLGenerator",
    "FormattedResult",
    "ResultFormatter",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
