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

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlparse

from app.ai.tools.security import SqlValidator
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.data_intelligence")


# ============================================
# Validation Result / 校验结果
# ============================================

@dataclass
class SQLValidationResult:
    """SQL validation result / SQL 校验结果"""  # 校验结果

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

# Compile into regex pattern (match function call form) / 编译成正则模式（匹配函数调用形式）
_BLOCKED_FUNC_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in _BLOCKED_FUNCTIONS) + r")\s*\(",
    re.IGNORECASE,
)

# ============================================
# Table Name Extraction / 表名提取
# ============================================

# Regex for extracting table names after FROM / JOIN / FROM / JOIN 后的表名提取正则
# Matches: FROM table_name [AS alias], JOIN table_name [AS alias] / 匹配格式
_TABLE_REF_PATTERN = re.compile(
    r"""
    (?:FROM|JOIN)\s+           # FROM 或 JOIN 关键字
    (?:ONLY\s+)?               # 可选 ONLY
    (\w+)                      # 表名（捕获组）
    (?:                        # 可选别名（避免吞掉 JOIN/WHERE 等关键字）
      \s+
      (?!
        JOIN\b|ON\b|WHERE\b|GROUP\b|ORDER\b|LIMIT\b|OFFSET\b|HAVING\b|
        UNION\b|EXCEPT\b|INTERSECT\b|LEFT\b|RIGHT\b|FULL\b|INNER\b|CROSS\b
      )
      (?:AS\s+)?\w+
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_table_names(sql: str) -> set[str]:
    """
    从 SQL 中提取所有引用的表名 / Extract all referenced table names from SQL.

    Uses sqlparse parsing + regex to handle CTEs, subqueries, etc.
    使用 sqlparse 解析 + 正则辅助，处理 CTE、子查询等情况。
    """
    tables: set[str] = set()

    # Normalize SQL with sqlparse / 先用 sqlparse 标准化 SQL
    parsed = sqlparse.parse(sql)
    if not parsed:
        return tables

    normalized = str(parsed[0]).strip()

    # Extract CTE-defined names (not real tables, need to exclude) / 提取 CTE 定义的名称
    cte_names: set[str] = set()
    cte_pattern = re.compile(
        r"\bWITH\s+(?:RECURSIVE\s+)?(\w+)\s+AS\s*\(",
        re.IGNORECASE,
    )
    for match in cte_pattern.finditer(normalized):
        cte_names.add(match.group(1).lower())

    # Extract table names after FROM / JOIN / 提取 FROM / JOIN 后的表名
    for match in _TABLE_REF_PATTERN.finditer(normalized):
        table_name = match.group(1).lower()
        # Exclude CTE names and SQL keywords / 排除 CTE 名称和 SQL 关键字
        if table_name not in cte_names and table_name not in {
            "select", "where", "and", "or", "not", "in",
            "lateral", "unnest", "generate_series",
        }:
            tables.add(table_name)

    return tables


# ============================================
# SQLSafetyValidator
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
        if not re.match(r"^\s*(SELECT|WITH)\b", stripped, re.IGNORECASE):
            violations.append(_("data_intelligence.sql.select_only"))

        # ---- Check 2: Prohibit dangerous keywords / 检查 2: 禁止危险关键字 ----
        dangerous_pattern = re.compile(
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|"
            r"GRANT|REVOKE|EXEC|COPY|INTO|"
            r"LOAD\s+DATA|DO)\b",
            re.IGNORECASE,
        )
        match = dangerous_pattern.search(stripped)
        if match:
            violations.append(
                _("data_intelligence.sql.dangerous_keyword",
                  keyword=match.group())
            )

        # ---- Check 3: Subquery modification detection / 检查 3: 子查询修改检测 ----
        # Even if main query is SELECT, write ops in subqueries are not allowed / 子查询中也不允许写操作
        write_ops = re.compile(
            r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|"
            r"DROP\s+TABLE|ALTER\s+TABLE|TRUNCATE)\b",
            re.IGNORECASE,
        )
        if write_ops.search(stripped):
            violations.append(_("data_intelligence.sql.write_in_subquery"))

        # ---- Check 4: Table whitelist validation / 检查 4: 表白名单验证 ----
        if allowed_tables is not None:
            tables_in_sql = extract_table_names(stripped)
            for table in tables_in_sql:
                if table not in allowed_tables:
                    violations.append(
                        _("data_intelligence.sql.table_not_allowed",
                          table=table)
                    )

        # ---- Check 5: Function blacklist / 检查 5: 函数黑名单 ----
        func_match = _BLOCKED_FUNC_PATTERN.search(stripped)
        if func_match:
            violations.append(
                _("data_intelligence.sql.blocked_function",
                  func=func_match.group(1))
            )

        # ---- Check 6: Comment prohibition (prevent bypassing via comments) / 检查 6: 注释禁止 ----
        if "--" in stripped:
            violations.append(_("data_intelligence.sql.no_line_comment"))
        if "/*" in stripped:
            violations.append(_("data_intelligence.sql.no_block_comment"))

        # ---- Extra check: System tables / 额外检查：系统表 ----
        system_pattern = re.compile(
            r"\b(pg_catalog|information_schema|pg_toast)\b",
            re.IGNORECASE,
        )
        if system_pattern.search(stripped):
            violations.append(_("data_intelligence.sql.system_table_blocked"))

        passed = len(violations) == 0

        if not passed:
            logger.warning(
                "SQL safety validation failed: violations=%s sql=%s",
                violations, stripped[:200],
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
