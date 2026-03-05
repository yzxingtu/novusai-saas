"""
.env.example 解析器

解析 .env.example 文件，提取环境变量定义，生成 JSON Schema 格式的 valves_schema。

支持的格式：
  # 注释行（作为下一个变量的 description）
  VAR_NAME=default_value          → 有默认值，非必填
  VAR_NAME=                       → 空默认值，非必填
  # VAR_NAME=value                → 注释掉的变量，视为可选
  VAR_NAME 无等号                  → 跳过

从 SKILL.md metadata.clawdbot.requires.env 中标记的变量为必填。
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("ai.skill.env")

# 匹配有效的环境变量行：VAR_NAME=value 或 VAR_NAME=
_ENV_LINE_RE = re.compile(r"^([A-Z][A-Z0-9_]+)\s*=\s*(.*?)\s*$")

# 匹配注释掉的环境变量行：# VAR_NAME=value
_COMMENTED_ENV_RE = re.compile(r"^#\s*([A-Z][A-Z0-9_]+)\s*=\s*(.*?)\s*$")


def parse_env_example(
    content: str,
    required_vars: list[str] | None = None,
) -> dict[str, Any]:
    """
    解析 .env.example 文件内容，返回 JSON Schema 格式的 valves_schema。

    Args:
        content: .env.example 文件内容
        required_vars: 从 SKILL.md requires.env 中提取的必填变量名列表

    Returns:
        JSON Schema dict，格式与 toolkit_parser 的 valves_schema 一致：
        {
            "type": "object",
            "properties": {
                "var_name": {
                    "type": "string",
                    "description": "注释说明",
                    "default": "默认值"
                }
            },
            "required": ["var1", "var2"]
        }

        注意：property key 统一输出为 lowercase，与 Valves Pydantic 类字段名一致。
    """
    if not content or not content.strip():
        return {}

    required_set = {v.lower() for v in (required_vars or [])}
    properties: dict[str, dict[str, Any]] = {}
    required_fields: list[str] = []

    # 收集注释行作为下一个变量的描述
    pending_comments: list[str] = []
    # 保留同组（无空行分隔）的描述，用于连续变量行
    last_group_desc: str = ""

    for line in content.splitlines():
        stripped = line.strip()

        # 空行：重置 pending comments 和组描述
        if not stripped:
            pending_comments = []
            last_group_desc = ""
            continue

        # 纯注释行（不是注释掉的变量定义）
        if stripped.startswith("#"):
            commented_match = _COMMENTED_ENV_RE.match(stripped)
            if commented_match:
                # 注释掉的变量定义 → 可选变量
                var_name = commented_match.group(1)
                default_value = commented_match.group(2).strip("'\"")

                prop: dict[str, Any] = {"type": "string"}
                desc = " ".join(pending_comments).strip()
                if not desc:
                    desc = last_group_desc
                if desc:
                    prop["description"] = desc
                    last_group_desc = desc
                if default_value:
                    prop["default"] = default_value

                properties[var_name.lower()] = prop
                pending_comments = []
            else:
                # 普通注释 → 收集作为描述
                comment_text = stripped.lstrip("#").strip()
                if comment_text:
                    pending_comments.append(comment_text)
            continue

        # 环境变量定义行
        env_match = _ENV_LINE_RE.match(stripped)
        if env_match:
            var_name = env_match.group(1)
            raw_value = env_match.group(2).strip("'\"")

            prop = {"type": _infer_type(raw_value)}
            desc = " ".join(pending_comments).strip()
            if not desc:
                desc = last_group_desc
            if desc:
                prop["description"] = desc
                last_group_desc = desc

            # 判断是否为占位符默认值
            if raw_value and not _is_placeholder(raw_value):
                prop["default"] = raw_value

            # 是否必填（统一 lowercase 比较）
            lower_name = var_name.lower()
            if lower_name in required_set:
                required_fields.append(lower_name)

            properties[lower_name] = prop
            pending_comments = []
            continue

        # 其他行：忽略
        pending_comments = []
        last_group_desc = ""

    if not properties:
        return {}

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required_fields:
        schema["required"] = required_fields

    logger.info(
        "Parsed .env.example: %d variables (%d required)",
        len(properties), len(required_fields),
    )
    return schema


def _is_placeholder(value: str) -> bool:
    """判断值是否为占位符（不应作为实际默认值）"""
    lower = value.lower()
    # 常见占位符模式
    if lower.startswith("xxx") or lower.startswith("your-"):
        return True
    if "xxxx" in lower:
        return True
    if lower.startswith("cli_xxxx"):
        return True
    # 全 x 占位符
    return bool(re.match(r"^[xX]+$", value))


def _infer_type(value: str) -> str:
    """从默认值推断 JSON Schema 类型"""
    if not value:
        return "string"

    # 整数
    try:
        int(value)
        return "integer"
    except ValueError:
        pass

    # 浮点数
    try:
        float(value)
        return "number"
    except ValueError:
        pass

    # 布尔
    if value.lower() in ("true", "false"):
        return "boolean"

    # JSON 对象/数组
    if value.startswith("{") or value.startswith("["):
        return "string"

    return "string"


__all__ = ["parse_env_example"]
