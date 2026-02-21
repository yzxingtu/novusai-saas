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


def backup_plugin_directory(plugin_name: str, plugin_version: str, entry_point: str) -> str | None:
    """卸载前自动备份插件目录为 .nap 文件

    仅处理通过 .nap 上传安装的插件（entry_point 以 ``app.plugins.`` 开头）。
    备份存储在 ``plugins/_backups/`` 目录下，每个插件最多保留 3 个备份。
    失败不阻塞卸载流程。

    Args:
        plugin_name: 插件名称
        plugin_version: 插件版本号
        entry_point: 插件入口点路径

    Returns:
        备份文件路径（成功时），或 None（跳过/失败时）
    """
    if not entry_point.startswith(_PLUGINS_BASE_PREFIX):
        return None

    from pathlib import Path
    from app.core.base_model import utc_now

    plugins_base = Path(__file__).resolve().parent
    module_name = plugin_name.replace("-", "_")
    plugin_dir = plugins_base / module_name
    if not plugin_dir.exists():
        plugin_dir = plugins_base / plugin_name
    if not plugin_dir.exists():
        plugin_dir = plugins_base / "builtin" / module_name
    if not plugin_dir.exists():
        logger.debug("Plugin directory not found for backup: %s", plugin_name)
        return None

    backups_dir = plugins_base / "_backups"
    backups_dir.mkdir(exist_ok=True)

    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    nap_filename = f"{plugin_name}-{plugin_version}-{timestamp}.nap"
    nap_path = backups_dir / nap_filename

    try:
        from app.plugins.packaging import pack_plugin
        pack_plugin(plugin_dir, nap_path)

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="backup",
            plugin_name=plugin_name,
            details={
                "version": plugin_version,
                "backup_path": str(nap_path),
            },
        )
        logger.info("Plugin backed up before uninstall: %s -> %s", plugin_name, nap_path)

        # 清理旧备份：每个插件最多保留 3 个
        _cleanup_old_backups(backups_dir, plugin_name, max_keep=3)

        return str(nap_path)
    except Exception as exc:
        logger.warning(
            "Failed to backup plugin %s before uninstall: %s — proceeding with uninstall",
            plugin_name, str(exc),
        )
        return None


def _cleanup_old_backups(backups_dir, plugin_name: str, max_keep: int = 3) -> None:
    """清理旧备份，每个插件最多保留 max_keep 个"""
    from pathlib import Path

    prefix = f"{plugin_name}-"
    backups = sorted(
        [f for f in backups_dir.iterdir() if f.name.startswith(prefix) and f.suffix == ".nap"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[max_keep:]:
        try:
            old_backup.unlink()
            logger.debug("Removed old plugin backup: %s", old_backup.name)
        except Exception:
            pass


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

    # 检查是否有 pip 安装的依赖（提醒管理员可能需要手动清理）
    req_file = plugin_dir / "requirements.txt"
    if req_file.exists():
        try:
            deps = [
                line.strip()
                for line in req_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            if deps:
                logger.warning(
                    "Plugin %s had pip dependencies installed: %s — "
                    "these packages remain in the Python environment and may need manual cleanup",
                    plugin_name, deps,
                )
        except Exception:
            pass

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
