"""
Runtime identity helpers / 运行时身份标识辅助工具

Provides lightweight branch / commit / pid markers for startup and request logs.
为启动日志与请求日志提供轻量分支 / 提交 / 进程标识。
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return start.resolve()


@lru_cache(maxsize=1)
def get_runtime_identity() -> dict[str, str]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    branch = "unknown"
    commit = "unknown"

    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        ).stdout.strip() or branch
    except Exception:
        branch = "unknown"

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        ).stdout.strip() or commit
    except Exception:
        commit = "unknown"

    return {
        "branch": branch,
        "commit": commit,
        "pid": str(os.getpid()),
    }


def get_runtime_identity_tag() -> str:
    identity = get_runtime_identity()
    return (
        f"{identity.get('branch', 'unknown')}"
        f"@{identity.get('commit', 'unknown')}"
        f"#pid={identity.get('pid', 'unknown')}"
    )


__all__ = ["get_runtime_identity", "get_runtime_identity_tag"]
