"""
输出变量提取器

从 AI 回复中提取结构化数据，支持 JSON 代码块提取和基于 output_schema 的字段提取。
"""

import json
import re
from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("ai.engine.output_parser")

# 匹配 ```json ... ``` 代码块
_JSON_BLOCK_RE = re.compile(
    r"```json\s*\n(.*?)\n\s*```",
    re.DOTALL | re.IGNORECASE,
)


def extract_json_block(text: str) -> dict[str, Any] | list[Any] | None:
    """
    从文本中提取第一个 ```json ... ``` 代码块并解析为 JSON

    Args:
        text: AI 回复文本

    Returns:
        解析后的 dict/list 或 None
    """
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.debug("Failed to parse JSON block: %s", str(exc))
        return None


def extract_fields(
    text: str,
    output_schema: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    基于 output_schema 定义从文本中提取字段值

    优先从 JSON 代码块提取，若无则尝试正则匹配 "field_name: value" 模式

    output_schema 格式:
        [{"name": "summary", "type": "string"}, {"name": "score", "type": "number"}]

    Args:
        text: AI 回复文本
        output_schema: 字段定义列表

    Returns:
        提取到的字段字典
    """
    result: dict[str, Any] = {}
    if not output_schema:
        return result

    # 1. 先尝试从 JSON 代码块提取
    json_data = extract_json_block(text)
    if isinstance(json_data, dict):
        for field in output_schema:
            name = field.get("name", "")
            if name and name in json_data:
                result[name] = json_data[name]

    # 2. 补充未从 JSON 提取到的字段：正则匹配 "field: value"
    for field in output_schema:
        name = field.get("name", "")
        if not name or name in result:
            continue

        pattern = re.compile(
            rf"(?:^|\n)\s*{re.escape(name)}\s*[:：]\s*(.+?)(?:\n|$)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            raw_value = match.group(1).strip()
            result[name] = _coerce_type(raw_value, field.get("type", "string"))

    return result


def parse_output(
    text: str,
    output_schema: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """
    统一提取入口

    Args:
        text: AI 回复文本
        output_schema: 输出字段定义（来自 Agent.output_schema）

    Returns:
        提取到的字段字典，若无 schema 或无结果则返回 None
    """
    if not output_schema or not text:
        return None

    result = extract_fields(text, output_schema)
    return result if result else None


def _coerce_type(value: str, field_type: str) -> Any:
    """尝试将字符串值转换为目标类型"""
    if field_type == "number":
        try:
            return float(value) if "." in value else int(value)
        except ValueError:
            return value
    if field_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    return value


__all__ = [
    "extract_json_block",
    "extract_fields",
    "parse_output",
]
