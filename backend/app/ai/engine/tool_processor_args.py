from __future__ import annotations

import json
import re
from typing import Any

from app.ai.text_semantics import (
    remove_trailing_json_commas,
    strip_model_function_call_markup,
)
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.engine.tool_processor.args")


def _strip_dsml_from_args(s: str) -> str:
    """Remove leaked DSML markers from tool arguments (DeepSeek etc.)."""
    return strip_model_function_call_markup(s)


def _fix_unescaped_control_chars(s: str) -> str:
    """Replace unescaped control chars inside JSON string values (with look-ahead
    quote disambiguation to handle embedded quotes like "她叫"小喵"的猫").
    """
    chars = list(s)
    n = len(chars)
    result: list[str] = []
    in_string = False
    escape_next = False
    i = 0
    while i < n:
        ch = chars[i]
        if in_string:
            if escape_next:
                result.append(ch)
                escape_next = False
            elif ch == "\\":
                result.append(ch)
                escape_next = True
            elif ch == '"':
                j = i + 1
                while j < n and chars[j] in " \t\r\n":
                    j += 1
                if j >= n or chars[j] in ":,}]":
                    in_string = False
                    result.append(ch)
                else:
                    result.append('\\"')
            elif ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            else:
                result.append(ch)
        else:
            if ch == '"':
                in_string = True
            result.append(ch)
        i += 1
    return "".join(result)


def _brute_force_control_chars(s: str) -> str:
    """Replace ALL literal control characters (\n, \r, \t) with spaces
    as a last-resort fix when context-aware repair fails."""
    return (
        s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    )


def _try_convert_single_quotes(s: str) -> str | None:
    """Try converting Python-style single-quoted dict to JSON (only when appropriate)."""
    s = s.strip()
    if not s.startswith("{") or "'" not in s:
        return None
    try:
        import ast

        parsed = ast.literal_eval(s)
        if isinstance(parsed, dict):
            return json.dumps(parsed, ensure_ascii=False)
    except (ValueError, SyntaxError):
        pass
    return None


def _try_fix_bare_single_key_object(s: str) -> str | None:
    """Repair simple one-field objects where the key loses its closing quote
    and/or the value is emitted as a bare locator-like string.

    Example:
    `{"table_locator: div >:nth-of-type(2)}` ->
    `{"table_locator": "div >:nth-of-type(2)"}`
    """
    match = re.match(
        r'^\{\s*"(?P<key>[A-Za-z_][A-Za-z0-9_]*)"?\s*:\s*(?P<value>.+)\}\s*$',
        s.strip(),
    )
    if not match:
        return None

    key = str(match.group("key") or "").strip()
    raw_value = str(match.group("value") or "").strip().rstrip(",")
    if not key or not raw_value:
        return None
    if raw_value.startswith('"') and not raw_value.endswith('"'):
        return None

    try:
        parsed_value: Any = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed_value = raw_value

    if isinstance(parsed_value, (dict, list)):
        return None

    return json.dumps({key: parsed_value}, ensure_ascii=False)


def _try_fix_truncation(s: str) -> str:
    """Try closing truncated string and brackets with look-ahead quote handling."""
    chars = list(s)
    n = len(chars)
    result: list[str] = []
    in_string = False
    escape_next = False
    brace_stack: list[str] = []
    i = 0
    while i < n:
        ch = chars[i]
        if in_string:
            if escape_next:
                result.append(ch)
                escape_next = False
            elif ch == "\\":
                result.append(ch)
                escape_next = True
            elif ch == '"':
                j = i + 1
                while j < n and chars[j] in " \t\r\n":
                    j += 1
                if j >= n or chars[j] in ":,}]":
                    in_string = False
                    result.append(ch)
                else:
                    result.append('\\"')
            elif ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            else:
                result.append(ch)
        else:
            if ch == '"':
                in_string = True
            if ch == "{":
                brace_stack.append("}")
            elif ch == "[":
                brace_stack.append("]")
            elif ch in "}]" and brace_stack:
                brace_stack.pop()
            result.append(ch)
        i += 1
    if in_string:
        result.append('"')
    while brace_stack:
        result.append(brace_stack.pop())
    return "".join(result)


def try_repair_json(raw: str) -> dict[str, Any] | None:
    """
    Attempt to repair common JSON malformations.
    尝试修复常见 JSON 畸形：DSML 泄漏、尾部逗号、缺失括号、
    未转义控制字符、Python 风格单引号、截断。
    """
    s = raw.strip()
    # Phase A: DSML cleanup / 阶段 A：去除 DSML
    s = _strip_dsml_from_args(s)

    # Trailing commas and missing brackets / 尾部逗号与补全括号
    s = remove_trailing_json_commas(s)
    s_before_braces = s
    opens = s.count("{") - s.count("}")
    if opens > 0:
        s += "}" * opens
    opens = s.count("[") - s.count("]")
    if opens > 0:
        s += "]" * opens

    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Phase B: unescaped control chars in strings / 阶段 B：字符串内未转义控制字符
    s2 = _fix_unescaped_control_chars(s)
    if s2 != s:
        try:
            parsed = json.loads(s2)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            s = s2

    # Phase C: Python-style single-quoted dict / 阶段 C：Python 单引号字典
    s3 = _try_convert_single_quotes(s)
    if s3:
        try:
            parsed = json.loads(s3)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    # Phase D: repair simple malformed single-field objects often emitted by
    # fallback tool-capable models for locator-style page tools.
    s4 = _try_fix_bare_single_key_object(s)
    if s4 and s4 != s:
        try:
            parsed = json.loads(s4)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    # Phase E: truncation repair — use s before brace padding so } does not
    # close inside string / 阶段 E：截断修复（补括号前字符串，避免 } 误入未闭合串）
    s5 = _try_fix_truncation(s_before_braces)
    if s5 != s:
        try:
            parsed = json.loads(s5)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    # Phase F: replace control chars with spaces (last resort; may lose
    # newlines) / 阶段 F：控制符替换为空格（最后手段，可能丢失换行语义）
    s6 = _brute_force_control_chars(s)
    if s6 != s:
        # Again strip trailing commas and balance braces on cleaned string / 清理后再次去尾部逗号并补括号
        s6 = remove_trailing_json_commas(s6)
        opens = s6.count("{") - s6.count("}")
        if opens > 0:
            s6 += "}" * opens
        opens = s6.count("[") - s6.count("]")
        if opens > 0:
            s6 += "]" * opens
        try:
            parsed = json.loads(s6)
            if isinstance(parsed, dict):
                logger.info("JSON repaired via brute-force control-char replacement")
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def parse_tool_arguments(
    raw_args: str | dict,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Parse tool call arguments (JSON string → dict).
    解析工具调用参数（JSON 字符串 → dict）

    Returns:
        (args, error_type): On success (dict, None). On JSON parse failure (None, "invalid_tool_arguments_json").
        成功返回 (dict, None)；JSON 解析失败返回 (None, "invalid_tool_arguments_json")。
    """
    if isinstance(raw_args, dict):
        return raw_args, None
    if not raw_args:
        return {}, None
    try:
        parsed = json.loads(raw_args)
        if isinstance(parsed, str):
            repaired = try_repair_json(parsed)
            if repaired is not None:
                return repaired, None
            try:
                nested = json.loads(parsed)
            except json.JSONDecodeError:
                nested = None
            if isinstance(nested, dict):
                return nested, None
        if not isinstance(parsed, dict):
            return None, "invalid_tool_arguments_json"
        return parsed, None
    except json.JSONDecodeError:
        repaired = try_repair_json(raw_args)
        if repaired is not None:
            return repaired, None
        raw_snippet = (
            (raw_args[:500] + "…")
            if isinstance(raw_args, str) and len(raw_args) > 500
            else raw_args
        )
        logger.warning(
            "Tool arguments JSON parse failed: raw_args_snippet={} error=invalid_tool_arguments_json",
            repr(raw_snippet)[:600],
        )
        return None, "invalid_tool_arguments_json"
