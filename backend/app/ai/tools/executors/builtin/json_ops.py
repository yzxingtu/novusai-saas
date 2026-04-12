"""
JSON formatting helpers for builtin tools.
内置工具 JSON 格式化辅助函数。
"""

from __future__ import annotations

import json


def format_json(data: str = "") -> str:
    """Format JSON string / 格式化 JSON 字符串"""
    try:
        parsed = json.loads(data)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError as exc:
        return f"Error: Invalid JSON - {exc}"


__all__ = ["format_json"]
