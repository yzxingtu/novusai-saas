"""
AI Data Intelligence Module (Text-to-SQL + Business Operations)
AI 数据智能模块（Text-to-SQL + 业务操作）

Core components / 核心组件：
- SchemaProvider: Data dictionary service, manages table whitelist and column filtering / 数据字典服务
- SQLSafetyValidator: Six-layer SQL safety validation / SQL 六重安全校验
- TenantIsolationInjector: Automatic tenant_id isolation injection / 自动注入 tenant_id 隔离条件
- ReadOnlyExecutor: Read-only database executor / 只读数据库执行器
- TextToSQLGenerator: LLM natural language to SQL generator / LLM 自然语言转 SQL 生成器
- ResultFormatter: Query result smart formatting / 查询结果智能格式化

Security chain / 安全链路：
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
    # SchemaProvider / 上文为英文说明 / English above
    "ColumnSchema",
    "TableSchema",
    "SchemaProvider",
    # SQLSafetyValidator / 上文为英文说明 / English above
    "SQLSafetyValidator",
    "SQLValidationResult",
    "extract_table_names",
    # TenantIsolationInjector / 上文为英文说明 / English above
    "TenantIsolationInjector",
    "TenantIsolationError",
    # ReadOnlyExecutor / 上文为英文说明 / English above
    "QueryResult",
    "ReadOnlyExecutor",
    # TextToSQLGenerator / 上文为英文说明 / English above
    "ConversationRound",
    "GeneratedSQL",
    "TextToSQLGenerator",
    # ResultFormatter / 上文为英文说明 / English above
    "FormattedResult",
    "ResultFormatter",
]
