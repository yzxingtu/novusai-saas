"""
Yjs Document Provider — Redis 持久化

管理 Yjs document 的服务端状态：
- 每个文档对应一个 Y.Doc 实例（内存中）
- state vector / update 通过 Redis 持久化
- Socket.IO 广播 Yjs 更新到同文档的其他客户端

Redis Key 设计：
  ndpro:yjs:{tenant_id}:{doc_id}:state  — Yjs 完整 state（Binary）
  ndpro:yjs:{tenant_id}:{doc_id}:awareness — 在线用户 awareness
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc-pro.yjs")


class YjsDocProvider:
    """Yjs 文档 Provider — 管理单个文档的协作状态"""

    def __init__(self, tenant_id: int, doc_id: int) -> None:
        self.tenant_id = tenant_id
        self.doc_id = doc_id
        self._key_prefix = f"ndpro:yjs:{tenant_id}:{doc_id}"
        self._connected_sids: set[str] = set()

    @property
    def state_key(self) -> str:
        return f"{self._key_prefix}:state"

    @property
    def awareness_key(self) -> str:
        return f"{self._key_prefix}:awareness"

    async def load_state(self) -> bytes | None:
        """从 Redis 加载 Yjs state"""
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            state = await redis.get(self.state_key)
            if state:
                logger.info("yjs: loaded state for doc %d (%d bytes)", self.doc_id, len(state))
            return state
        except Exception as exc:
            logger.error("yjs: failed to load state for doc %d: %s", self.doc_id, exc)
            return None

    async def save_state(self, state: bytes) -> None:
        """保存 Yjs state 到 Redis"""
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            await redis.set(self.state_key, state, ex=86400 * 7)  # 7 days TTL
            logger.info("yjs: saved state for doc %d (%d bytes)", self.doc_id, len(state))
        except Exception as exc:
            logger.error("yjs: failed to save state for doc %d: %s", self.doc_id, exc)

    async def apply_update(self, update: bytes) -> None:
        """应用客户端发来的 Yjs update 并持久化

        要求 y-py 已安装。缺少 y-py 时拒绝写入并记录错误，
        避免 raw 字节拼接导致不可恢复的状态损坏。
        """
        try:
            import y_py as Y
        except ImportError:
            logger.error(
                "yjs: y-py is NOT installed — refusing to apply update for doc %d. "
                "Install y-py>=0.6.0 to enable collaboration persistence.",
                self.doc_id,
            )
            return

        try:
            current_state = await self.load_state()

            doc = Y.YDoc()
            if current_state:
                Y.apply_update(doc, current_state)
            Y.apply_update(doc, update)
            new_state = Y.encode_state_as_update(doc)
            await self.save_state(new_state)
        except Exception as exc:
            logger.error("yjs: failed to apply update for doc %d: %s", self.doc_id, exc)

    def add_connection(self, sid: str) -> None:
        self._connected_sids.add(sid)

    def remove_connection(self, sid: str) -> None:
        self._connected_sids.discard(sid)

    @property
    def connection_count(self) -> int:
        return len(self._connected_sids)

    @property
    def is_empty(self) -> bool:
        return len(self._connected_sids) == 0


class YjsProviderManager:
    """全局 Yjs Provider 管理器（单例）"""

    _instance: YjsProviderManager | None = None
    _providers: dict[str, YjsDocProvider]

    def __init__(self) -> None:
        self._providers = {}

    @classmethod
    def get_instance(cls) -> YjsProviderManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _key(self, tenant_id: int, doc_id: int) -> str:
        return f"{tenant_id}:{doc_id}"

    def get_or_create(self, tenant_id: int, doc_id: int) -> YjsDocProvider:
        key = self._key(tenant_id, doc_id)
        if key not in self._providers:
            self._providers[key] = YjsDocProvider(tenant_id, doc_id)
            logger.info("yjs: created provider for tenant=%d doc=%d", tenant_id, doc_id)
        return self._providers[key]

    def remove_if_empty(self, tenant_id: int, doc_id: int) -> None:
        key = self._key(tenant_id, doc_id)
        provider = self._providers.get(key)
        if provider and provider.is_empty:
            del self._providers[key]
            logger.info("yjs: removed empty provider for tenant=%d doc=%d", tenant_id, doc_id)

    @property
    def active_count(self) -> int:
        return len(self._providers)
