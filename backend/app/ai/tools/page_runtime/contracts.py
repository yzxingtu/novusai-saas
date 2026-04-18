"""Page-runtime tool contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class PageRuntimeGuardResult:
    """Preflight guard outcome before the bridge is invoked."""

    allowed: bool
    error_type: str = ""
    message: str = ""
    payload: dict[str, Any] | None = None


class PageRuntimeBridge(Protocol):
    """Bridge frontend page-runtime requests to the active page session."""

    async def invoke(
        self,
        *,
        arguments: dict[str, Any],
        page_session_id: str,
        tool_name: str,
        user_role: str,
    ) -> dict[str, Any]: ...

