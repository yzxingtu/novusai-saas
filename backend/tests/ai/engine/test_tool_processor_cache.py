"""
Test type: behavioral
Scope: ToolCallProcessor turn-local readonly cache behavior.
Mocked dependencies: Tool sandbox executor only; cache ownership runs real.
"""

from typing import Any

from app.ai.tools.types import ToolResult


class _FakeSandbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(
        self,
        tool_call_id: str,
        name: str,
        arguments: dict[str, Any],
        definitions=None,
        conversation_id: int | None = None,
    ) -> ToolResult:
        del definitions, conversation_id
        self.calls.append((name, dict(arguments)))
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            success=True,
            output=f"{name}-result",
        )
