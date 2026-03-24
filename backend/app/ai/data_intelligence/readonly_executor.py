"""
Read-Only Database Executor (ReadOnlyExecutor)
只读数据库执行器（ReadOnlyExecutor）

Security measures / 安全措施：
1. Uses independent read-only DB connection (not main pool) / 使用独立的只读数据库连接
2. SET default_transaction_read_only = ON (transaction-level read-only) / 事务级只读
3. SET statement_timeout = '10s' (prevent slow query DoS) / 防止慢查询 DoS
4. Max 200 rows returned (LIMIT forced injection) / 最大返回 200 行
5. Result masking (email/phone/ip_address column values replaced with ***) / 结果脱敏
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from app.ai.constants import TEXT_TO_SQL_MAX_ROWS, TEXT_TO_SQL_TIMEOUT
from app.ai.data_intelligence.sql_safety import SQLSafetyValidator
from app.core.database import get_readonly_session_factory
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.data_intelligence")


# ============================================
# Data Structures / 数据结构
# ============================================

@dataclass
class QueryResult:
    """Query result / 查询结果"""

    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False    # Whether truncated by LIMIT / 是否被 LIMIT 截断
    duration_ms: int = 0       # Execution duration (ms) / 执行耗时（毫秒）
    masked_columns: list[str] = field(default_factory=list)  # Masked columns / 被脱敏的列

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "duration_ms": self.duration_ms,
            "masked_columns": self.masked_columns,
        }


# ============================================
# Result Masking / 结果脱敏
# ============================================

def _mask_email(value: Any) -> str:
    """Email masking: abc***@example.com / 邮箱脱敏"""
    val = str(value)
    if "@" in val:
        local, domain = val.split("@", 1)
        return local[:3] + "***@" + domain
    return "***"


def _mask_phone(value: Any) -> str:
    """Phone masking: 138****1234 / 手机号脱敏"""
    val = str(value)
    if len(val) >= 7:
        return val[:3] + "****" + val[-4:]
    return "***"


def _mask_ip(value: Any) -> str:
    """IP masking: ***.***.***.123 / IP 脱敏"""
    val = str(value)
    if "." in val:
        parts = val.split(".")
        return "***.***.***." + parts[-1]
    return "***"


# Column names requiring masking -> masking function / 需要脱敏的列名 → 脱敏函数
_MASK_COLUMNS: dict[str, Any] = {
    "email": _mask_email,
    "phone": _mask_phone,
    "mobile": _mask_phone,
    "phone_number": _mask_phone,
    "ip_address": _mask_ip,
    "ip": _mask_ip,
    "last_login_ip": _mask_ip,
    "login_ip": _mask_ip,
}


def _mask_row(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Mask a single row, returns (masked_row, masked_column_names) / 对单行数据进行脱敏"""
    masked: dict[str, Any] = {}
    masked_cols: list[str] = []

    for col, value in row.items():
        col_lower = col.lower()
        mask_func = _MASK_COLUMNS.get(col_lower)
        if mask_func and value is not None:
            masked[col] = mask_func(value)
            masked_cols.append(col)
        else:
            masked[col] = value

    return masked, masked_cols


# ============================================
# ReadOnlyExecutor / 只读执行器
# ============================================

class ReadOnlyExecutor:
    """
    Read-Only Database Executor / 只读数据库执行器

    Executes SQL queries using independent read-only connections,
    ensuring no impact on the main business database connection pool.
    使用独立只读连接执行 SQL 查询，
    确保不会影响主业务数据库连接池。
    """

    def __init__(
        self,
        timeout_seconds: int = TEXT_TO_SQL_TIMEOUT,
        max_rows: int = TEXT_TO_SQL_MAX_ROWS,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_rows = max_rows

    async def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        """
        Execute SQL on read-only connection.
        在只读连接上执行 SQL。

        Prefers independent read-only connection; falls back to main connection (still enforces read-only transaction) if not configured.
        优先使用独立只读连接，未配置时回退到主连接（仍强制只读事务）。

        Args:
            sql: SQL query (with tenant_id injected) / SQL 查询语句（已注入 tenant_id）
            params: SQL parameters (for parameterized queries) / SQL 参数

        Returns:
            QueryResult execution result / 执行结果

        Raises:
            Exception: Execution failure / 执行失败
        """
        session_factory = get_readonly_session_factory()
        if session_factory is None:
            from app.core.database import async_session_factory
            session_factory = async_session_factory
            logger.warning(
                "AI_READONLY_DB_URL not configured, falling back to main DB "
                "(read-only transaction enforced)"
            )

        # Force inject LIMIT / 强制注入 LIMIT
        sql = SQLSafetyValidator.inject_limit(sql, self.max_rows)

        start_time = time.monotonic()

        async with session_factory() as session:
            try:
                # Set transaction-level read-only and timeout / 设置事务级只读和超时
                await session.execute(
                    text("SET LOCAL default_transaction_read_only = ON")
                )
                await session.execute(
                    text(f"SET LOCAL statement_timeout = '{self.timeout_seconds * 1000}'")
                )

                # Execute query / 执行查询
                result = await session.execute(text(sql), params or {})
                raw_rows = result.fetchall()
                columns = list(result.keys()) if result.keys() else []

                duration_ms = int((time.monotonic() - start_time) * 1000)

                # Convert to dict list and mask / 转换为字典列表并脱敏
                rows: list[dict[str, Any]] = []
                all_masked_cols: set[str] = set()

                for raw_row in raw_rows:
                    row_dict = dict(zip(columns, raw_row, strict=False))
                    masked_row, masked_cols = _mask_row(row_dict)
                    rows.append(masked_row)
                    all_masked_cols.update(masked_cols)

                # Check if truncated / 判断是否被截断
                truncated = len(rows) >= self.max_rows

                logger.info(
                    "ReadOnlyExecutor: {} rows in {}ms (truncated={})",
                    len(rows), duration_ms, truncated,
                )

                return QueryResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=truncated,
                    duration_ms=duration_ms,
                    masked_columns=sorted(all_masked_cols),
                )

            except Exception as exc:
                duration_ms = int((time.monotonic() - start_time) * 1000)
                logger.error(
                    "ReadOnlyExecutor failed in {}ms: {}",
                    duration_ms, str(exc),
                )
                raise
            finally:
                await session.rollback()

    async def check_connection(self) -> bool:
        """Check if read-only connection is available / 检查只读连接是否可用"""
        session_factory = get_readonly_session_factory()
        if session_factory is None:
            return False

        try:
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as exc:
            logger.error("ReadOnlyExecutor connection check failed: {}", str(exc))
            return False


__all__ = [
    "QueryResult",
    "ReadOnlyExecutor",
]
