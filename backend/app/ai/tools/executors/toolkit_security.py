"""
Toolkit security policy helpers. / Toolkit 安全策略支持。
"""

from __future__ import annotations

import ast

# permissive: only block the most dangerous modules (suitable for trusted environments)
# permissive: 仅禁止最危险的模块（适合可信环境）
_BLOCKED_MODULES_PERMISSIVE: frozenset[str] = frozenset(
    {
        "os",
        "subprocess",
        "ctypes",
        "builtins",
        "__builtin__",
    }
)

# normal (default): block system/process/file/deserialization modules, allow network libs
# normal (默认): 禁止系统/进程/文件/反序列化模块，允许网络库
_BLOCKED_MODULES_NORMAL: frozenset[str] = frozenset(
    {
        # Process / OS / 进程 / OS
        "os",
        "subprocess",
        "shutil",
        "signal",
        "multiprocessing",
        "threading",
        # System internals / 系统内部
        "sys",
        "ctypes",
        "importlib",
        # Deserialization attacks / 反序列化攻击
        "pickle",
        "marshal",
        # Database / 数据库
        "sqlite3",
        # Raw network / 原始网络
        "socket",
        # Filesystem / 文件系统
        "pathlib",
        "io",
        "tempfile",
        "glob",
        "fnmatch",
        # Code generation / 代码生成
        "code",
        "codeop",
        "compileall",
        "py_compile",
        # Miscellaneous / 杂项
        "webbrowser",
        "antigravity",
        "builtins",
        "__builtin__",
    }
)

# strict: only allow safe computation/data processing modules
# strict: 仅允许安全的计算/数据处理模块
_BLOCKED_MODULES_STRICT: frozenset[str] = _BLOCKED_MODULES_NORMAL | frozenset(
    {
        # Network / 网络
        "requests",
        "httpx",
        "urllib",
        "urllib3",
        "aiohttp",
        "http",
        "xmlrpc",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        # External processes / 外部进程
        "asyncio",
        # Serialization / 序列化
        "shelve",
        "dbm",
        # Debugging / 调试
        "pdb",
        "traceback",
        "dis",
        "inspect",
    }
)

_SECURITY_LEVEL_MAP: dict[str, frozenset[str]] = {
    "strict": _BLOCKED_MODULES_STRICT,
    "normal": _BLOCKED_MODULES_NORMAL,
    "permissive": _BLOCKED_MODULES_PERMISSIVE,
}

_BLOCKED_MODULE_PREFIXES: tuple[str, ...] = (
    "app.",  # Application internal modules / 应用内部模块
    "config.",  # Configuration modules / 配置模块
)

_BLOCKED_BUILTINS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "breakpoint",
        "exit",
        "quit",
    }
)


def get_blocked_modules(security_level: str | None = None) -> frozenset[str]:
    """Return the set of blocked modules based on security level. / 根据安全等级返回被阻止的模块集合。"""
    if security_level is None:
        security_level = "normal"
    return _SECURITY_LEVEL_MAP.get(security_level, _BLOCKED_MODULES_NORMAL)


def scan_toolkit_security(
    source: str,
    security_level: str | None = None,
) -> list[str]:
    """
    AST static analysis: detect dangerous imports and builtin function calls in Toolkit source code.
    AST 静态分析：检测 Toolkit 源码中的危险 import 和内置函数调用。

    Args:
        source: Toolkit Python source code / Toolkit Python 源码
        security_level: Security level (strict/normal/permissive), None uses normal
                        安全等级 (strict/normal/permissive)，None 使用 normal

    Returns:
        List of violation descriptions (empty list means safe).
        违规描述列表（空列表表示安全）。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"Syntax error at line {exc.lineno}: {exc.msg}"]

    blocked_modules = get_blocked_modules(security_level)
    violations: list[str] = []

    for node in ast.walk(tree):
        # Check import xxx / 检查 import xxx
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module(alias.name, node.lineno, violations, blocked_modules)

        # Check from xxx import yyy / 检查 from xxx import yyy
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _check_module(node.module, node.lineno, violations, blocked_modules)

        # Check dangerous builtin function calls: eval(), exec(), open(), etc.
        # 检查危险内置函数调用：eval(), exec(), open() 等
        elif isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name and func_name in _BLOCKED_BUILTINS:
                violations.append(
                    f"Blocked builtin '{func_name}()' at line {node.lineno}"
                )

    return violations


def _check_module(
    module_name: str,
    lineno: int,
    violations: list[str],
    blocked_modules: frozenset[str],
) -> None:
    """Check if module name is in the blacklist / 检查模块名是否在黑名单中"""
    top_level = module_name.split(".")[0]
    if top_level in blocked_modules:
        violations.append(f"Blocked import '{module_name}' at line {lineno}")
        return

    for prefix in _BLOCKED_MODULE_PREFIXES:
        if module_name.startswith(prefix):
            violations.append(f"Blocked import '{module_name}' at line {lineno}")
            return


def _get_call_name(node: ast.Call) -> str | None:
    """Extract function name from AST Call node / 从 AST Call 节点中提取函数名"""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


__all__ = ["get_blocked_modules", "scan_toolkit_security"]
