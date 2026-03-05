"""
插件安全扫描（基础版）

扫描插件 Python 代码中的危险调用。

行为说明：
- 安装预览（preview）：结果作为 warning 包含在预览信息中
- 实际安装 / 升级：fail-close，若 has_warnings=True 则 lifecycle 抛出
  PluginSecurityError 阻止安装
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

# 危险函数调用
_DANGEROUS_CALLS: set[str] = {
    "eval", "exec", "compile", "__import__",
    "breakpoint", "exit", "quit",
}

# 危险模块
# 注：只列入能实际实现系统入侵的模块。
# sys/io/pathlib/tempfile/gc 等通用模块在合法插件代码中被广泛使用，不列入黑名单。
_DANGEROUS_MODULES: set[str] = {
    "subprocess", "os", "shutil", "ctypes",
    "pickle", "marshal", "socket",
    "multiprocessing", "threading",
    # importlib 能绕过 import 黑名单动态加载危险模块
    "importlib",
    # builtins 可覆盖内置函数实现不等式攻击
    "builtins",
    # signal 可干乐进程信号处理和操作系统行为
    "signal",
}

# importlib 的安全子模块白名单
# importlib.util      — 按文件路径加载模块（插件目录含连字符时的合法用法）
# importlib.metadata  — 只读包元数据，无安全风险
# importlib.abc       — 抽象基类，无执行能力
# importlib.resources — 只读资源文件访问
# importlib.machinery — 查找器/加载器接口，不能直接 import_module
_IMPORTLIB_SAFE_SUBMODULES: frozenset[str] = frozenset({
    "importlib.util",
    "importlib.metadata",
    "importlib.abc",
    "importlib.resources",
    "importlib.machinery",
})

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
        if "__pycache__" in py_file.parts:
            continue
        # 排除 tests/ 目录：测试代码合法使用 importlib/sys 等进行动态导入测试
        if "tests" in py_file.parts:
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
                top_mod = alias.name.split(".")[0]
                if top_mod in _DANGEROUS_MODULES:
                    # 白名单：importlib 的安全子模块不触发警告
                    if alias.name in _IMPORTLIB_SAFE_SUBMODULES:
                        continue
                    result.warnings.append(
                        f"{filename}:{node.lineno}: imports dangerous module '{alias.name}'"
                    )

        if isinstance(node, ast.ImportFrom) and node.module:
            top_mod = node.module.split(".")[0]
            if top_mod in _DANGEROUS_MODULES:
                # 白名单：importlib 的安全子模块不触发警告
                if node.module in _IMPORTLIB_SAFE_SUBMODULES:
                    continue
                result.warnings.append(
                    f"{filename}:{node.lineno}: imports from dangerous module '{node.module}'"
                )

        # 检查危险属性访问: os.system(), subprocess.run(), etc.
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            mod_name = node.value.id
            attr_name = node.attr
            if mod_name in _DANGEROUS_ATTRS and attr_name in _DANGEROUS_ATTRS[mod_name]:
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
