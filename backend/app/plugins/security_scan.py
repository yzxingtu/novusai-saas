"""
Plugin security scan (basic version).
/ 插件安全扫描（基础版）

Scans plugin Python code for dangerous calls.
/ 扫描插件 Python 代码中的危险调用。

Behavior:
- Install preview: results included as warnings in preview info
- Actual install / upgrade: fail-close, if has_warnings=True then lifecycle raises
  PluginSecurityError to block installation
/ 行为说明：预览时作为 warning，实际安装时 fail-close。
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import resolve_public_error_message
from app.plugins.exceptions import PluginSecurityError

logger = get_logger(__name__)

# Dangerous function calls / 危险函数调用
_DANGEROUS_CALLS: set[str] = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "breakpoint",
    "exit",
    "quit",
}

# Dangerous modules / 危险模块
# Note: only modules that can actually enable system intrusion are listed.
# Common modules like sys/io/pathlib/tempfile/gc are widely used in legitimate plugin code and not blacklisted.
# / 注：只列入能实际实现系统入侵的模块。
_DANGEROUS_MODULES: set[str] = {
    "subprocess",
    "os",
    "shutil",
    "ctypes",
    "pickle",
    "marshal",
    "socket",
    "multiprocessing",
    "threading",
    # importlib can bypass import blacklist to dynamically load dangerous modules
    # / importlib 能绕过 import 黑名单动态加载危险模块
    "importlib",
    # builtins can override built-in functions to implement inequality attacks
    # / builtins 可覆盖内置函数实现不等式攻击
    "builtins",
    # signal can interfere with process signal handling and OS behavior
    # / signal 可干扰进程信号处理和操作系统行为
    "signal",
}

# importlib safe submodule whitelist / importlib 的安全子模块白名单
# importlib.util      — Load modules by file path (legitimate use when plugin dir contains hyphens)
# importlib.metadata  — Read-only package metadata, no security risk
# importlib.abc       — Abstract base classes, no execution capability
# importlib.resources — Read-only resource file access
# importlib.machinery — Finder/loader interfaces, cannot directly import_module
_IMPORTLIB_SAFE_SUBMODULES: frozenset[str] = frozenset(
    {
        "importlib.util",
        "importlib.metadata",
        "importlib.abc",
        "importlib.resources",
        "importlib.machinery",
    }
)

# Dangerous attribute access / 危险属性访问
_DANGEROUS_ATTRS: dict[str, set[str]] = {
    "os": {
        "system",
        "popen",
        "remove",
        "rmdir",
        "unlink",
        "rename",
        "chmod",
        "chown",
        "listdir",
        "walk",
        "environ",
    },
    "shutil": {"rmtree", "move", "copy", "copytree"},
    "subprocess": {"run", "Popen", "call", "check_output", "check_call"},
}


class SecurityScanResult:
    """Security scan result / 安全扫描结果"""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.files_scanned: int = 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def scan_plugin_directory(plugin_dir: Path) -> SecurityScanResult:
    """
    Scan all Python files in the plugin directory.
    / 扫描插件目录中的所有 Python 文件。

    Returns:
        SecurityScanResult containing all discovered security warnings
        / SecurityScanResult 包含所有发现的安全警告
    """
    result = SecurityScanResult()
    backend_dir = plugin_dir / "backend"

    if not backend_dir.is_dir():
        return result

    for py_file in backend_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        # Exclude tests/ directory: test code legitimately uses importlib/sys etc. for dynamic import testing
        # / 排除 tests/ 目录
        if "tests" in py_file.parts:
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            relative = py_file.relative_to(plugin_dir)
            _scan_file(source, str(relative), result)
            result.files_scanned += 1
        except Exception as exc:
            result.warnings.append(
                _(
                    "plugin.preview.security.scan_failed_file",
                    file=py_file.name,
                    error=resolve_public_error_message(
                        exc,
                        fallback_message=_(
                            "plugin.preview.security.scan_failed_generic"
                        ),
                    ),
                )
            )

    return result


def assert_plugin_security_clean(
    plugin_dir: Path,
    *,
    plugin_name: str,
    action: str,
) -> SecurityScanResult:
    """Fail-close security assertion for plugin runtime entry points. / 插件运行时入口统一安全断言。"""
    try:
        result = scan_plugin_directory(plugin_dir)
    except Exception as exc:
        raise PluginSecurityError(
            message=_(
                "plugin.preview.security.scan_failed_action",
                plugin_name=plugin_name,
                action=action,
                error=resolve_public_error_message(
                    exc,
                    fallback_message=_("plugin.preview.security.scan_failed_generic"),
                ),
            ),
        ) from exc

    if result.has_warnings:
        top_warnings = "; ".join(result.warnings[:5])
        raise PluginSecurityError(
            message=_(
                "plugin.preview.security.blocked",
                plugin_name=plugin_name,
                warnings=top_warnings,
            ),
        )

    return result


def _scan_file(source: str, filename: str, result: SecurityScanResult) -> None:
    """Scan a single Python file / 扫描单个 Python 文件"""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        result.warnings.append(_("plugin.preview.security.syntax_error", file=filename))
        return

    for node in ast.walk(tree):
        # Check dangerous function calls: eval(), exec(), etc. / 检查危险函数调用
        if isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name in _DANGEROUS_CALLS:
                result.warnings.append(
                    _(
                        "plugin.preview.security.dangerous_call",
                        file=filename,
                        line=node.lineno,
                        call=f"{func_name}()",
                    )
                )

        # Check dangerous imports / 检查危险 import
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_mod = alias.name.split(".")[0]
                if top_mod in _DANGEROUS_MODULES:
                    # Whitelist: importlib safe submodules don't trigger warnings
                    # / 白名单
                    if alias.name in _IMPORTLIB_SAFE_SUBMODULES:
                        continue
                    result.warnings.append(
                        _(
                            "plugin.preview.security.dangerous_import",
                            file=filename,
                            line=node.lineno,
                            module=alias.name,
                        )
                    )

        if isinstance(node, ast.ImportFrom) and node.module:
            top_mod = node.module.split(".")[0]
            if top_mod in _DANGEROUS_MODULES:
                # 白名单：importlib 的安全子模块不触发警告
                if node.module in _IMPORTLIB_SAFE_SUBMODULES:
                    continue
                result.warnings.append(
                    _(
                        "plugin.preview.security.dangerous_import_from",
                        file=filename,
                        line=node.lineno,
                        module=node.module,
                    )
                )

        # Check dangerous attribute access: os.system(), subprocess.run(), etc.
        # / 检查危险属性访问
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            mod_name = node.value.id
            attr_name = node.attr
            if mod_name in _DANGEROUS_ATTRS and attr_name in _DANGEROUS_ATTRS[mod_name]:
                result.warnings.append(
                    _(
                        "plugin.preview.security.dangerous_attribute",
                        file=filename,
                        line=node.lineno,
                        call=f"{mod_name}.{attr_name}",
                    )
                )


def _get_call_name(node: ast.Call) -> str:
    """Extract function call name / 提取函数调用的名称"""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""
