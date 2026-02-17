"""
插件工具函数

负责插件文件目录清理和 Python 依赖安装。
从 PluginManager 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException

logger = LogManager.get_logger("app")

_PLUGINS_BASE_PREFIX = "app.plugins."


def cleanup_plugin_directory(plugin_name: str, entry_point: str) -> None:
    """卸载后清理插件文件目录

    仅处理通过 .nap 上传安装的插件（entry_point 以 ``app.plugins.`` 开头）。
    外部 entry_point 安装的插件不删除文件。删除失败不阻塞卸载流程。

    Args:
        plugin_name: 插件名称
        entry_point: 插件入口点路径
    """
    if not entry_point.startswith(_PLUGINS_BASE_PREFIX):
        logger.debug(
            "Skipping directory cleanup for external plugin: %s (entry_point=%s)",
            plugin_name, entry_point,
        )
        return

    import shutil
    from pathlib import Path

    plugins_base = Path(__file__).resolve().parent.parent / "plugins"
    plugin_dir = plugins_base / plugin_name

    if not plugin_dir.exists():
        logger.debug(
            "Plugin directory does not exist, nothing to clean: %s",
            plugin_dir,
        )
        return

    try:
        shutil.rmtree(plugin_dir)
        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="cleanup_directory",
            plugin_name=plugin_name,
            details={"directory": str(plugin_dir), "status": "deleted"},
        )
        logger.info(
            "Plugin directory cleaned up: %s", plugin_dir,
        )
    except Exception as exc:
        logger.warning(
            "Failed to delete plugin directory %s: %s — "
            "manual cleanup may be required",
            plugin_dir, exc, exc_info=True,
        )


def install_plugin_requirements(plugin_name: str) -> list[str]:
    """安装插件 Python 依赖（带安全限制）

    检测 ``app/plugins/{name}/requirements.txt``，若存在则：
    1. 校验所有包名是否在白名单中
    2. 使用 ``--no-deps --only-binary :all:`` 安全参数
    3. 非白名单包拒绝并提示管理员

    Args:
        plugin_name: 插件名称

    Returns:
        安装的依赖列表（来自 requirements.txt 的行）

    Raises:
        BusinessException: 包不在白名单中或 pip install 失败
    """
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    plugins_base = Path(__file__).resolve().parent.parent / "plugins"
    req_file = plugins_base / plugin_name / "requirements.txt"

    if not req_file.exists():
        return []

    deps = [
        line.strip()
        for line in req_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not deps:
        return []

    # 白名单校验
    from app.plugins.security import validate_requirements
    allowed, rejected = validate_requirements(deps)

    if rejected:
        logger.warning(
            "Plugin %s has non-whitelisted packages: %s",
            plugin_name, rejected,
        )
        raise BusinessException(
            _("plugin.packages_not_whitelisted").format(
                packages=", ".join(sorted(rejected)),
            )
        )

    if not allowed:
        return []

    logger.info(
        "Installing plugin dependencies: %s (%d packages)",
        plugin_name, len(allowed),
    )

    # 写入临时 requirements 文件（仅包含白名单内的包）
    tmp_req = Path(tempfile.mktemp(suffix=".txt", prefix="plugin_req_"))
    try:
        tmp_req.write_text("\n".join(allowed), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "-r", str(tmp_req),
                "--no-deps",
                "--only-binary", ":all:",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        if result.returncode != 0:
            # --only-binary 可能失败（无预编译包），回退允许源码构建
            logger.warning(
                "pip install with --only-binary failed for %s, retrying without",
                plugin_name,
            )
            result = subprocess.run(
                [
                    sys.executable, "-m", "pip", "install",
                    "-r", str(tmp_req),
                    "--no-deps",
                ],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

        if result.returncode != 0:
            logger.error(
                "pip install failed for plugin %s:\nstdout: %s\nstderr: %s",
                plugin_name, result.stdout, result.stderr,
            )
            raise BusinessException(
                _("plugin.dependency_install_failed")
            )
    except subprocess.TimeoutExpired:
        raise BusinessException(
            _("plugin.dependency_install_timeout")
        )
    finally:
        tmp_req.unlink(missing_ok=True)

    from app.plugins.security import log_plugin_action
    log_plugin_action(
        action="install_dependencies",
        plugin_name=plugin_name,
        details={"dependencies": allowed},
    )

    logger.info(
        "Plugin dependencies installed: %s — %s",
        plugin_name, allowed,
    )
    return allowed


__all__ = ["cleanup_plugin_directory", "install_plugin_requirements"]
