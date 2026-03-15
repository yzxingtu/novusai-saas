"""
会话记忆存储服务（Redis） / Session Memory Service (Redis)

能力 / Capabilities:
1) 会话记忆读取/写入
2) CAS 版本控制（version compare-and-set）
3) event_id 幂等防重
4) TTL 自动续期（24h）
5) 按 conversation 维度清理
"""

from __future__ import annotations

import json
import time
from contextlib import suppress
from typing import Any

from redis.asyncio.client import Pipeline

from app.ai.constants import (
    SESSION_MEMORY_TTL_SECONDS,
    session_memory_conversation_pattern,
    session_memory_key,
)
from app.core.logging import LogManager
from app.core.redis import get_redis_client

logger = LogManager.get_logger("ai.session_memory_service")


class SessionMemoryService:
    """
    会话记忆 Redis 服务 / Session memory Redis service.
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    @staticmethod
    def _get_redis_safe():
        """
        获取 Redis 客户端（未初始化时返回 None，调用方降级）/ Get Redis client (None if not initialized).
        """
        try:
            return get_redis_client()
        except RuntimeError:
            return None

    @staticmethod
    def _empty_state(
        *,
        tenant_id: int,
        channel: str,
        source: str,
        agent_id: int,
        user_id: int,
        conversation_id: int,
    ) -> dict[str, Any]:
        return {
            "tenant_id": tenant_id,
            "channel": channel,
            "source": source,
            "agent_id": agent_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "version": 0,
            "updated_at": int(time.time()),
            "last_event_id": None,
            "preferences": [],
            "constraints": [],
            "task_states": [],
            "verified_facts": [],
            "metadata": {},
        }

    async def get_state(
        self,
        *,
        channel: str,
        source: str,
        agent_id: int,
        user_id: int,
        conversation_id: int,
    ) -> tuple[str, dict[str, Any]]:
        """
        读取会话记忆状态（不存在时返回空状态）/ Get session memory state (empty if missing).
        """
        key = session_memory_key(
            tenant_id=self.tenant_id,
            channel=channel,
            source=source,
            agent_id=agent_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        redis = self._get_redis_safe()
        if redis is None:
            logger.warning(
                "Session memory degraded (redis unavailable): tenant=%s agent=%s user=%s conversation=%s",
                self.tenant_id,
                agent_id,
                user_id,
                conversation_id,
            )
            return key, self._empty_state(
                tenant_id=self.tenant_id,
                channel=channel,
                source=source,
                agent_id=agent_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        raw = await redis.get(key)
        if not raw:
            logger.info(
                "Session memory miss: tenant=%s agent=%s user=%s conversation=%s",
                self.tenant_id,
                agent_id,
                user_id,
                conversation_id,
            )
            return key, self._empty_state(
                tenant_id=self.tenant_id,
                channel=channel,
                source=source,
                agent_id=agent_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                logger.info(
                    "Session memory hit: tenant=%s agent=%s user=%s conversation=%s version=%s",
                    self.tenant_id,
                    agent_id,
                    user_id,
                    conversation_id,
                    data.get("version", 0),
                )
                return key, data
        except json.JSONDecodeError:
            logger.warning("Invalid session memory payload, reset: key=%s", key)
        return key, self._empty_state(
            tenant_id=self.tenant_id,
            channel=channel,
            source=source,
            agent_id=agent_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    @staticmethod
    def _merge_list(original: list[str], incoming: list[str], limit: int = 20) -> list[str]:
        """
        合并字符串列表，去重并截断 / Merge string lists, dedup and truncate.
        """
        seen: set[str] = set()
        merged: list[str] = []
        for item in [*incoming, *original]:
            text = (item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
            if len(merged) >= limit:
                break
        return merged

    async def update_state_cas(
        self,
        *,
        channel: str,
        source: str,
        agent_id: int,
        user_id: int,
        conversation_id: int,
        expected_version: int,
        event_id: str,
        delta: dict[str, list[str]],
        metadata: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        基于 expected_version 的 CAS 更新 / CAS update by expected_version.

        Returns:
            (success, state)
            - success=False 表示 CAS 冲突，返回最新 state
        """
        key = session_memory_key(
            tenant_id=self.tenant_id,
            channel=channel,
            source=source,
            agent_id=agent_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        redis = self._get_redis_safe()
        if redis is None:
            # Redis 未初始化时降级：直接返回当前空状态
            logger.warning(
                "Session memory write degraded (redis unavailable): tenant=%s agent=%s user=%s conversation=%s",
                self.tenant_id,
                agent_id,
                user_id,
                conversation_id,
            )
            return True, self._empty_state(
                tenant_id=self.tenant_id,
                channel=channel,
                source=source,
                agent_id=agent_id,
                user_id=user_id,
                conversation_id=conversation_id,
            )

        while True:
            async with redis.pipeline(transaction=True) as pipe:
                pipe: Pipeline
                try:
                    await pipe.watch(key)
                    raw = await redis.get(key)
                    if raw:
                        state = json.loads(raw)
                    else:
                        state = self._empty_state(
                            tenant_id=self.tenant_id,
                            channel=channel,
                            source=source,
                            agent_id=agent_id,
                            user_id=user_id,
                            conversation_id=conversation_id,
                        )

                    current_version = int(state.get("version", 0))
                    if current_version != expected_version:
                        logger.info(
                            "Session memory CAS conflict: tenant=%s agent=%s user=%s conversation=%s expected=%s actual=%s",
                            self.tenant_id,
                            agent_id,
                            user_id,
                            conversation_id,
                            expected_version,
                            current_version,
                        )
                        await pipe.unwatch()
                        return False, state

                    # 幂等：event_id 重复直接返回成功（不重复写）
                    if event_id and state.get("last_event_id") == event_id:
                        logger.info(
                            "Session memory idempotent hit: tenant=%s agent=%s user=%s conversation=%s event_id=%s",
                            self.tenant_id,
                            agent_id,
                            user_id,
                            conversation_id,
                            event_id,
                        )
                        await pipe.unwatch()
                        return True, state

                    state["preferences"] = self._merge_list(
                        state.get("preferences", []),
                        delta.get("preferences", []),
                    )
                    state["constraints"] = self._merge_list(
                        state.get("constraints", []),
                        delta.get("constraints", []),
                    )
                    state["task_states"] = self._merge_list(
                        state.get("task_states", []),
                        delta.get("task_states", []),
                    )
                    state["verified_facts"] = self._merge_list(
                        state.get("verified_facts", []),
                        delta.get("verified_facts", []),
                    )

                    state["version"] = current_version + 1
                    state["updated_at"] = int(time.time())
                    state["last_event_id"] = event_id
                    if metadata:
                        state["metadata"] = {**state.get("metadata", {}), **metadata}

                    payload = json.dumps(state, ensure_ascii=False)
                    pipe.multi()
                    await pipe.set(key, payload, ex=SESSION_MEMORY_TTL_SECONDS)
                    await pipe.execute()
                    logger.info(
                        "Session memory updated: tenant=%s agent=%s user=%s conversation=%s version=%s",
                        self.tenant_id,
                        agent_id,
                        user_id,
                        conversation_id,
                        state["version"],
                    )
                    return True, state
                except Exception:
                    # WATCH 冲突重试一次
                    with suppress(Exception):
                        await pipe.reset()
                    latest_raw = await redis.get(key)
                    latest = json.loads(latest_raw) if latest_raw else self._empty_state(
                        tenant_id=self.tenant_id,
                        channel=channel,
                        source=source,
                        agent_id=agent_id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                    )
                    logger.warning(
                        "Session memory CAS retry required: tenant=%s agent=%s user=%s conversation=%s",
                        self.tenant_id,
                        agent_id,
                        user_id,
                        conversation_id,
                    )
                    return False, latest

    async def upsert_state(
        self,
        *,
        channel: str,
        source: str,
        agent_id: int,
        user_id: int,
        conversation_id: int,
        event_id: str,
        delta: dict[str, list[str]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        读当前 state 后执行 CAS 更新，冲突时自动重试一次 / Read state then CAS update, retry once on conflict.
        """
        _, state = await self.get_state(
            channel=channel,
            source=source,
            agent_id=agent_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        expected = int(state.get("version", 0))
        ok, latest = await self.update_state_cas(
            channel=channel,
            source=source,
            agent_id=agent_id,
            user_id=user_id,
            conversation_id=conversation_id,
            expected_version=expected,
            event_id=event_id,
            delta=delta,
            metadata=metadata,
        )
        if ok:
            return latest

        # 冲突重试一次
        expected_retry = int(latest.get("version", 0))
        _, final_state = await self.update_state_cas(
            channel=channel,
            source=source,
            agent_id=agent_id,
            user_id=user_id,
            conversation_id=conversation_id,
            expected_version=expected_retry,
            event_id=event_id,
            delta=delta,
            metadata=metadata,
        )
        return final_state

    async def get_conversation_memory_state(
        self, conversation_id: int,
    ) -> dict[str, Any]:
        """
        读取会话下全部记忆状态（跨渠道/来源）/ Read all memory state for a conversation (across all channels/sources).

        Returns merged state dict with preferences/constraints/task_states/verified_facts.
        """
        redis = self._get_redis_safe()
        if redis is None:
            return {
                "preferences": [],
                "constraints": [],
                "task_states": [],
                "verified_facts": [],
                "version": 0,
                "updated_at": 0,
            }

        pattern = session_memory_conversation_pattern(self.tenant_id, conversation_id)
        cursor = 0
        merged: dict[str, Any] = {
            "preferences": [],
            "constraints": [],
            "task_states": [],
            "verified_facts": [],
            "version": 0,
            "updated_at": 0,
        }

        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=200)
            for key in keys:
                raw = await redis.get(key)
                if not raw:
                    continue
                try:
                    state = json.loads(raw)
                    if not isinstance(state, dict):
                        continue
                    for field in ("preferences", "constraints", "task_states", "verified_facts"):
                        merged[field] = self._merge_list(
                            merged[field], state.get(field, []),
                        )
                    merged["version"] = max(
                        merged["version"], int(state.get("version", 0)),
                    )
                    merged["updated_at"] = max(
                        merged["updated_at"], int(state.get("updated_at", 0)),
                    )
                except (json.JSONDecodeError, ValueError):
                    logger.warning("Invalid session memory payload, skip: key=%s", key)
            if cursor == 0:
                break

        logger.info(
            "Session memory state fetched: tenant=%s conversation=%s version=%s",
            self.tenant_id,
            conversation_id,
            merged["version"],
        )
        return merged

    async def clear_conversation_memory(self, conversation_id: int) -> int:
        """
        清理当前 tenant 下指定 conversation 的所有会话记忆 key / Clear all session memory keys for conversation.
        """
        redis = self._get_redis_safe()
        if redis is None:
            return 0
        pattern = session_memory_conversation_pattern(self.tenant_id, conversation_id)
        cursor = 0
        total_deleted = 0
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                total_deleted += await redis.delete(*keys)
            if cursor == 0:
                break
        logger.info(
            "Session memory cleared by conversation: tenant=%s conversation=%s deleted=%s",
            self.tenant_id,
            conversation_id,
            total_deleted,
        )
        return total_deleted


__all__ = ["SessionMemoryService"]
