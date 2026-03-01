"""
Yjs Document Provider — Redis 持久化

管理 Yjs document 的服务端状态：
- 每个文档对应一个 Y.Doc 实例（内存中）
- 首次加载从 Redis 恢复，之后 update 仅操作内存
- 防抖持久化：update 后 5s 内无新 update 才写入 Redis
- provider 销毁时保证最终持久化

Redis Key 设计：
  ndpro:yjs:{tenant_id}:{doc_id}:state  — Yjs 完整 state（Binary）
  ndpro:yjs:{tenant_id}:{doc_id}:awareness — 在线用户 awareness
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc-pro.yjs")

_PERSIST_DEBOUNCE_SECONDS = 5.0
_REDIS_TTL_SECONDS = 86400 * 7  # 7 days


class YjsDocProvider:
    """Yjs 文档 Provider — 管理单个文档的协作状态

    Y.Doc 在 provider 生命周期内保持在内存中，
    Redis 只在首次加载和防抖持久化时访问。
    """

    def __init__(self, tenant_id: int, doc_id: int) -> None:
        self.tenant_id = tenant_id
        self.doc_id = doc_id
        self._key_prefix = f"ndpro:yjs:{tenant_id}:{doc_id}"
        self._connected_sids: set[str] = set()
        self._ydoc: Any = None  # Y.YDoc instance (lazy init)
        self._dirty = False
        self._persist_task: asyncio.Task[None] | None = None
        self._loaded = False

    @property
    def state_key(self) -> str:
        return f"{self._key_prefix}:state"

    @property
    def awareness_key(self) -> str:
        return f"{self._key_prefix}:awareness"

    async def _ensure_ydoc(self) -> Any:
        """Lazy-init Y.Doc and load state from Redis on first access."""
        if self._ydoc is not None:
            return self._ydoc

        try:
            import y_py as Y
        except ImportError:
            logger.error(
                "yjs: y-py is NOT installed — collaboration persistence disabled for doc %d. "
                "Install y-py>=0.6.0 to enable.",
                self.doc_id,
            )
            return None

        self._ydoc = Y.YDoc()

        if not self._loaded:
            state = await self._redis_load()
            if state:
                try:
                    Y.apply_update(self._ydoc, state)
                    logger.info("yjs: loaded state for doc %d (%d bytes)", self.doc_id, len(state))
                except Exception as exc:
                    logger.error("yjs: failed to apply saved state for doc %d: %s", self.doc_id, exc)
            self._loaded = True

        return self._ydoc

    async def load_state(self) -> bytes | None:
        """获取当前 Yjs state（从内存 Y.Doc 编码）"""
        try:
            import y_py as Y
        except ImportError:
            return await self._redis_load()

        doc = await self._ensure_ydoc()
        if doc is None:
            return await self._redis_load()

        try:
            return Y.encode_state_as_update(doc)
        except Exception as exc:
            logger.error("yjs: failed to encode state for doc %d: %s", self.doc_id, exc)
            return None

    async def apply_update(self, update: bytes) -> None:
        """应用客户端发来的 Yjs update（内存操作 + 防抖持久化）"""
        try:
            import y_py as Y
        except ImportError:
            logger.error(
                "yjs: y-py is NOT installed — refusing to apply update for doc %d.",
                self.doc_id,
            )
            return

        doc = await self._ensure_ydoc()
        if doc is None:
            return

        try:
            Y.apply_update(doc, update)
            self._dirty = True
            self._schedule_persist()
        except Exception as exc:
            logger.error("yjs: failed to apply update for doc %d: %s", self.doc_id, exc)

    def _schedule_persist(self) -> None:
        """Schedule debounced Redis persistence."""
        if self._persist_task and not self._persist_task.done():
            self._persist_task.cancel()
        try:
            loop = asyncio.get_running_loop()
            self._persist_task = loop.create_task(self._debounced_persist())
        except RuntimeError:
            pass

    async def _debounced_persist(self) -> None:
        """Wait for debounce period then persist to Redis."""
        try:
            await asyncio.sleep(_PERSIST_DEBOUNCE_SECONDS)
            await self._persist_to_redis()
        except asyncio.CancelledError:
            pass

    async def _persist_to_redis(self) -> None:
        """Encode current Y.Doc and save to Redis."""
        if not self._dirty or self._ydoc is None:
            return

        try:
            import y_py as Y
            state = Y.encode_state_as_update(self._ydoc)
            await self._redis_save(state)
            self._dirty = False
        except Exception as exc:
            logger.error("yjs: failed to persist state for doc %d: %s", self.doc_id, exc)

    async def flush(self) -> None:
        """Force persist current state to Redis (called before provider removal)."""
        if self._persist_task and not self._persist_task.done():
            self._persist_task.cancel()
        await self._persist_to_redis()

    async def _redis_load(self) -> bytes | None:
        """Raw Redis GET."""
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            return await redis.get(self.state_key)
        except Exception as exc:
            logger.error("yjs: redis load failed for doc %d: %s", self.doc_id, exc)
            return None

    async def _redis_save(self, state: bytes) -> None:
        """Raw Redis SET."""
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            await redis.set(self.state_key, state, ex=_REDIS_TTL_SECONDS)
            logger.info("yjs: persisted state for doc %d (%d bytes)", self.doc_id, len(state))
        except Exception as exc:
            logger.error("yjs: redis save failed for doc %d: %s", self.doc_id, exc)

    def add_connection(self, sid: str) -> None:
        self._connected_sids.add(sid)

    def remove_connection(self, sid: str) -> None:
        self._connected_sids.discard(sid)

    def has_connection(self, sid: str) -> bool:
        return sid in self._connected_sids

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
            # Flush state to Redis before removing
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(provider.flush())
            except RuntimeError:
                pass
            del self._providers[key]
            logger.info("yjs: removed empty provider for tenant=%d doc=%d", tenant_id, doc_id)

    def iter_providers(self) -> list[tuple[str, YjsDocProvider]]:
        """Return a snapshot of (key, provider) pairs for safe iteration."""
        return list(self._providers.items())

    @property
    def active_count(self) -> int:
        return len(self._providers)
