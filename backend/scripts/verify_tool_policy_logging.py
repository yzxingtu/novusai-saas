"""
Verify runtime tool policy logging by executing a real AgentChatService request.
通过真实 AgentChatService 请求验证运行时 tool policy 与 ai_call_logs 落库。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from sqlalchemy import select

from app.ai.adapters import AdapterRegistry
from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.core.database import async_session_factory
from app.core.redis import RedisManager
from app.enums.common import UserRoleEnum
from app.models.ai.call_log import AICallLog
from app.schemas.ai.invalid_ai_runtime_input import is_invalid_ai_runtime_reference
from app.services.ai.agent_chat_service import AgentChatService


def _collect_retired_runtime_references(value: Any) -> list[str]:
    found: list[str] = []

    def _walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if is_invalid_ai_runtime_reference(key):
                    found.append(str(key))
                _walk(nested)
            return
        if isinstance(item, list | tuple):
            for nested in item:
                _walk(nested)
            return
        if isinstance(item, str) and is_invalid_ai_runtime_reference(item):
            found.append(item)

    _walk(value)
    deduped: list[str] = []
    for item in found:
        if item not in deduped:
            deduped.append(item)
    return deduped


async def _run(agent_id: int, message: str, user_id: int) -> None:
    AdapterRegistry.register("openai_compatible", OpenAIAdapter)
    await RedisManager.init()
    try:
        async with async_session_factory() as db:
            service = AgentChatService(db, 0)
            result = await service.chat(
                agent_id=agent_id,
                message=message,
                conversation_id=None,
                user_id=user_id,
                user_role=UserRoleEnum.PLATFORM_ADMIN.value,
                user_role_id=user_id,
                permissions=set(),
            )

            print(f"conversation_id={result.conversation_id}")
            print(f"total_tokens={result.total_tokens}")
            print("assistant_preview=")
            print((result.message or "")[:1200])

            log_rows = (
                (
                    await db.execute(
                        select(AICallLog)
                        .where(AICallLog.conversation_id == result.conversation_id)
                        .order_by(AICallLog.id.desc())
                        .limit(5)
                    )
                )
                .scalars()
                .all()
            )

            print("\nai_call_logs:")
            for row in log_rows:
                metadata: dict[str, Any] = dict(row.request_metadata or {})
                request_payload = dict(metadata.get("request") or {})
                retired_refs = _collect_retired_runtime_references(request_payload)
                if retired_refs:
                    raise RuntimeError(
                        "retired online-search runtime references found: "
                        + ", ".join(retired_refs)
                    )
                print(
                    json.dumps(
                        {
                            "id": row.id,
                            "total_tokens": row.total_tokens,
                            "tool_choice": request_payload.get("tool_choice"),
                            "selected_tool_names": request_payload.get(
                                "selected_tool_names"
                            ),
                            "all_tool_names": request_payload.get("all_tool_names"),
                            "tool_use_policy": request_payload.get("tool_use_policy"),
                            "breach_retry_result": request_payload.get(
                                "breach_retry_result"
                            ),
                        },
                        ensure_ascii=False,
                    )
                )
    finally:
        await RedisManager.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify tool policy logging for a real agent chat request.",
    )
    parser.add_argument("--agent-id", type=int, default=59)
    parser.add_argument(
        "--message",
        type=str,
        default="说明一下小猫为什么爱吃鱼",
    )
    parser.add_argument("--user-id", type=int, default=1)
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(_run(args.agent_id, args.message, args.user_id))


if __name__ == "__main__":
    main()
