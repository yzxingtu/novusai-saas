"""
Routing contracts for ModelRouter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RouteResult:
    """Routing result / 路由结果"""

    provider_code: str
    model_code: str
    model_id: int
    tier: str | None
    reason: str
    is_overridden: bool = False


__all__ = ["RouteResult"]
