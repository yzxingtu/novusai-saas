"""
Execution Engine Module / 执行引擎模块

Provides multi-mode engine implementations and a unified dispatcher.
提供多执行模式的引擎实现和统一分发器。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.engine.types import (
    BatchItem,
    BatchResult,
    ExecutionRequest,
    ExecutionResult,
)
from app.ai.runtime import ProtocolExecutionPlan, TurnCommand, TurnExecutionResult

if TYPE_CHECKING:
    from app.ai.engine.base import BaseEngine
    from app.ai.engine.batch import BatchEngine
    from app.ai.engine.conversation import ConversationEngine
    from app.ai.engine.dispatcher import ExecutionDispatcher
    from app.ai.engine.task import TaskEngine


def __getattr__(name: str) -> Any:
    if name == "BaseEngine":
        from app.ai.engine.base import BaseEngine

        return BaseEngine
    if name == "ConversationEngine":
        from app.ai.engine.conversation import ConversationEngine

        return ConversationEngine
    if name == "TaskEngine":
        from app.ai.engine.task import TaskEngine

        return TaskEngine
    if name == "BatchEngine":
        from app.ai.engine.batch import BatchEngine

        return BatchEngine
    if name == "ExecutionDispatcher":
        from app.ai.engine.dispatcher import ExecutionDispatcher

        return ExecutionDispatcher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ExecutionRequest",
    "ExecutionResult",
    "BatchItem",
    "BatchResult",
    "ProtocolExecutionPlan",
    "TurnCommand",
    "TurnExecutionResult",
    "BaseEngine",
    "ConversationEngine",
    "TaskEngine",
    "BatchEngine",
    "ExecutionDispatcher",
]
