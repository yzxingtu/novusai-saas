"""
插件安全扫描（基础版）

扫描插件 Python 代码中的危险调用，结果作为 warning 包含在安装预览中。
不阻止安装，仅警告。
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# 危险函数调用
_DANGEROUS_CALLS: set[str] = {
    "eval", "exec", "compile", "__import__",
    "breakpoint", "exit", "quit",
}

# 危险模块
_DANGEROUS_MODULES: set[str] = {
    "subprocess", "os", "shutil", "ctypes",
    "pickle", "marshal", "socket",
    "multiprocessing", "threading",
}

# 危险属性访问
_DANGEROUS_ATTRS: dict[str, set[str]] = {
    "os": {"system", "popen", "remove", "rmdir", "unlink", "rename", "chmod",
           "chown", "listdir", "walk", "environ"},
    "shutil": {"rmtree", "move", "copy", "copytree"},
    "subprocess": {"run", "Popen", "call", "check_output", "check_call"},
}


class SecurityScanResult:
    """安全扫描结果"""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.files_scanned: int = 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def scan_plugin_directory(plugin_dir: Path) -> SecurityScanResult:
    """
    扫描插件目录中的所有 Python 文件。

    Returns:
        SecurityScanResult 包含所有发现的安全警告
    """
    result = SecurityScanResult()
    backend_dir = plugin_dir / "backend"

    if not backend_dir.is_dir():
        return result

    for py_file in backend_dir.rglob("*.py"):
        if py_file.name.startswith("__"):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            relative = py_file.relative_to(plugin_dir)
            _scan_file(source, str(relative), result)
            result.files_scanned += 1
        except Exception as exc:
            result.warnings.append(f"Failed to scan {py_file.name}: {exc}")

    return result


def _scan_file(source: str, filename: str, result: SecurityScanResult) -> None:
    """扫描单个 Python 文件"""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        result.warnings.append(f"{filename}: syntax error, cannot parse")
        return

    for node in ast.walk(tree):
        # 检查危险函数调用: eval(), exec(), etc.
        if isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name in _DANGEROUS_CALLS:
                result.warnings.append(
                    f"{filename}:{node.lineno}: dangerous call '{func_name}()'"
                )

        # 检查危险 import
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in _DANGEROUS_MODULES:
                    result.warnings.append(
                        f"{filename}:{node.lineno}: imports dangerous module '{alias.name}'"
                    )

        if isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod in _DANGEROUS_MODULES:
                    result.warnings.append(
                        f"{filename}:{node.lineno}: imports from dangerous module '{node.module}'"
                    )

        # 检查危险属性访问: os.system(), subprocess.run(), etc.
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                mod_name = node.value.id
                attr_name = node.attr
                if mod_name in _DANGEROUS_ATTRS:
                    if attr_name in _DANGEROUS_ATTRS[mod_name]:
                        result.warnings.append(
                            f"{filename}:{node.lineno}: dangerous call '{mod_name}.{attr_name}'"
                        )


def _get_call_name(node: ast.Call) -> str:
    """提取函数调用的名称"""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""
