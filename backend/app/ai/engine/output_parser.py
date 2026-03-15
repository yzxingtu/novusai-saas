"""
Output Variable Extractor / 输出变量提取器

Extracts structured data from AI replies, supports JSON code block extraction
and field extraction based on output_schema.
从 AI 回复中提取结构化数据，支持 JSON 代码块提取和基于 output_schema 的字段提取。
"""

import json
import re
from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("ai.engine.output_parser")

# Match ```json ... ``` code blocks / 匹配 ```json ... ``` 代码块
_JSON_BLOCK_RE = re.compile(
    r"```json\s*\n(.*?)\n\s*```",
    re.DOTALL | re.IGNORECASE,
)


def extract_json_block(text: str) -> dict[str, Any] | list[Any] | None:
    """
    Extract the first ```json ... ``` code block from text and parse as JSON.
    从文本中提取第一个 ```json ... ``` 代码块并解析为 JSON。

    Args:
        text: AI reply text / AI 回复文本

    Returns:
        Parsed dict/list or None / 解析后的 dict/list 或 None
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
    Extract field values from text based on output_schema definition.
    基于 output_schema 定义从文本中提取字段值。

    Prioritizes extraction from JSON code blocks, falls back to regex matching
    "field_name: value" patterns.
    优先从 JSON 代码块提取，若无则尝试正则匹配 "field_name: value" 模式。

    output_schema format / 格式:
        [{"name": "summary", "type": "string"}, {"name": "score", "type": "number"}]

    Args:
        text: AI reply text / AI 回复文本
        output_schema: Field definition list / 字段定义列表

    Returns:
        Extracted field dictionary / 提取到的字段字典
    """
    result: dict[str, Any] = {}
    if not output_schema:
        return result

    # 1. Try extracting from JSON code block first / 先尝试从 JSON 代码块提取
    json_data = extract_json_block(text)
    if isinstance(json_data, dict):
        for field in output_schema:
            name = field.get("name", "")
            if name and name in json_data:
                result[name] = json_data[name]

    # 2. Supplement fields not extracted from JSON: regex match "field: value" / 补充未从 JSON 提取到的字段
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
    Unified extraction entry point.
    统一提取入口。

    Args:
        text: AI reply text / AI 回复文本
        output_schema: Output field definition (from Agent.output_schema) / 输出字段定义

    Returns:
        Extracted field dict, or None if no schema or no result / 提取到的字段字典，若无结果则返回 None
    """
    if not output_schema or not text:
        return None

    result = extract_fields(text, output_schema)
    return result if result else None


def _coerce_type(value: str, field_type: str) -> Any:
    """Attempt to convert string value to target type / 尝试将字符串值转换为目标类型"""
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
