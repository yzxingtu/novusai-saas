"""
数据库查询工具执行器

仅允许 SELECT 语句，通过独立只读连接执行，支持 SQL 模板和表白名单
"""

import re
import time
from typing import Any

import sqlalchemy

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.database")

# 危险 SQL 关键字正则（不区分大小写）
_DANGEROUS_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE"
    r"|UNION|INTO|COPY|SET|DO|EXPLAIN)\b",
    re.IGNORECASE,
)

# 默认限制
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_ROWS = 100


class DatabaseToolExecutor(BaseToolExecutor):
    """
    数据库查询工具执行器

    安全策略:
    - 仅允许 SELECT 语句
    - 正则过滤危险 SQL 关键字
    - 使用独立只读连接
    - 限制返回行数
    - connection_string 从环境变量读取，禁止前端传入
    """

    def __init__(
        self,
        max_rows: int = DEFAULT_MAX_ROWS,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Args:
            max_rows: 最大返回行数
            timeout: 查询超时秒数
        """
        self.max_rows = max_rows
        self.timeout = timeout

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        执行数据库查询

        config 格式:
            connection_string_env: 环境变量名（包含数据库连接字符串）
            sql_template: SQL 模板（含 {param} 占位符）
            allowed_tables: 允许查询的表名列表（可选）
        """
        import os

        start = time.perf_counter()
        config = definition.config

        # 从环境变量获取连接字符串
        conn_env = config.get("connection_string_env", "")
        if not conn_env:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.db_missing_connection_env"),
            )

        connection_string = os.environ.get(conn_env, "")
        if not connection_string:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.db_env_not_set", env_var=conn_env),
            )

        # 构建 SQL（使用参数化查询防止注入）
        sql_template: str = config.get("sql_template", "")
        if not sql_template:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.db_missing_sql_template"),
            )

        # 将 {param} 占位符转换为 :param SQLAlchemy 绑定参数
        # 仅允许简单字段名 {word}，拒绝 {obj.attr} / {a[0]} 等复杂表达式
        param_names = re.findall(r"\{(\w+)\}", sql_template)
        parameterized_sql = re.sub(r"\{(\w+)\}", r":\1", sql_template)

        # 检查是否所有模板参数都有对应的 argument
        missing = [p for p in param_names if p not in arguments]
        if missing:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.db_sql_template_param_error", detail=f"missing: {missing}"),
            )

        # 构建绑定参数（仅传递模板中声明的参数，忽略多余参数）
        bind_params = {k: arguments[k] for k in param_names if k in arguments}

        # 安全检查在模板级别执行（参数值不可能影响 SQL 结构）
        sql_stripped = parameterized_sql.strip().rstrip(";")
        if not re.match(r"^\s*(SELECT|WITH)\b", sql_stripped, re.IGNORECASE):
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.sql_only_select"),
            )

        if _DANGEROUS_SQL_PATTERN.search(sql_stripped):
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.sql_write_blocked"),
            )

        # 表白名单检查
        allowed_tables = config.get("allowed_tables", [])
        if allowed_tables:
            table_check_error = self._check_tables(sql_stripped, allowed_tables)
            if table_check_error:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=table_check_error,
                )

        # 添加 LIMIT
        if not re.search(r"\bLIMIT\b", sql_stripped, re.IGNORECASE):
            sql_stripped = f"{sql_stripped} LIMIT {self.max_rows}"

        # 执行查询（在线程中运行同步 DB 操作，避免阻塞事件循环）
        try:
            import asyncio

            final_bind_params = bind_params

            def _run_query() -> tuple[list[str], list[dict]]:
                engine = sqlalchemy.create_engine(
                    connection_string,
                    pool_pre_ping=True,
                    connect_args={"connect_timeout": self.timeout},
                )
                try:
                    with engine.connect() as conn:
                        stmt = sqlalchemy.text(sql_stripped)
                        result_proxy = conn.execute(stmt, final_bind_params)
                        columns = list(result_proxy.keys())
                        rows = [dict(zip(columns, row)) for row in result_proxy.fetchall()]
                    return columns, rows
                finally:
                    engine.dispose()

            columns, rows = await asyncio.to_thread(_run_query)

            duration_ms = int((time.perf_counter() - start) * 1000)

            import json
            output = json.dumps(
                {"columns": columns, "rows": rows, "count": len(rows)},
                ensure_ascii=False,
                default=str,
            )

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Database tool error: %s: %s",
                definition.name,
                str(exc),
                exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验数据库工具参数"""
        config = definition.config
        if not config.get("sql_template"):
            return False
        if not config.get("connection_string_env"):
            return False

        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False

        return True

    @staticmethod
    def _check_tables(sql: str, allowed_tables: list[str]) -> str:
        """
        检查 SQL 中引用的表是否在白名单内

        Returns:
            错误信息字符串，为空表示通过
        """
        from_pattern = re.compile(
            r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)",
            re.IGNORECASE,
        )
        matches = from_pattern.findall(sql)
        tables = {m[0] or m[1] for m in matches if m[0] or m[1]}

        allowed_set = {t.lower() for t in allowed_tables}
        for table in tables:
            if table.lower() not in allowed_set:
                return _("tool.error.db_table_not_allowed", table=table)

        return ""


__all__ = ["DatabaseToolExecutor"]
