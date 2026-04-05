"""
SQL Safety Validator (SQLSafetyValidator)
SQL 安全校验器（SQLSafetyValidator）

Six-layer safety check; all must pass before execution is allowed.
Even if LLM is attacked by Prompt Injection, dangerous operations cannot be executed.
六重安全检查，全部通过才允许执行。
即使 LLM 被 Prompt Injection 攻击，也无法执行危险操作。

Extends SqlValidator from security.py / 继承并增强 security.py 中的 SqlValidator：
- SqlValidator checks: SELECT-only, dangerous keywords, system tables / SqlValidator 检查
- New checks: table whitelist, function blacklist, comment prohibition / 新增检查
"""

from __future__ import annotations  # noqa: I001

from dataclasses import dataclass, field

from app.ai.data_intelligence.sql_analysis import (
    contains_sql_comments,
    extract_called_functions,
    find_keyword_sequences,
    starts_with_select_or_cte,
)
from app.ai.data_intelligence.sql_analysis import (
    extract_table_names as extract_table_names_from_sql,
)
from app.ai.tools.security import SqlValidator
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.data_intelligence")


# ============================================
# Validation Result / 校验结果
# ============================================


@dataclass
class SQLValidationResult:
    """SQL validation result / SQL 校验结果"""

    passed: bool
    violations: list[str] = field(default_factory=list)

    @property
    def error_message(self) -> str:
        """Merge all violation messages / 合并所有违规信息"""
        if self.passed:
            return ""
        return "; ".join(self.violations)


# ============================================
# Function Blacklist / 函数黑名单
# ============================================

# PostgreSQL dangerous function list / PostgreSQL 危险函数列表
_BLOCKED_FUNCTIONS: list[str] = [
    # File system access / 文件系统访问
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    # Large object operations / 大对象操作
    "lo_import",
    "lo_export",
    "lo_get",
    "lo_put",
    # Remote connection / 远程连接
    "dblink",
    "dblink_connect",
    "dblink_exec",
    # DoS attack / DoS 攻击
    "pg_sleep",
    # Process management / 进程管理
    "pg_terminate_backend",
    "pg_cancel_backend",
    # Configuration modification / 配置修改
    "set_config",
    "current_setting",
    # Execute arbitrary code / 执行任意代码
    "pg_execute_server_program",
]

_DANGEROUS_KEYWORD_SEQUENCES: list[tuple[str, ...]] = [
    ("INSERT",),
    ("UPDATE",),
    ("DELETE",),
    ("DROP",),
    ("ALTER",),
    ("TRUNCATE",),
    ("CREATE",),
    ("GRANT",),
    ("REVOKE",),
    ("EXEC",),
    ("INTO",),
    ("COPY",),
    ("LOAD", "DATA"),
    ("DO",),
]
_WRITE_OPERATION_SEQUENCES: list[tuple[str, ...]] = [
    ("INSERT", "INTO"),
    ("UPDATE",),
    ("DELETE", "FROM"),
    ("DROP", "TABLE"),
    ("ALTER", "TABLE"),
    ("TRUNCATE",),
]
_SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


def extract_table_names(sql: str) -> set[str]:
    """
    从 SQL 中提取所有引用的表名 / Extract all referenced table names from SQL.

    Uses shared sqlparse-based analysis helpers.
    使用共享的 sqlparse 语义分析辅助工具。
    """
    return extract_table_names_from_sql(sql)


# ============================================
# SQLSafetyValidator / SQL 安全校验器
# ============================================


class SQLSafetyValidator:
    """
    SQL Safety Validator — Six-Layer Defense
    SQL 安全校验器 —— 六重防线

    Check order / 检查顺序：
    1. SELECT-only (allows WITH...SELECT / CTE) / SELECT-only
    2. Dangerous keywords (INSERT/UPDATE/DELETE/DROP etc.) / 危险关键字
    3. Subquery modification detection / 子查询修改检测
    4. Table whitelist validation / 表白名单验证
    5. Function blacklist / 函数黑名单
    6. Comment prohibition / 注释禁止
    """

    @staticmethod
    def validate(
        sql: str,
        allowed_tables: set[str] | None = None,
    ) -> SQLValidationResult:
        """
        Six-layer check; all must pass before execution is allowed.
        六重检查，全部通过才允许执行。

        Args:
            sql: SQL statement to check / 待检查的 SQL 语句
            allowed_tables: Set of allowed table names (lowercase) / 允许查询的表名集合

        Returns:
            SQLValidationResult(passed=True/False, violations=[])
        """
        violations: list[str] = []
        stripped = sql.strip()

        if not stripped:
            violations.append(_("data_intelligence.sql.empty"))

        # ---- Check 1: Must be SELECT or WITH (CTE) / 检查 1: 必须是 SELECT 或 WITH ----
        if not starts_with_select_or_cte(stripped):
            violations.append(_("data_intelligence.sql.select_only"))

        # ---- Check 2: Prohibit dangerous keywords / 检查 2: 禁止危险关键字 ----
        blocked_keywords = find_keyword_sequences(
            stripped, _DANGEROUS_KEYWORD_SEQUENCES
        )
        if blocked_keywords:
            violations.append(
                _(
                    "data_intelligence.sql.dangerous_keyword",
                    keyword=blocked_keywords[0],
                )
            )

        # ---- Check 3: Subquery modification detection / 检查 3: 子查询修改检测 ----
        # Even if main query is SELECT, write ops in subqueries are not allowed / 子查询中也不允许写操作
        if find_keyword_sequences(stripped, _WRITE_OPERATION_SEQUENCES):
            violations.append(_("data_intelligence.sql.write_in_subquery"))

        # ---- Check 4: Table whitelist validation / 检查 4: 表白名单验证 ----
        if allowed_tables is not None:
            tables_in_sql = extract_table_names(stripped)
            for table in tables_in_sql:
                if table not in allowed_tables:
                    violations.append(
                        _("data_intelligence.sql.table_not_allowed", table=table)
                    )

        # ---- Check 5: Function blacklist / 检查 5: 函数黑名单 ----
        blocked_calls = extract_called_functions(stripped)
        blocked_function = next(
            (func for func in _BLOCKED_FUNCTIONS if func.lower() in blocked_calls),
            None,
        )
        if blocked_function:
            violations.append(
                _("data_intelligence.sql.blocked_function", func=blocked_function)
            )

        # ---- Check 6: Comment prohibition (prevent bypassing via comments) / 检查 6: 注释禁止 ----
        if contains_sql_comments(stripped):
            violations.append(_("data_intelligence.sql.no_line_comment"))

        # ---- Extra check: System tables / 额外检查：系统表 ----
        table_names = extract_table_names_from_sql(stripped)
        if any(table in _SYSTEM_SCHEMAS for table in table_names) or any(
            f"{schema}." in stripped.lower() for schema in _SYSTEM_SCHEMAS
        ):
            violations.append(_("data_intelligence.sql.system_table_blocked"))

        passed = len(violations) == 0

        if not passed:
            logger.warning(
                "SQL safety validation failed: violations={} sql={}",
                violations,
                stripped[:200],
            )

        return SQLValidationResult(passed=passed, violations=violations)

    @staticmethod
    def inject_limit(sql: str, max_rows: int = 200) -> str:
        """
        自动注入 LIMIT（如果缺失）/ Auto-inject LIMIT (if missing).

        Reuses SqlValidator.inject_limit logic with Text-to-SQL default limit (200 rows).
        复用 SqlValidator.inject_limit 逻辑，使用 Text-to-SQL 默认限制（200 行）。
        """
        return SqlValidator.inject_limit(sql, max_rows)


__all__ = [
    "SQLValidationResult",
    "SQLSafetyValidator",
    "extract_table_names",
]
