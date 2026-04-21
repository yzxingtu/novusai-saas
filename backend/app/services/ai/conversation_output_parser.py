"""
Lazy output parser wrapper for ConversationStatsService.
"""

from __future__ import annotations

from typing import Any


def parse_output(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper to avoid importing the engine parser at module load."""
    from app.ai.engine.output_parser import parse_output as _parse_output

    return _parse_output(*args, **kwargs)
