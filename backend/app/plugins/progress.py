"""
Plugin operation progress emitter.
/ 插件操作进度推送器

Pushes real-time progress logs for plugin install/uninstall/enable/disable to the operator via Socket.IO.
Events are only sent to the admin performing the operation (room=user:{operator_id}), not broadcast.
/ 通过 Socket.IO 向操作者实时推送进度日志。事件仅推送给执行操作的管理员。

Event name: plugin:install:progress
Namespace: /admin

Usage / 用法:
    emitter = PluginProgressEmitter(operator_id=5, plugin_name="novusdoc", action="install")
    await emitter.emit_step("pip", "running", "Installing bleach>=6.0.0...")
    await emitter.emit_step("pip", "success", "bleach installed")
    await emitter.emit_log("pip", "Collecting bleach>=6.0.0")  # subprocess output line / 子进程输出行
    await emitter.emit_done()
    await emitter.emit_error("Failed to install bleach")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.plugins.progress")

# Socket.IO event name / 事件名
EVENT_PLUGIN_PROGRESS = "plugin:install:progress"
NAMESPACE_ADMIN = "/admin"

# Install steps and their weights (install phase does not modify runtime dependencies)
# / 安装步骤及其权重（install 阶段不修改运行时依赖）
INSTALL_STEPS = [
    ("copy", 15),
    ("alembic", 30),
    ("ai_features", 10),
    ("on_install", 15),
    ("db", 15),
    ("done", 0),
]

ENABLE_STEPS = [
    ("alembic", 10),
    ("pip", 30),
    ("extensions", 25),
    ("on_enable", 15),
    ("done", 0),
]

DISABLE_STEPS = [
    ("extensions", 30),
    ("skills", 15),
    ("on_disable", 20),
    ("tasks", 10),
    ("permissions", 15),
    ("done", 0),
]

UNINSTALL_STEPS = [
    ("disable", 5),
    ("on_uninstall", 5),
    ("cleanup_extensions", 5),
    ("cleanup_skills", 5),
    ("cleanup_ai_features", 5),
    ("cleanup_db", 15),
    ("cleanup_pip", 20),
    ("cleanup_records", 5),
    ("cleanup_files", 5),
    ("done", 0),
]


def _calc_progress(
    steps_config: list[tuple[str, int]], current_step: str, status: str
) -> int:
    """Calculate overall progress percentage (0-100) based on current step and status / 根据当前步骤和状态计算总进度百分比"""
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
    """Plugin operation progress emitter / 插件操作进度推送器

    Args:
        operator_id: Admin ID performing the operation (None = no push) / 执行操作的管理员 ID
        plugin_name: Plugin name / 插件名称
        action: Operation type (install | uninstall | enable | disable) / 操作类型
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
            INSTALL_STEPS
            if action == "install"
            else ENABLE_STEPS
            if action == "enable"
            else UNINSTALL_STEPS
            if action == "uninstall"
            else DISABLE_STEPS
            if action == "disable"
            else []
        )

    @property
    def active(self) -> bool:
        """Whether push is active (no push when operator_id is None) / 是否激活推送"""
        return self._operator_id is not None

    async def emit_step(
        self,
        step: str,
        status: str,
        message: str = "",
    ) -> None:
        """Push step progress / 推送步骤进度

        Args:
            step: Step name (copy/pip/alembic/ai_features/on_install/db/done/error etc.) / 步骤名
            status: Status (running/success/error) / 状态
            message: Description / 描述信息
        """
        if not self.active:
            return

        progress = _calc_progress(self._steps_config, step, status)

        await self._emit(
            {
                "plugin_name": self._plugin_name,
                "action": self._action,
                "step": step,
                "status": status,
                "message": message,
                "progress": progress,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def emit_log(self, step: str, line: str) -> None:
        """Push subprocess output log line (pip/alembic stdout/stderr)
        / 推送子进程输出日志行

        Args:
            step: Current step name / 当前步骤名
            line: Log line content / 日志行内容
        """
        if not self.active:
            return

        await self._emit(
            {
                "plugin_name": self._plugin_name,
                "action": self._action,
                "step": step,
                "status": "log",
                "message": line.rstrip(),
                "progress": _calc_progress(self._steps_config, step, "running"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def emit_done(self, message: str = "") -> None:
        """Push operation completed / 推送操作完成"""
        await self.emit_step("done", "success", message or f"{self._action} completed")

    async def emit_error(self, message: str) -> None:
        """Push operation failed / 推送操作失败"""
        await self.emit_step("error", "error", message)

    async def _emit(self, data: dict[str, Any]) -> None:
        """Send Socket.IO event to the operator's room.
        / 发送 Socket.IO 事件到操作者的 room。

        Uses asyncio.wait_for with 1s timeout to prevent sio.emit() from blocking
        indefinitely when Redis connection is slow/unreachable.
        / 使用 asyncio.wait_for 设置 1 秒超时，防止流程挂死。
        """
        if not self._operator_id:
            return

        import asyncio

        room = f"user:{self._operator_id}"
        step = data.get("step")
        logger.debug(
            "Emitting plugin_progress for {} step={} status={} room={}",
            self._plugin_name,
            step,
            data.get("status"),
            room,
        )
        try:
            from app.core.socketio_server import sio

            await asyncio.wait_for(
                sio.emit(
                    EVENT_PLUGIN_PROGRESS,
                    data,
                    room=room,
                    namespace=NAMESPACE_ADMIN,
                ),
                timeout=1.0,
            )
            logger.debug(
                "Emitted plugin_progress for {} step={} OK", self._plugin_name, step
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout emitting plugin progress for {} (step={}) — "
                "Redis pub/sub may be unavailable; SIO events lost but enable continues",
                self._plugin_name,
                step,
            )
        except Exception as exc:
            logger.error(
                "Failed to emit plugin progress for {} (step={}): {}",
                self._plugin_name,
                step,
                exc,
            )
