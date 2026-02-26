"""
插件操作进度推送器

通过 Socket.IO 向操作者实时推送插件安装/卸载/启用/禁用的进度日志。
事件仅推送给执行操作的管理员（room=user:{operator_id}），不广播。

事件名: plugin:install:progress
Namespace: /admin

用法:
    emitter = PluginProgressEmitter(operator_id=5, plugin_name="novusdoc", action="install")
    await emitter.emit_step("pip", "running", "Installing bleach>=6.0.0...")
    await emitter.emit_step("pip", "success", "bleach installed")
    await emitter.emit_log("pip", "Collecting bleach>=6.0.0")  # 子进程输出行
    await emitter.emit_done()
    await emitter.emit_error("Failed to install bleach")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.plugins.progress")

# Socket.IO 事件名
EVENT_PLUGIN_PROGRESS = "plugin:install:progress"
NAMESPACE_ADMIN = "/admin"

# 安装步骤及其权重（pip/npm 延迟到 enable 阶段，install 不安装依赖）
INSTALL_STEPS = [
    ("copy", 15),
    ("alembic", 30),
    ("ai_features", 10),
    ("on_install", 15),
    ("db", 15),
    ("done", 0),
]

ENABLE_STEPS = [
    ("pip", 30),
    ("npm", 30),
    ("extensions", 15),
    ("on_enable", 10),
    ("done", 0),
]

UNINSTALL_STEPS = [
    ("disable", 5),
    ("on_uninstall", 5),
    ("cleanup_extensions", 5),
    ("cleanup_skills", 5),
    ("cleanup_ai_features", 5),
    ("cleanup_db", 15),
    ("cleanup_pip", 15),
    ("cleanup_npm", 15),
    ("cleanup_records", 5),
    ("cleanup_files", 5),
    ("done", 0),
]


def _calc_progress(steps_config: list[tuple[str, int]], current_step: str, status: str) -> int:
    """根据当前步骤和状态计算总进度百分比（0-100）"""
    total_weight = sum(w for _, w in steps_config)
    if total_weight == 0:
        return 0

    accumulated = 0
    for step_name, weight in steps_config:
        if step_name == current_step:
            if status == "success":
                accumulated += weight
            elif status == "running":
                accumulated += weight // 2
            break
        accumulated += weight

    return min(100, int(accumulated / total_weight * 100))


class PluginProgressEmitter:
    """插件操作进度推送器

    Args:
        operator_id: 执行操作的管理员 ID（为 None 时不推送）
        plugin_name: 插件名称
        action: 操作类型 (install | uninstall | enable | disable)
    """

    def __init__(
        self,
        operator_id: int | None,
        plugin_name: str,
        action: str,
    ) -> None:
        self._operator_id = operator_id
        self._plugin_name = plugin_name
        self._action = action
        self._steps_config = (
            INSTALL_STEPS if action == "install" else
            ENABLE_STEPS if action == "enable" else
            UNINSTALL_STEPS if action == "uninstall" else
            []
        )

    @property
    def active(self) -> bool:
        """是否激活推送（operator_id 为 None 时不推送）"""
        return self._operator_id is not None

    async def emit_step(
        self,
        step: str,
        status: str,
        message: str = "",
    ) -> None:
        """推送步骤进度

        Args:
            step: 步骤名 (copy/pip/npm/alembic/ai_features/on_install/db/done/error 等)
            status: 状态 (running/success/error)
            message: 描述信息
        """
        if not self.active:
            return

        progress = _calc_progress(self._steps_config, step, status)

        await self._emit({
            "plugin_name": self._plugin_name,
            "action": self._action,
            "step": step,
            "status": status,
            "message": message,
            "progress": progress,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_log(self, step: str, line: str) -> None:
        """推送子进程输出日志行（pip/pnpm/alembic 的 stdout/stderr）

        Args:
            step: 当前步骤名
            line: 日志行内容
        """
        if not self.active:
            return

        await self._emit({
            "plugin_name": self._plugin_name,
            "action": self._action,
            "step": step,
            "status": "log",
            "message": line.rstrip(),
            "progress": _calc_progress(self._steps_config, step, "running"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_done(self, message: str = "") -> None:
        """推送操作完成"""
        await self.emit_step("done", "success", message or f"{self._action} completed")

    async def emit_error(self, message: str) -> None:
        """推送操作失败"""
        await self.emit_step("error", "error", message)

    async def _emit(self, data: dict[str, Any]) -> None:
        """发送 Socket.IO 事件到操作者的 room"""
        if not self._operator_id:
            return

        try:
            from app.core.socketio_server import sio
            await sio.emit(
                EVENT_PLUGIN_PROGRESS,
                data,
                room=f"user:{self._operator_id}",
                namespace=NAMESPACE_ADMIN,
            )
        except Exception as exc:
            logger.warning(
                "Failed to emit plugin progress for %s: %s",
                self._plugin_name, exc,
            )
