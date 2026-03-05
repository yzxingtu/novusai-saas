"""
AI 数据智能模块（Text-to-SQL + 业务操作）

核心组件：
- SchemaProvider: 数据字典服务，管理表白名单和列过滤
- SQLSafetyValidator: SQL 六重安全校验
- TenantIsolationInjector: 自动注入 tenant_id 隔离条件
- ReadOnlyExecutor: 只读数据库执行器
- TextToSQLGenerator: LLM 自然语言转 SQL 生成器
- ResultFormatter: 查询结果智能格式化

安全链路：
  SchemaProvider → TextToSQLGenerator → SQLSafetyValidator
    → TenantIsolationInjector → ReadOnlyExecutor → ResultFormatter
"""

from app.ai.data_intelligence.readonly_executor import (
    QueryResult,
    ReadOnlyExecutor,
)
from app.ai.data_intelligence.result_formatter import (
    FormattedResult,
    ResultFormatter,
)
from app.ai.data_intelligence.schema_provider import (
    ColumnSchema,
    SchemaProvider,
    TableSchema,
)
from app.ai.data_intelligence.sql_safety import (
    SQLSafetyValidator,
    SQLValidationResult,
    extract_table_names,
)
from app.ai.data_intelligence.tenant_isolation import (
    TenantIsolationError,
    TenantIsolationInjector,
)
from app.ai.data_intelligence.text_to_sql import (
    ConversationRound,
    GeneratedSQL,
    TextToSQLGenerator,
)

__all__ = [
    # SchemaProvider
    "ColumnSchema",
    "TableSchema",
    "SchemaProvider",
    # SQLSafetyValidator
    "SQLSafetyValidator",
    "SQLValidationResult",
    "extract_table_names",
    # TenantIsolationInjector
    "TenantIsolationInjector",
    "TenantIsolationError",
    # ReadOnlyExecutor
    "QueryResult",
    "ReadOnlyExecutor",
    # TextToSQLGenerator
    "ConversationRound",
    "GeneratedSQL",
    "TextToSQLGenerator",
    # ResultFormatter
    "FormattedResult",
    "ResultFormatter",
]
