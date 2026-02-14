"""
查询结果格式化器（ResultFormatter）

将 ReadOnlyExecutor 返回的原始查询结果智能转换为前端可渲染的格式。

自动检测类型：
- number: 单值结果（如 COUNT、SUM、AVG）
- chart: 适合图表展示的数据（时间序列 → line，分类统计 → bar/pie）
- table: 多行多列数据
- text: 无数据或纯文本结果

生成 ECharts 配置供前端直接渲染。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.ai.data_intelligence.readonly_executor import QueryResult
from app.ai.data_intelligence.text_to_sql import GeneratedSQL
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.data_intelligence")


# ============================================
# 显示类型枚举
# ============================================

DISPLAY_TYPE_NUMBER = "number"
DISPLAY_TYPE_LINE_CHART = "line_chart"
DISPLAY_TYPE_BAR_CHART = "bar_chart"
DISPLAY_TYPE_PIE_CHART = "pie_chart"
DISPLAY_TYPE_TABLE = "table"
DISPLAY_TYPE_TEXT = "text"


# ============================================
# 数据结构
# ============================================

@dataclass
class FormattedResult:
    """格式化后的查询结果"""

    display_type: str = DISPLAY_TYPE_TABLE
    data: dict[str, Any] = field(default_factory=dict)
    chart_config: dict[str, Any] | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "display_type": self.display_type,
            "data": self.data,
            "summary": self.summary,
        }
        if self.chart_config is not None:
            result["chart_config"] = self.chart_config
        return result


# ============================================
# 时间列检测
# ============================================

_TIME_COLUMN_PATTERNS = re.compile(
    r"(date|time|day|month|year|week|created|updated|period|_at$)",
    re.IGNORECASE,
)

_NUMERIC_TYPES = {"int", "float", "decimal", "numeric", "bigint", "real"}


def _is_time_column(col_name: str) -> bool:
    """判断列名是否为时间类型"""
    return bool(_TIME_COLUMN_PATTERNS.search(col_name))


def _is_time_value(value: Any) -> bool:
    """判断值是否为时间类型"""
    if isinstance(value, (date, datetime)):
        return True
    if isinstance(value, str):
        # 简单检测 ISO 日期格式
        return bool(re.match(r"^\d{4}[-/]\d{2}", value))
    return False


def _is_numeric(value: Any) -> bool:
    """判断值是否为数值"""
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    return False


# ============================================
# ResultFormatter
# ============================================

class ResultFormatter:
    """
    查询结果格式化器

    根据数据特征自动选择最佳展示方式，
    生成 ECharts 配置和中文摘要。
    """

    @staticmethod
    def format(
        query_result: QueryResult,
        generated_sql: GeneratedSQL | None = None,
    ) -> FormattedResult:
        """
        格式化查询结果

        Args:
            query_result: 只读执行器返回的原始结果
            generated_sql: LLM 生成的 SQL 信息（含 explanation 和 visualization 建议）

        Returns:
            FormattedResult 格式化结果
        """
        columns = query_result.columns
        rows = query_result.rows
        row_count = query_result.row_count

        # 空结果
        if not rows:
            return FormattedResult(
                display_type=DISPLAY_TYPE_TEXT,
                data={"columns": columns, "rows": [], "row_count": 0},
                summary=_("data_intelligence.formatter.no_data"),
            )

        # 检测显示类型
        display_type = ResultFormatter._detect_display_type(
            columns,
            rows,
            generated_sql.visualization_suggestion if generated_sql else None,
        )

        # 构建基础数据
        data: dict[str, Any] = {
            "columns": columns,
            "rows": rows,
            "row_count": row_count,
            "truncated": query_result.truncated,
        }

        # 单值 number
        if display_type == DISPLAY_TYPE_NUMBER:
            value = rows[0].get(columns[0]) if columns else None
            data["value"] = value
            data["label"] = columns[0] if columns else ""
            summary = ResultFormatter._generate_number_summary(
                columns[0] if columns else "",
                value,
                generated_sql,
            )
            return FormattedResult(
                display_type=display_type,
                data=data,
                summary=summary,
            )

        # 图表类型
        chart_config = None
        if display_type in (
            DISPLAY_TYPE_LINE_CHART,
            DISPLAY_TYPE_BAR_CHART,
            DISPLAY_TYPE_PIE_CHART,
        ):
            chart_config = ResultFormatter._build_chart_config(
                display_type, columns, rows,
            )

        # 生成摘要
        summary = ResultFormatter._generate_summary(
            query_result, generated_sql,
        )

        return FormattedResult(
            display_type=display_type,
            data=data,
            chart_config=chart_config,
            summary=summary,
        )

    @staticmethod
    def _detect_display_type(
        columns: list[str],
        rows: list[dict[str, Any]],
        llm_suggestion: str | None = None,
    ) -> str:
        """
        自动检测最佳显示类型

        优先级：
        1. 单行单列数值 → number
        2. LLM 建议（如果合理）
        3. 时间列 + 数值列 → line_chart
        4. 2 列（分类 + 数值）→ bar_chart 或 pie_chart
        5. 默认 → table
        """
        col_count = len(columns)
        row_count = len(rows)

        # 单行单列 → number
        if row_count == 1 and col_count == 1:
            value = rows[0].get(columns[0])
            if _is_numeric(value):
                return DISPLAY_TYPE_NUMBER

        # LLM 建议映射
        suggestion_map = {
            "number": DISPLAY_TYPE_NUMBER,
            "line": DISPLAY_TYPE_LINE_CHART,
            "bar": DISPLAY_TYPE_BAR_CHART,
            "pie": DISPLAY_TYPE_PIE_CHART,
            "table": DISPLAY_TYPE_TABLE,
        }

        if llm_suggestion and llm_suggestion in suggestion_map:
            suggested_type = suggestion_map[llm_suggestion]
            # 验证 LLM 建议是否合理
            if suggested_type == DISPLAY_TYPE_NUMBER and (
                row_count != 1 or col_count != 1
            ):
                pass  # 不合理，跳过
            elif suggested_type in (
                DISPLAY_TYPE_LINE_CHART,
                DISPLAY_TYPE_BAR_CHART,
                DISPLAY_TYPE_PIE_CHART,
            ) and col_count >= 2 and row_count >= 2:
                return suggested_type

        # 自动检测：时间列 + 数值列 → line
        if col_count >= 2 and row_count >= 2:
            first_col = columns[0]
            first_value = rows[0].get(first_col)
            if _is_time_column(first_col) or _is_time_value(first_value):
                # 检查是否有数值列
                has_numeric = any(
                    _is_numeric(rows[0].get(c))
                    for c in columns[1:]
                )
                if has_numeric:
                    return DISPLAY_TYPE_LINE_CHART

        # 2 列（分类 + 数值）且行数适中 → bar/pie
        if col_count == 2 and 2 <= row_count <= 20:
            second_col = columns[1]
            if _is_numeric(rows[0].get(second_col)):
                if row_count <= 8:
                    return DISPLAY_TYPE_PIE_CHART
                return DISPLAY_TYPE_BAR_CHART

        return DISPLAY_TYPE_TABLE

    @staticmethod
    def _build_chart_config(
        display_type: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        生成 ECharts 配置

        返回前端可直接传给 ECharts 的 option 对象
        """
        x_col = columns[0]
        y_cols = columns[1:]

        x_data = [str(row.get(x_col, "")) for row in rows]

        if display_type == DISPLAY_TYPE_PIE_CHART:
            # 饼图：name + value 格式
            value_col = y_cols[0] if y_cols else columns[0]
            pie_data = [
                {
                    "name": str(row.get(x_col, "")),
                    "value": row.get(value_col, 0),
                }
                for row in rows
            ]
            return {
                "tooltip": {"trigger": "item"},
                "legend": {"orient": "vertical", "left": "left"},
                "series": [
                    {
                        "type": "pie",
                        "radius": "60%",
                        "data": pie_data,
                        "emphasis": {
                            "itemStyle": {
                                "shadowBlur": 10,
                                "shadowOffsetX": 0,
                                "shadowColor": "rgba(0, 0, 0, 0.5)",
                            },
                        },
                    },
                ],
            }

        # 折线图 / 柱状图
        chart_type = (
            "line" if display_type == DISPLAY_TYPE_LINE_CHART else "bar"
        )

        series = []
        for y_col in y_cols:
            series.append({
                "name": y_col,
                "type": chart_type,
                "data": [row.get(y_col, 0) for row in rows],
                "smooth": display_type == DISPLAY_TYPE_LINE_CHART,
            })

        config: dict[str, Any] = {
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": x_data,
            },
            "yAxis": {"type": "value"},
            "series": series,
        }

        if len(y_cols) > 1:
            config["legend"] = {"data": y_cols}

        return config

    @staticmethod
    def _generate_number_summary(
        label: str,
        value: Any,
        generated_sql: GeneratedSQL | None = None,
    ) -> str:
        """生成单值结果的摘要"""
        explanation = (
            generated_sql.explanation if generated_sql else ""
        )
        if explanation:
            return explanation

        formatted_value = value
        if isinstance(value, float):
            formatted_value = f"{value:,.2f}"
        elif isinstance(value, int):
            formatted_value = f"{value:,}"

        return _("data_intelligence.formatter.number_summary",
                 label=label, value=str(formatted_value))

    @staticmethod
    def _generate_summary(
        query_result: QueryResult,
        generated_sql: GeneratedSQL | None = None,
    ) -> str:
        """生成通用结果摘要"""
        parts: list[str] = []

        # LLM 的解释
        if generated_sql and generated_sql.explanation:
            parts.append(generated_sql.explanation)

        # 行数统计
        row_info = _("data_intelligence.formatter.row_count",
                      count=str(query_result.row_count))
        parts.append(row_info)

        if query_result.truncated:
            parts.append(
                _("data_intelligence.formatter.truncated")
            )

        if query_result.masked_columns:
            parts.append(
                _("data_intelligence.formatter.masked",
                  columns=", ".join(query_result.masked_columns))
            )

        return " ".join(parts)


__all__ = [
    "FormattedResult",
    "ResultFormatter",
    "DISPLAY_TYPE_NUMBER",
    "DISPLAY_TYPE_LINE_CHART",
    "DISPLAY_TYPE_BAR_CHART",
    "DISPLAY_TYPE_PIE_CHART",
    "DISPLAY_TYPE_TABLE",
    "DISPLAY_TYPE_TEXT",
]
