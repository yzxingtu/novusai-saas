"""
AI usage metrics compatibility facade / AI 用量指标兼容入口

Kept for legacy imports; runtime implementation lives in
`app.ai.runtime.usage_metrics`.
保留旧导入兼容，运行时实现已下沉至 `app.ai.runtime.usage_metrics`。
"""

from __future__ import annotations

from app.ai.runtime.usage_metrics import CostCalculator, TokenCounter

__all__ = ["TokenCounter", "CostCalculator"]
