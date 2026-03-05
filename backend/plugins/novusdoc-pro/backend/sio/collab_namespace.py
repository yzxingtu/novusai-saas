"""
NovusDoc Pro 协作 Socket.IO Namespace

处理 Yjs 实时同步事件：
- join_doc: 加入文档协作房间
- leave_doc: 离开文档协作房间
- yjs_update: 转发 Yjs 更新到同文档的其他客户端
- awareness_update: 转发用户光标/选区/在线状态

Namespace 路径: /plugin/novusdoc-pro/collab
Auth: 由 PluginAuthNamespaceWrapper 自动处理 JWT 验证

安全规则：
- tenant_id/user_id 必须从 SIO session 获取（JWT 鉴权写入），不信任客户端 payload
- doc_id 由客户端指定（房间标识），但 room key 由服务端用 session.tenant_id 构造
- enter_room/leave_room 必须 await（AsyncNamespace 规范）
"""

from __future__ import annotations

import socketio

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc-pro.collab")


PLATFORM_TENANT_ID = 0


async def _get_session_tenant_id(ns: socketio.AsyncNamespace, sid: str) -> int | None:
    """从 SIO session 获取可信 tenant_id（由 PluginAuthNamespaceWrapper 鉴权写入）

    - tenant_admin: 返回真实 tenant_id
    - admin: session 中 tenant_id 为 None，回退到 PLATFORM_TENANT_ID (0)
    """
    try:
        session = await ns.get_session(sid)
        if not session:
            return None
        tid = session.get("tenant_id")
        if tid is not None:
            return int(tid)
        # admin 用户没有 tenant_id，使用平台命名空间
        user_type = session.get("user_type", "")
        if user_type == "admin":
            return PLATFORM_TENANT_ID
        return None
    except Exception:
        return None


class CollabNamespace(socketio.AsyncNamespace):
    """协作实时同步 Namespace"""

    async def on_join_doc(self, sid: str, data: dict) -> None:
        """客户端加入文档协作"""
        doc_id = data.get("doc_id")
        if not doc_id:
            await self.emit("error", {"message": "doc_id required"}, to=sid)
            return

        # 从 session 获取可信 tenant_id（不信任客户端）
        tenant_id = await _get_session_tenant_id(self, sid)
        if tenant_id is None:
            await self.emit("error", {"message": "authentication required"}, to=sid)
            return

        # License 门控：协作连接需要有效 Pro license
        try:
            from app.core.database import async_session_factory
            async with async_session_factory() as db:
                from ..services.license_gate import check_license_valid
                is_valid, license_info = await check_license_valid(db)
                if not is_valid:
                    await self.emit("error", {
                        "message": "NovusDoc Pro license required for collaboration",
                        "code": 4031,
                        "license_status": license_info.get("status", "invalid"),
                    }, to=sid)
                    return
        except Exception as exc:
            logger.error("collab: license check failed for sid=%s: %s", sid, exc)

        room = f"doc:{tenant_id}:{doc_id}"
        await self.enter_room(sid, room)

        from ..services.yjs_provider import YjsProviderManager
        manager = YjsProviderManager.get_instance()
        provider = manager.get_or_create(tenant_id, int(doc_id))
        provider.add_connection(sid)

        state = await provider.load_state()
        if state:
            await self.emit("yjs_sync_step1", {"state": state.hex()}, to=sid)

        session = await self.get_session(sid)
        user_info = {
            "user_id": session.get("user_id") if session else None,
            "username": session.get("username") if session else None,
        }
        await self.emit(
            "user_joined",
            {"sid": sid, "user": user_info, "count": provider.connection_count},
            room=room,
            skip_sid=sid,
        )

        logger.info(
            "collab: sid=%s joined doc=%s tenant=%s (now %d users)",
            sid, doc_id, tenant_id, provider.connection_count,
        )

    async def on_leave_doc(self, sid: str, data: dict) -> None:
        """客户端离开文档协作"""
        doc_id = data.get("doc_id")
        if not doc_id:
            return

        tenant_id = await _get_session_tenant_id(self, sid)
        if tenant_id is None:
            return

        room = f"doc:{tenant_id}:{doc_id}"
        await self.leave_room(sid, room)

        from ..services.yjs_provider import YjsProviderManager
        manager = YjsProviderManager.get_instance()
        provider = manager.get_or_create(tenant_id, int(doc_id))
        provider.remove_connection(sid)

        await self.emit(
            "user_left",
            {"sid": sid, "count": provider.connection_count},
            room=room,
            skip_sid=sid,
        )

        manager.remove_if_empty(tenant_id, int(doc_id))
        logger.info("collab: sid=%s left doc=%s tenant=%s", sid, doc_id, tenant_id)

    async def on_yjs_update(self, sid: str, data: dict) -> None:
        """转发 Yjs 更新（二进制 update 编码为 hex）"""
        doc_id = data.get("doc_id")
        update_hex = data.get("update")
        if not doc_id or not update_hex:
            return

        tenant_id = await _get_session_tenant_id(self, sid)
        if tenant_id is None:
            return

        room = f"doc:{tenant_id}:{doc_id}"

        try:
            update_bytes = bytes.fromhex(update_hex)
            from ..services.yjs_provider import YjsProviderManager
            provider = YjsProviderManager.get_instance().get_or_create(tenant_id, int(doc_id))
            await provider.apply_update(update_bytes)
        except Exception as exc:
            logger.error("collab: failed to apply yjs update: %s", exc)

        await self.emit("yjs_update", {"update": update_hex}, room=room, skip_sid=sid)

    async def on_awareness_update(self, sid: str, data: dict) -> None:
        """转发 awareness（光标位置/用户状态）"""
        doc_id = data.get("doc_id")
        if not doc_id:
            return

        tenant_id = await _get_session_tenant_id(self, sid)
        if tenant_id is None:
            return

        room = f"doc:{tenant_id}:{doc_id}"
        await self.emit("awareness_update", data, room=room, skip_sid=sid)

    async def on_disconnect(self, sid: str, reason: str = "") -> None:
        """客户端断开连接 — 清理所有房间"""
        _ = reason
        from ..services.yjs_provider import YjsProviderManager
        manager = YjsProviderManager.get_instance()

        for key, provider in manager.iter_providers():
            if provider.has_connection(sid):
                provider.remove_connection(sid)
                tenant_id, doc_id = key.split(":")
                room = f"doc:{tenant_id}:{doc_id}"
                await self.emit(
                    "user_left",
                    {"sid": sid, "count": provider.connection_count},
                    room=room,
                )
                if provider.is_empty:
                    manager.remove_if_empty(int(tenant_id), int(doc_id))

        logger.info("collab: sid=%s disconnected", sid)
