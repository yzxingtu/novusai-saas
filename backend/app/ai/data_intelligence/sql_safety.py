"""
SQL 安全校验器（SQLSafetyValidator）

六重安全检查，全部通过才允许执行。
即使 LLM 被 Prompt Injection 攻击，也无法执行危险操作。

继承并增强 security.py 中的 SqlValidator：
- SqlValidator 检查：SELECT-only、危险关键字、系统表
- 新增检查：表白名单、函数黑名单、注释禁止
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
# 校验结果
# ============================================

@dataclass
class SQLValidationResult:
    """SQL 校验结果"""

    passed: bool
    violations: list[str] = field(default_factory=list)

    @property
    def error_message(self) -> str:
        """合并所有违规信息"""
        if self.passed:
            return ""
        return "; ".join(self.violations)


# ============================================
# 函数黑名单
# ============================================

# PostgreSQL 危险函数列表
_BLOCKED_FUNCTIONS: list[str] = [
    # 文件系统访问
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    # 大对象操作
    "lo_import",
    "lo_export",
    "lo_get",
    "lo_put",
    # 远程连接
    "dblink",
    "dblink_connect",
    "dblink_exec",
    # DoS 攻击
    "pg_sleep",
    # 进程管理
    "pg_terminate_backend",
    "pg_cancel_backend",
    # 配置修改
    "set_config",
    "current_setting",
    # 执行任意代码
    "pg_execute_server_program",
]

# 编译成正则模式（匹配函数调用形式）
_BLOCKED_FUNC_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in _BLOCKED_FUNCTIONS) + r")\s*\(",
    re.IGNORECASE,
)

# ============================================
# 表名提取
# ============================================

# FROM / JOIN 后的表名提取正则
# 匹配: FROM table_name [AS alias], JOIN table_name [AS alias]
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
    从 SQL 中提取所有引用的表名

    使用 sqlparse 解析 + 正则辅助，处理 CTE、子查询等情况
    """
    tables: set[str] = set()

    # 先用 sqlparse 标准化 SQL
    parsed = sqlparse.parse(sql)
    if not parsed:
        return tables

    normalized = str(parsed[0]).strip()

    # 提取 CTE 定义的名称（不是真实表，需排除）
    cte_names: set[str] = set()
    cte_pattern = re.compile(
        r"\bWITH\s+(?:RECURSIVE\s+)?(\w+)\s+AS\s*\(",
        re.IGNORECASE,
    )
    for match in cte_pattern.finditer(normalized):
        cte_names.add(match.group(1).lower())

    # 提取 FROM / JOIN 后的表名
    for match in _TABLE_REF_PATTERN.finditer(normalized):
        table_name = match.group(1).lower()
        # 排除 CTE 名称和 SQL 关键字
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
    SQL 安全校验器 —— 六重防线

    检查顺序：
    1. SELECT-only（允许 WITH...SELECT / CTE）
    2. 危险关键字（INSERT/UPDATE/DELETE/DROP 等）
    3. 子查询修改检测
    4. 表白名单验证
    5. 函数黑名单
    6. 注释禁止
    """

    @staticmethod
    def validate(
        sql: str,
        allowed_tables: set[str] | None = None,
    ) -> SQLValidationResult:
        """
        六重检查，全部通过才允许执行

        Args:
            sql: 待检查的 SQL 语句
            allowed_tables: 允许查询的表名集合（小写）

        Returns:
            SQLValidationResult(passed=True/False, violations=[])
        """
        violations: list[str] = []
        stripped = sql.strip()

        if not stripped:
            violations.append(_("data_intelligence.sql.empty"))
            return SQLValidationResult(passed=False, violations=violations)

        # ---- 检查 1: 必须是 SELECT 或 WITH（CTE）----
        if not re.match(r"^\s*(SELECT|WITH)\b", stripped, re.IGNORECASE):
            violations.append(_("data_intelligence.sql.select_only"))

        # ---- 检查 2: 禁止危险关键字 ----
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

        # ---- 检查 3: 子查询修改检测 ----
        # 即使主查询是 SELECT，子查询中也不允许写操作
        write_ops = re.compile(
            r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|"
            r"DROP\s+TABLE|ALTER\s+TABLE|TRUNCATE)\b",
            re.IGNORECASE,
        )
        if write_ops.search(stripped):
            violations.append(_("data_intelligence.sql.write_in_subquery"))

        # ---- 检查 4: 表白名单 ----
        if allowed_tables is not None:
            tables_in_sql = extract_table_names(stripped)
            for table in tables_in_sql:
                if table not in allowed_tables:
                    violations.append(
                        _("data_intelligence.sql.table_not_allowed",
                          table=table)
                    )

        # ---- 检查 5: 函数黑名单 ----
        func_match = _BLOCKED_FUNC_PATTERN.search(stripped)
        if func_match:
            violations.append(
                _("data_intelligence.sql.blocked_function",
                  func=func_match.group(1))
            )

        # ---- 检查 6: 注释禁止（防止注释绕过安全检查）----
        if "--" in stripped:
            violations.append(_("data_intelligence.sql.no_line_comment"))
        if "/*" in stripped:
            violations.append(_("data_intelligence.sql.no_block_comment"))

        # ---- 额外检查：系统表 ----
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
        自动注入 LIMIT（如果缺失）

        复用 SqlValidator.inject_limit 逻辑，
        但使用 Text-to-SQL 默认限制（200 行）
        """
        return SqlValidator.inject_limit(sql, max_rows)


__all__ = [
    "SQLValidationResult",
    "SQLSafetyValidator",
    "extract_table_names",
]
