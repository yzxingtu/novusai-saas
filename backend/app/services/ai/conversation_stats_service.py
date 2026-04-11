"""Conversation stats update helpers."""

from __future__ import annotations

from typing import Any


class ConversationStatsService:
    """Owns token/cost stat updates and output extraction for conversations."""

    def __init__(self, *, repo: Any, parse_output_fn: Any) -> None:
        self.repo = repo
        self.parse_output = parse_output_fn

    async def update_stats(
        self,
        *,
        conversation: Any,
        result: Any,
        current_agent: Any | None = None,
    ) -> None:
        new_token_count = (conversation.token_count or 0) + result.total_tokens
        new_total_tokens = (conversation.total_tokens or 0) + result.total_tokens

        update_data: dict[str, Any] = {
            "token_count": new_token_count,
            "total_tokens": new_total_tokens,
        }

        agent = current_agent or conversation.agent
        if agent and agent.output_schema and result.output:
            extracted = self.parse_output(result.output, agent.output_schema)
            if extracted:
                metadata = dict(conversation.metadata_ or {})
                metadata["output_variables"] = extracted
                update_data["metadata_"] = metadata

        await self.repo.update(conversation.id, update_data)
