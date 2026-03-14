"""
hosts 文件管理工具（仅开发环境） / Hosts File Manager (dev environment only)

在 DEBUG 模式下，自动管理 hosts 文件中的企业域名映射。
Automatically manages tenant domain mappings in hosts file under DEBUG mode.
支持 Windows / macOS / Linux，生产环境（DEBUG=false）完全不触发。
Supports Windows / macOS / Linux. Never triggered in production (DEBUG=false).

标记格式 / Entry format:
    127.0.0.1  demo.app.local  # NovusAI-Dev

CLI 用法 / CLI usage (in backend/ dir, requires admin/sudo):
    python -m app.core.hosts_helper add demo.app.local
    python -m app.core.hosts_helper remove demo.app.local
    python -m app.core.hosts_helper list
    python -m app.core.hosts_helper cleanup
"""

from __future__ import annotations

import asyncio
import os
import platform
import re
import sys
from pathlib import Path
from typing import Literal, TypedDict

from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

MARKER = "# NovusAI-Dev"
LOOPBACK_IP = "127.0.0.1"

_HOSTS_PATHS: dict[str, Path] = {
    "Windows": Path(r"C:\Windows\System32\drivers\etc\hosts"),
    "Darwin": Path("/etc/hosts"),
    "Linux": Path("/etc/hosts"),
}

HostEntryState = Literal["managed_present", "manual_present", "missing", "unsupported"]


class HostsRuntimeInfo(TypedDict):
    enabled: bool
    debug: bool
    supported: bool
    os_name: str
    hosts_path: str | None
    requires_elevation: bool
    can_write_hint: bool


class HostEntryStatus(TypedDict):
    domain: str
    status: HostEntryState
    matched_ip: str | None
    managed: bool


# ──────────────────────────────────────────────
# 环境检测
# ──────────────────────────────────────────────


def _get_hosts_path() -> Path | None:
    """返回当前操作系统的 hosts 文件路径，不支持则返回 None"""
    return _HOSTS_PATHS.get(platform.system())


def is_dev_local() -> bool:
    """
    判断当前是否为开发环境（需要自动管理 hosts）

    条件：settings.DEBUG == True 且当前 OS 支持 hosts 操作

    Returns:
        True = DEBUG 模式且 OS 支持，应执行 hosts 操作
    """
    from app.core.config import settings

    return bool(settings.DEBUG) and _get_hosts_path() is not None


# ──────────────────────────────────────────────
# 底层文件读写
# ──────────────────────────────────────────────


def _read_lines() -> list[str]:
    """读取 hosts 文件所有行（含换行符），文件不存在返回空列表"""
    path = _get_hosts_path()
    if not path or not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)


def _write_lines(lines: list[str]) -> None:
    """将行列表写回 hosts 文件，自动补末尾换行"""
    path = _get_hosts_path()
    if not path:
        return
    content = "".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")


# ──────────────────────────────────────────────
# 行解析工具
# ──────────────────────────────────────────────


def _is_managed(line: str) -> bool:
    """是否为本工具管理的条目（含 MARKER 注释）"""
    return MARKER in line


def _normalize_domain(domain: str) -> str:
    """标准化域名，统一去空格并转小写 / Normalize domain by trimming spaces and lowercasing"""
    return domain.strip().lower()


def _parse_hosts_line(line: str) -> tuple[str, list[str]] | None:
    """解析 hosts 行并返回 IP 与域名列表，忽略注释与空行 / Parse a hosts line into IP and domains while ignoring comments and blank lines"""
    line_body = line.split("#", 1)[0].strip()
    if not line_body:
        return None

    parts = re.split(r"\s+", line_body)
    if len(parts) < 2:
        return None

    ip = parts[0]
    domains = [part for part in parts[1:] if part]
    if not domains:
        return None

    return ip, domains


def _extract_domain(line: str) -> str | None:
    """从 hosts 行提取域名，不是托管行则返回 None"""
    if not _is_managed(line):
        return None
    parsed = _parse_hosts_line(line)
    if not parsed:
        return None
    _, domains = parsed
    return domains[0] if domains else None


def _extract_managed_domains(line: str) -> list[str]:
    """提取单行中的所有托管域名，非托管行返回空列表 / Extract all managed domains from one line, or return an empty list for unmanaged lines"""
    if not _is_managed(line):
        return []
    parsed = _parse_hosts_line(line)
    if not parsed:
        return []
    _, domains = parsed
    return domains


def _has_entry(lines: list[str], domain: str) -> bool:
    """检查域名是否已存在于任意 hosts 条目中（大小写不敏感） / Check whether the domain exists in any hosts entry, case-insensitively"""
    return _inspect_entry(lines, domain)["status"] in {"managed_present", "manual_present"}


def _inspect_entry(lines: list[str], domain: str) -> HostEntryStatus:
    """在已读取的 hosts 行中检查域名状态 / Inspect the domain state from already loaded hosts lines"""
    normalized_domain = _normalize_domain(domain)

    for line in lines:
        parsed = _parse_hosts_line(line)
        if not parsed:
            continue

        ip, domains = parsed
        if any(_normalize_domain(item) == normalized_domain for item in domains):
            managed = _is_managed(line)
            return {
                "domain": domain.strip(),
                "status": "managed_present" if managed else "manual_present",
                "matched_ip": ip,
                "managed": managed,
            }

    return {
        "domain": domain.strip(),
        "status": "missing",
        "matched_ip": None,
        "managed": False,
    }


def _make_entry(domain: str) -> str:
    """生成标准格式的 hosts 条目行（含换行符）"""
    return f"{LOOPBACK_IP}  {domain}  {MARKER}\n"


def get_runtime_info() -> HostsRuntimeInfo:
    """返回当前 hosts 管理的运行时信息 / Return runtime information for current hosts management"""
    from app.core.config import settings

    hosts_path = _get_hosts_path()
    supported = hosts_path is not None

    can_write_hint = False
    if hosts_path is not None:
        probe_path = hosts_path if hosts_path.exists() else hosts_path.parent
        can_write_hint = probe_path.exists() and os.access(probe_path, os.W_OK)

    return {
        "enabled": bool(settings.DEBUG) and supported,
        "debug": bool(settings.DEBUG),
        "supported": supported,
        "os_name": platform.system(),
        "hosts_path": str(hosts_path) if hosts_path else None,
        "requires_elevation": supported and not can_write_hint,
        "can_write_hint": can_write_hint,
    }


def get_domain_entry_status(domain: str) -> HostEntryStatus:
    """检查单个域名在 hosts 文件中的状态 / Check the status of a single domain inside the hosts file"""
    hosts_path = _get_hosts_path()
    if hosts_path is None:
        return {
            "domain": domain.strip(),
            "status": "unsupported",
            "matched_ip": None,
            "managed": False,
        }

    try:
        return _inspect_entry(_read_lines(), domain)
    except Exception:
        logger.exception(
            "[NovusAI-Dev] Failed to inspect hosts entry status: %s",
            domain,
        )
        return {
            "domain": domain.strip(),
            "status": "missing",
            "matched_ip": None,
            "managed": False,
        }


# ──────────────────────────────────────────────
# 核心操作（同步，供 to_thread 使用）
# ──────────────────────────────────────────────


def add_host_entry(domain: str) -> bool:
    """
    添加域名到 hosts 文件（幂等）

    - 已存在：直接返回 True，不重复写入
    - 权限不足：打印详细指引，返回 False，不阻塞业务
    - 非 DEBUG 环境：直接返回 False

    Args:
        domain: 要添加的域名（不含端口）

    Returns:
        True = 添加成功或已存在；False = 跳过或失败
    """
    if not is_dev_local():
        return False

    hosts_path = _get_hosts_path()

    try:
        lines = _read_lines()
        entry_status = _inspect_entry(lines, domain)
        if entry_status["status"] == "managed_present":
            logger.info(
                "[NovusAI-Dev] managed hosts entry already exists, skipping: %s  %s",
                LOOPBACK_IP,
                domain,
            )
            return True
        if entry_status["status"] == "manual_present":
            logger.info(
                "[NovusAI-Dev] manual hosts entry already exists, skipping managed write: %s  %s",
                entry_status["matched_ip"] or LOOPBACK_IP,
                domain,
            )
            return True

        lines.append(_make_entry(domain))
        _write_lines(lines)

        logger.info(
            "\n"
            "┌─────────────────────────────────────────────────────────┐\n"
            "│  [NovusAI-Dev] LOCAL DEV ENVIRONMENT - hosts updated    │\n"
            "└─────────────────────────────────────────────────────────┘\n"
            "  Added : %s  %s\n"
            "  File  : %s\n"
            "  Access: http://%s:8000 (API) | http://%s:5666 (Frontend)\n",
            LOOPBACK_IP,
            domain,
            hosts_path,
            domain,
            domain,
        )
        return True

    except PermissionError:
        _print_permission_warning("add", domain, hosts_path)
        return False
    except OSError as exc:
        logger.warning(
            "[NovusAI-Dev] Could not write hosts file (%s): %s",
            type(exc).__name__,
            exc,
        )
        return False
    except Exception:
        logger.exception(
            "[NovusAI-Dev] Unexpected error while adding hosts entry: %s",
            domain,
        )
        return False


def remove_host_entry(domain: str) -> bool:
    """
    从 hosts 文件移除域名托管条目

    - 条目不存在：直接返回 True（幂等）
    - 权限不足：打印指引，返回 False
    - 非 DEBUG 环境：直接返回 False

    Args:
        domain: 要移除的域名

    Returns:
        True = 移除成功或本就不存在；False = 失败
    """
    if not is_dev_local():
        return False

    hosts_path = _get_hosts_path()

    try:
        lines = _read_lines()
        dl = domain.lower()

        new_lines: list[str] = []
        removed = False
        for line in lines:
            d = _extract_domain(line)
            if d and d.lower() == dl:
                removed = True
                continue
            new_lines.append(line)

        if not removed:
            return True

        _write_lines(new_lines)
        logger.info(
            "[NovusAI-Dev] LOCAL DEV ENVIRONMENT - removed hosts entry: %s",
            domain,
        )
        return True

    except PermissionError:
        _print_permission_warning("remove", domain, hosts_path)
        return False
    except OSError as exc:
        logger.warning(
            "[NovusAI-Dev] Could not update hosts file (%s): %s",
            type(exc).__name__,
            exc,
        )
        return False
    except Exception:
        logger.exception(
            "[NovusAI-Dev] Unexpected error while removing hosts entry: %s",
            domain,
        )
        return False


def list_managed_entries() -> list[str]:
    """
    列出所有 NovusAI-Dev 托管的域名

    Returns:
        域名列表，空列表表示无托管条目或读取失败
    """
    try:
        lines = _read_lines()
        return [domain for line in lines for domain in _extract_managed_domains(line)]
    except Exception:
        logger.exception("[NovusAI-Dev] Failed to read hosts file")
        return []


def cleanup_all_entries() -> int:
    """
    清除 hosts 文件中所有 NovusAI-Dev 托管条目
    Remove all NovusAI-Dev managed entries from the hosts file

    Returns:
        清除的条目数量（0 = 无或失败）/ Number of entries removed (0 = none or failed)
    """
    if not is_dev_local():
        return 0

    hosts_path = _get_hosts_path()

    try:
        lines = _read_lines()
        new_lines = [line for line in lines if not _is_managed(line)]
        removed = len(lines) - len(new_lines)

        if removed == 0:
            logger.info("[NovusAI-Dev] No managed entries found in hosts file")
            return 0

        _write_lines(new_lines)
        logger.info(
            "[NovusAI-Dev] LOCAL DEV ENVIRONMENT - cleaned %d entries from hosts file",
            removed,
        )
        return removed

    except PermissionError:
        _print_permission_warning("cleanup", "all NovusAI-Dev entries", hosts_path)
        return 0
    except OSError as exc:
        logger.warning(
            "[NovusAI-Dev] Could not cleanup hosts file (%s): %s",
            type(exc).__name__,
            exc,
        )
        return 0
    except Exception:
        logger.exception("[NovusAI-Dev] Unexpected error during cleanup")
        return 0


# ──────────────────────────────────────────────
# 异步包装（供 Service 层 asyncio 上下文使用）
# ──────────────────────────────────────────────


async def async_add_host_entry(domain: str) -> bool:
    """异步添加 hosts 条目（通过 to_thread 不阻塞事件循环）/ Add a hosts entry asynchronously via to_thread"""
    return await asyncio.to_thread(add_host_entry, domain)


async def async_remove_host_entry(domain: str) -> bool:
    """异步移除 hosts 条目 / Remove a hosts entry asynchronously"""
    return await asyncio.to_thread(remove_host_entry, domain)


async def async_cleanup_all_entries() -> int:
    """异步清除所有托管条目 / Remove all managed hosts entries asynchronously"""
    return await asyncio.to_thread(cleanup_all_entries)


async def async_get_runtime_info() -> HostsRuntimeInfo:
    """异步获取 hosts 管理运行时信息 / Get hosts management runtime information asynchronously"""
    return await asyncio.to_thread(get_runtime_info)


async def async_get_domain_entry_status(domain: str) -> HostEntryStatus:
    """异步获取单个域名的 hosts 状态 / Get the hosts status for a single domain asynchronously"""
    return await asyncio.to_thread(get_domain_entry_status, domain)


# ──────────────────────────────────────────────
# 权限错误提示
# ──────────────────────────────────────────────


def _print_permission_warning(action: str, target: str, hosts_path: Path | None) -> None:
    """打印权限不足的详细操作指引（不抛出异常）"""
    path_str = str(hosts_path) if hosts_path else "hosts"
    system = platform.system()
    entry_line = f"{LOOPBACK_IP}  {target}  {MARKER}"

    if system == "Windows":
        _instructions = (
            f"\n"
            f"  ┌─ Option A: PowerShell (Run as Administrator) ────────────────────┐\n"
            f'  │  Add-Content -Path "{path_str}"'
            f' -Value "{entry_line}"  │\n'
            f"  └──────────────────────────────────────────────────────────────────┘\n"
            f"  ┌─ Option B: Notepad (Run as Administrator) ────────────────────────┐\n"
            f"  │  1. Open Notepad as Administrator                                 │\n"
            f"  │  2. File → Open → {path_str}                │\n"
            f"  │  3. Append:  {entry_line:<52s}  │\n"
            f"  └──────────────────────────────────────────────────────────────────┘\n"
            f"  ┌─ Option C: Re-run backend as Administrator ───────────────────────┐\n"
            f"  │  Right-click PowerShell → Run as administrator                    │\n"
            f"  │  cd backend && uvicorn app.main:app --reload --reload-dir app     │\n"
            f"  └──────────────────────────────────────────────────────────────────┘\n"
        )
    else:
        _instructions = (
            f"\n"
            f"  Run with sudo:\n"
            f'  $ sudo sh -c \'echo "{entry_line}" >> {path_str}\'\n'
            f"\n"
            f"  Or re-run backend with sudo:\n"
            f"  $ sudo uvicorn app.main:app --reload --reload-dir app\n"
        )

    logger.warning(
        "\n"
        "╔══════════════════════════════════════════════════════════════════════╗\n"
        "║  [NovusAI-Dev] Cannot %s hosts entry — Permission Denied           ║\n"
        "╚══════════════════════════════════════════════════════════════════════╝\n"
        "\n"
        "  Action : %s  →  %s\n"
        "  File   : %s\n"
        "%s"
        "\n"
        "  NOTE: Domain record has been saved to database.\n"
        "        hosts update is optional for local browser access.\n"
        "        Use CLI to manage manually (run as admin):\n"
        "        python -m app.core.hosts_helper %s %s\n",
        action,
        action,
        target,
        path_str,
        _instructions,
        action,
        target if action != "cleanup" else "",
    )


# ──────────────────────────────────────────────
# CLI 入口（python -m app.core.hosts_helper）
# ──────────────────────────────────────────────


def _cli_main() -> None:
    """
    命令行工具入口

    用法（在 backend/ 目录下，建议管理员/sudo 权限运行）：
        python -m app.core.hosts_helper add <domain>
        python -m app.core.hosts_helper remove <domain>
        python -m app.core.hosts_helper list
        python -m app.core.hosts_helper cleanup
    """
    args = sys.argv[1:]

    if not args:
        print("Usage: python -m app.core.hosts_helper <command> [domain]")
        print("Commands:")
        print("  add <domain>    Add domain to hosts file")
        print("  remove <domain> Remove domain from hosts file")
        print("  list            List all NovusAI-Dev managed entries")
        print("  cleanup         Remove ALL NovusAI-Dev entries")
        sys.exit(0)

    command = args[0].lower()

    if command == "add":
        if len(args) < 2:
            print("Error: domain is required for 'add'")
            sys.exit(1)
        domain = args[1]
        ok = add_host_entry(domain)
        if ok:
            print(f"OK  {LOOPBACK_IP}  {domain}  {MARKER}")
        else:
            print(f"FAILED to add {domain!r} — check permissions or DEBUG setting")
            sys.exit(1)

    elif command == "remove":
        if len(args) < 2:
            print("Error: domain is required for 'remove'")
            sys.exit(1)
        domain = args[1]
        ok = remove_host_entry(domain)
        if ok:
            print(f"OK  Removed: {domain}")
        else:
            print(f"FAILED to remove {domain!r} — check permissions")
            sys.exit(1)

    elif command == "list":
        entries = list_managed_entries()
        if entries:
            print(f"NovusAI-Dev managed entries ({len(entries)}):")
            for d in entries:
                print(f"  {LOOPBACK_IP}  {d}  {MARKER}")
        else:
            print("No NovusAI-Dev managed entries found.")

    elif command == "cleanup":
        count = cleanup_all_entries()
        if count > 0:
            print(f"OK  Removed {count} entries")
        else:
            print("Nothing to clean up.")

    else:
        print(f"Unknown command: {command!r}")
        print("Available commands: add, remove, list, cleanup")
        sys.exit(1)


if __name__ == "__main__":
    _cli_main()
