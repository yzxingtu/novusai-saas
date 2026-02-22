"""
Socket.IO /collaboration 命名空间

富文本编辑器实时协作命名空间。
处理文档房间管理、Y.js 二进制更新转发、光标感知同步。
复用现有 JWT 认证逻辑，支持 tenant_admin scope。
"""

import base64

import socketio

from app.core.logging import LogManager
from app.core.security import (
    TOKEN_SCOPE_TENANT_ADMIN,
    TokenExpiredError,
    verify_token_with_scope,
)

logger = LogManager.get_logger("app")


class CollaborationNamespace(socketio.AsyncNamespace):
    """
    /collaboration 命名空间 — 富文本编辑器实时协作

    房间：
    - doc:{document_id} — 编辑同一文档的所有用户
    - tenant:{tenant_id} — 租户级广播（可选）

    客户端 → 服务端 事件：
    - join_doc: 加入文档房间
    - leave_doc: 离开文档房间
    - yjs_update: Y.js 二进制增量更新
    - awareness_update: 光标/选区感知更新

    服务端 → 客户端 事件：
    - yjs_update: 转发 Y.js 更新到同房间其他客户端
    - awareness_update: 转发光标感知
    - user_joined: 用户加入文档
    - user_left: 用户离开文档
    - doc_users: 当前文档在线用户列表
    - yjs_snapshot: 初始 Y.js 文档快照（加入房间时）
    """

    # sid → session 备份
    _sid_sessions: dict[str, dict] = {}
    # doc:{document_id} → {user_id: {sid, username, color, ...}}
    _doc_users: dict[str, dict[int, dict]] = {}

    # ==================== 连接认证 ====================

    async def on_connect(
        self, sid: str, environ: dict, auth: dict | None = None
    ) -> None:
        """连接认证：从 auth.token 提取 JWT，验证 scope=tenant_admin。"""
        from app.sio.ws_config import get_ws_configs

        ws_cfg = await get_ws_configs("ws_enabled")
        if not ws_cfg.get("ws_enabled", True):
            raise ConnectionRefusedError("websocket_disabled")

        if not auth or not auth.get("token"):
            raise ConnectionRefusedError("token_required")

        token = str(auth["token"]).removeprefix("Bearer ").strip()
        if not token:
            raise ConnectionRefusedError("token_required")

        try:
            user_id_str, scope = verify_token_with_scope(
                token,
                TOKEN_SCOPE_TENANT_ADMIN,
                raise_on_expired=True,
            )
        except TokenExpiredError:
            raise ConnectionRefusedError("token_expired")

        if not user_id_str:
            raise ConnectionRefusedError("authentication_failed")

        user_id = int(user_id_str)

        # 查询租户管理员获取 tenant_id
        from app.core.database import async_session_factory
        from app.models import TenantAdmin
        from sqlalchemy import select

        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantAdmin).where(
                    TenantAdmin.id == user_id,
                    TenantAdmin.is_deleted.is_(False),
                    TenantAdmin.is_active.is_(True),
                )
            )
            tenant_admin = result.scalar_one_or_none()
            if not tenant_admin:
                raise ConnectionRefusedError("account_not_found")
            tenant_id = tenant_admin.tenant_id
            username = tenant_admin.username

        # 保存 session
        session_data = {
            "user_id": user_id,
            "user_type": "tenant_admin",
            "tenant_id": tenant_id,
            "username": username,
        }
        await self.save_session(sid, session_data)
        self._sid_sessions[sid] = session_data

        logger.info(
            "SIO /collaboration connected: sid=%s user_id=%d tenant_id=%d",
            sid,
            user_id,
            tenant_id,
        )

    # ==================== 加入/离开文档 ====================

    async def on_join_doc(self, sid: str, data: dict) -> None:
        """加入文档房间，data: { document_id: int, color?: str }"""
        session = self._sid_sessions.get(sid)
        if not session:
            return

        document_id = data.get("document_id")
        if not document_id:
            await self.emit("error", {"message": "document_id_required"}, to=sid)
            return

        user_id = session["user_id"]
        tenant_id = session["tenant_id"]
        username = session["username"]
        color = data.get("color", self._assign_color(user_id))

        # 校验文档访问权限（租户隔离 + 文档归属/协作者）
        has_access = await self._check_doc_access(
            document_id, user_id, tenant_id
        )
        if not has_access:
            await self.emit(
                "error", {"message": "access_denied"}, to=sid
            )
            return

        room = f"doc:{document_id}"
        await self.enter_room(sid, room)

        # 记录在线用户
        if room not in self._doc_users:
            self._doc_users[room] = {}
        self._doc_users[room][user_id] = {
            "sid": sid,
            "username": username,
            "color": color,
            "user_id": user_id,
        }

        # 更新 session 中的当前房间
        session["current_doc"] = document_id
        session["current_room"] = room

        # 加载 Y.js 快照并发送给新客户端
        snapshot = await self._load_yjs_snapshot(document_id)
        if snapshot:
            await self.emit("yjs_snapshot", snapshot, to=sid)

        # 广播用户加入
        await self.emit(
            "user_joined",
            {
                "user_id": user_id,
                "username": username,
                "color": color,
            },
            room=room,
            skip_sid=sid,
        )

        # 发送当前在线用户列表
        await self.emit(
            "doc_users",
            {"users": list(self._doc_users.get(room, {}).values())},
            to=sid,
        )

        logger.info(
            "SIO /collaboration join_doc: sid=%s user_id=%d doc_id=%s",
            sid,
            user_id,
            document_id,
        )

    async def on_leave_doc(self, sid: str, data: dict | None = None) -> None:
        """离开当前文档房间"""
        session = self._sid_sessions.get(sid)
        if not session:
            return

        room = session.get("current_room")
        user_id = session["user_id"]
        username = session["username"]

        if room:
            await self.leave_room(sid, room)

            # 移除在线用户记录
            if room in self._doc_users:
                self._doc_users[room].pop(user_id, None)
                if not self._doc_users[room]:
                    # 最后一个用户离开 → 持久化 Y.js 状态
                    document_id = session.get("current_doc")
                    if document_id:
                        await self._persist_yjs_snapshot(document_id)
                    del self._doc_users[room]

            # 广播用户离开
            await self.emit(
                "user_left",
                {"user_id": user_id, "username": username},
                room=room,
                skip_sid=sid,
            )

            session.pop("current_doc", None)
            session.pop("current_room", None)

        logger.info(
            "SIO /collaboration leave_doc: sid=%s user_id=%d room=%s",
            sid,
            user_id,
            room,
        )

    # ==================== Y.js 更新转发 ====================

    async def on_yjs_update(self, sid: str, data: bytes) -> None:
        """转发 Y.js 二进制增量更新到同房间其他客户端"""
        session = self._sid_sessions.get(sid)
        if not session:
            return

        room = session.get("current_room")
        if not room:
            return

        # 转发给同房间其他客户端
        await self.emit("yjs_update", data, room=room, skip_sid=sid)

        # 更新 Redis 缓存的 Y.js 快照（异步，不阻塞转发）
        document_id = session.get("current_doc")
        if document_id:
            await self._cache_yjs_update(document_id, data)

    # ==================== 光标感知 ====================

    async def on_awareness_update(self, sid: str, data: bytes) -> None:
        """转发光标感知更新（Awareness Protocol）到同房间其他客户端"""
        session = self._sid_sessions.get(sid)
        if not session:
            return

        room = session.get("current_room")
        if not room:
            return

        await self.emit("awareness_update", data, room=room, skip_sid=sid)

    # ==================== 断开连接 ====================

    async def on_disconnect(self, sid: str, reason: str = "") -> None:
        """断开连接，自动离开文档房间并清理状态"""
        session = self._sid_sessions.get(sid)
        if session:
            # 自动离开文档房间
            await self.on_leave_doc(sid)

        self._sid_sessions.pop(sid, None)

        logger.info(
            "SIO /collaboration disconnected: sid=%s reason=%s",
            sid,
            reason,
        )

    # ==================== 内部方法 ====================

    async def _check_doc_access(
        self, document_id: int, user_id: int, tenant_id: int
    ) -> bool:
        """校验文档访问权限：租户隔离 + 文档所有者/协作者检查"""
        from app.core.database import async_session_factory
        from app.plugins.rich_editor.models.document import RichEditorDocument
        from app.plugins.rich_editor.models.document_collaborator import (
            RichEditorDocumentCollaborator,
        )
        from sqlalchemy import select, or_

        async with async_session_factory() as db:
            # 检查文档是否属于该租户
            result = await db.execute(
                select(RichEditorDocument.id).where(
                    RichEditorDocument.id == document_id,
                    RichEditorDocument.tenant_id == tenant_id,
                    RichEditorDocument.is_deleted.is_(False),
                )
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return False

            # 检查是否为文档所有者或协作者
            result = await db.execute(
                select(RichEditorDocument.id).where(
                    RichEditorDocument.id == document_id,
                    or_(
                        RichEditorDocument.owner_id == user_id,
                        RichEditorDocument.id.in_(
                            select(
                                RichEditorDocumentCollaborator.document_id
                            ).where(
                                RichEditorDocumentCollaborator.user_id
                                == user_id,
                                RichEditorDocumentCollaborator.is_deleted.is_(
                                    False
                                ),
                            )
                        ),
                    ),
                )
            )
            return result.scalar_one_or_none() is not None

    async def _load_yjs_snapshot(
        self, document_id: int
    ) -> bytes | None:
        """从 Redis（优先）或 DB（回退）加载 Y.js 文档快照"""
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            key = f"yjs:doc:{document_id}"
            cached = await redis.get(key)
            if cached:
                # Redis decode_responses=True → base64 字符串
                return base64.b64decode(cached)

            # Redis 没有 → 从 DB 加载
            from app.core.database import async_session_factory
            from app.plugins.rich_editor.models.document import (
                RichEditorDocument,
            )
            from sqlalchemy import select

            async with async_session_factory() as db:
                result = await db.execute(
                    select(RichEditorDocument.content_yjs).where(
                        RichEditorDocument.id == document_id,
                    )
                )
                db_snapshot = result.scalar_one_or_none()
                if db_snapshot:
                    # 写回 Redis 缓存（base64 编码）
                    await redis.set(
                        key, base64.b64encode(db_snapshot).decode(), ex=3600
                    )
                    return db_snapshot
        except Exception as e:
            logger.error(
                "Failed to load Y.js snapshot for doc %d: %s",
                document_id,
                e,
            )
        return None

    async def _cache_yjs_update(
        self, document_id: int, update: bytes
    ) -> None:
        """将 Y.js 增量更新追加到 Redis 缓存列表（base64 编码）"""
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            # 追加到更新列表（base64 编码，后续可合并为快照）
            updates_key = f"yjs:updates:{document_id}"
            encoded = base64.b64encode(update).decode()
            await redis.rpush(updates_key, encoded)
            await redis.expire(updates_key, 3600)
        except Exception as e:
            logger.error(
                "Failed to cache Y.js update for doc %d: %s",
                document_id,
                e,
            )

    async def _persist_yjs_snapshot(self, document_id: int) -> None:
        """
        所有客户端离开后，将 Y.js 状态持久化到 DB 并清理 Redis 缓存。

        合并策略：
        1. 优先使用 yjs:doc:{id} 完整快照
        2. 如果没有快照，从 yjs:updates:{id} 增量列表 + DB 已有快照合并
        3. 都没有则跳过
        """
        try:
            import y_py as Y

            from app.core.redis import get_redis

            redis = await get_redis()
            snapshot_key = f"yjs:doc:{document_id}"
            updates_key = f"yjs:updates:{document_id}"

            # 尝试获取完整快照
            cached_snapshot = await redis.get(snapshot_key)

            # 尝试获取增量更新列表
            cached_updates = await redis.lrange(updates_key, 0, -1)

            if not cached_snapshot and not cached_updates:
                return

            # 构建最终快照
            final_snapshot: bytes | None = None

            if cached_snapshot:
                final_snapshot = base64.b64decode(cached_snapshot)

            if cached_updates:
                # 从 DB 加载基础快照（如果 Redis 没有完整快照）
                if not final_snapshot:
                    from app.core.database import async_session_factory
                    from app.plugins.rich_editor.models.document import (
                        RichEditorDocument,
                    )
                    from sqlalchemy import select as sa_select

                    async with async_session_factory() as db:
                        result = await db.execute(
                            sa_select(RichEditorDocument.content_yjs).where(
                                RichEditorDocument.id == document_id,
                            )
                        )
                        final_snapshot = result.scalar_one_or_none()

                # 将增量更新合并到快照
                doc = Y.YDoc()
                if final_snapshot:
                    Y.apply_update(doc, final_snapshot)
                for encoded_update in cached_updates:
                    update_bytes = base64.b64decode(encoded_update)
                    Y.apply_update(doc, update_bytes)
                final_snapshot = Y.encode_state_as_update(doc)

            if not final_snapshot:
                return

            from app.core.database import async_session_factory
            from app.plugins.rich_editor.models.document import (
                RichEditorDocument,
            )
            from sqlalchemy import update

            async with async_session_factory() as db:
                await db.execute(
                    update(RichEditorDocument)
                    .where(RichEditorDocument.id == document_id)
                    .values(content_yjs=final_snapshot)
                )
                await db.commit()

            # 清理 Redis 缓存
            await redis.delete(snapshot_key, updates_key)

            logger.info(
                "Persisted Y.js snapshot for doc %d (%d bytes, %d updates merged)",
                document_id,
                len(final_snapshot),
                len(cached_updates) if cached_updates else 0,
            )
        except ImportError:
            # y_py 未安装时回退到仅保存快照（不合并增量）
            logger.warning(
                "y_py not installed, falling back to snapshot-only persist for doc %d",
                document_id,
            )
            await self._persist_yjs_snapshot_fallback(document_id)
        except Exception as e:
            logger.error(
                "Failed to persist Y.js snapshot for doc %d: %s",
                document_id,
                e,
            )

    async def _persist_yjs_snapshot_fallback(self, document_id: int) -> None:
        """回退方案：仅持久化 Redis 中的完整快照（不合并增量更新）"""
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            key = f"yjs:doc:{document_id}"
            cached = await redis.get(key)
            if not cached:
                return

            snapshot = base64.b64decode(cached)

            from app.core.database import async_session_factory
            from app.plugins.rich_editor.models.document import (
                RichEditorDocument,
            )
            from sqlalchemy import update

            async with async_session_factory() as db:
                await db.execute(
                    update(RichEditorDocument)
                    .where(RichEditorDocument.id == document_id)
                    .values(content_yjs=snapshot)
                )
                await db.commit()

            updates_key = f"yjs:updates:{document_id}"
            await redis.delete(key, updates_key)
        except Exception as e:
            logger.error(
                "Fallback persist failed for doc %d: %s",
                document_id,
                e,
            )

    @staticmethod
    def _assign_color(user_id: int) -> str:
        """根据 user_id 哈希分配协作者颜色（15 种预设颜色循环）"""
        colors = [
            "#F44336", "#E91E63", "#9C27B0", "#673AB7",
            "#3F51B5", "#2196F3", "#03A9F4", "#00BCD4",
            "#009688", "#4CAF50", "#8BC34A", "#FF9800",
            "#FF5722", "#795548", "#607D8B",
        ]
        return colors[user_id % len(colors)]
