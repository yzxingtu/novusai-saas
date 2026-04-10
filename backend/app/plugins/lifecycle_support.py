"""Shared lifecycle helpers used by the thin PluginLifecycle facade and mixins."""

from __future__ import annotations

import functools
import re
import subprocess
import sys
from typing import Any

import anyio

_IS_WINDOWS = sys.platform == "win32"
_SAFE_PLUGIN_TABLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_UNLOCK_IF_OWNER_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


async def run_subprocess_async(
    *args: str,
    timeout: int = 120,
    cwd: str | None = None,
    text: bool = True,
    capture_output: bool = True,
    shell: bool | None = None,
    env: dict[str, str] | None = None,
) -> Any:
    """Run subprocess.run in a worker thread to avoid blocking the event loop."""
    use_shell = shell if shell is not None else _IS_WINDOWS
    return await anyio.to_thread.run_sync(
        functools.partial(
            subprocess.run,
            list(args),
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            cwd=cwd,
            shell=use_shell,
            env=env,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
        )
    )


def is_safe_plugin_table_name(
    table_name: str,
    expected_prefix: list[str] | str | tuple[str, ...],
) -> bool:
    """Allow only safe table names that stay inside the plugin-owned prefix set."""
    if not _SAFE_PLUGIN_TABLE_RE.match(table_name):
        return False
    if isinstance(expected_prefix, str):
        prefixes = (expected_prefix,)
    else:
        prefixes = tuple(expected_prefix)
    return any(table_name.startswith(prefix) for prefix in prefixes)


def escape_like_pattern(value: str) -> str:
    """Escape SQL LIKE metacharacters so plugin prefixes stay literal."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


__all__ = [
    "_IS_WINDOWS",
    "_UNLOCK_IF_OWNER_LUA",
    "escape_like_pattern",
    "is_safe_plugin_table_name",
    "run_subprocess_async",
]
