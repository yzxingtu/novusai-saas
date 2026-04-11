"""
Context lifecycle helpers / 上下文生命周期辅助模块.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ai.context.engine import (
        ContextAssembly,
        ContextEngine,
        ConversationContextEngine,
        get_context_engine,
    )
    from app.ai.context.pruning import PruneStats, TransientPruner

_EXPORT_MAP = {
    "ContextAssembly": "app.ai.context.engine",
    "ContextEngine": "app.ai.context.engine",
    "ConversationContextEngine": "app.ai.context.engine",
    "get_context_engine": "app.ai.context.engine",
    "PruneStats": "app.ai.context.pruning",
    "TransientPruner": "app.ai.context.pruning",
}


def __getattr__(name: str) -> Any:
    module_path = _EXPORT_MAP.get(name)
    if not module_path:
        raise AttributeError(name)
    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "ContextAssembly",
    "ConversationContextEngine",
    "ContextEngine",
    "PruneStats",
    "TransientPruner",
    "get_context_engine",
]
