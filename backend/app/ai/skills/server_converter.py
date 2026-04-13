"""
Server Package → Toolkit Converter
Server 包 → Toolkit 转换器

Automatically converts SKILL.md server packages (FastAPI-based)
into class Tools format compatible with ToolkitParser.
自动将 SKILL.md server 包（基于 FastAPI）转换为与 ToolkitParser 兼容的 class Tools 格式。

Handles the common pattern / 处理常见模式：
  server/
    auth.py          → _get_token() / _request() internal helpers / 内部辅助函数
    xxx_api.py       → async def methods in class Tools / Tools 类的异步方法
    main.py          → skipped (app entry point) / 跳过（应用入口）

Falls back to a combined-source template if auto-conversion fails.
自动转换失败时回退到合并源码模板。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.skills.server_converter_helpers import convert_server_to_toolkit as _convert


def convert_server_to_toolkit(
    server_dir: Path,
    metadata: dict[str, Any],
    env_schema: dict[str, Any] | None = None,
) -> str:
    """
    Convert a server/ directory to a class Tools Python source.
    将 server/ 目录转换为 class Tools 的 Python 源码。

    Args:
        server_dir: Path to the extracted server/ directory / 解压后的 server/ 目录路径
        metadata: Parsed SKILL.md metadata / 解析后的 SKILL.md 元数据
        env_schema: Valves schema parsed from .env.example (optional),
                    used to generate Valves class with descriptions and defaults /
                    从 .env.example 解析的 valves_schema（可选），
                    用于生成带描述和默认值的 Valves 类

    Returns:
        Python source code containing class Valves + class Tools /
        包含 class Valves + class Tools 的 Python 源码
    """
    return _convert(server_dir, metadata, env_schema)
