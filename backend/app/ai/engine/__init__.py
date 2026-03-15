"""
Execution Engine Module / 执行引擎模块

Provides multi-mode engine implementations and a unified dispatcher.
提供多执行模式的引擎实现和统一分发器。
"""

from app.ai.engine.base import BaseEngine
from app.ai.engine.batch import BatchEngine
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.dispatcher import ExecutionDispatcher
from app.ai.engine.task import TaskEngine
from app.ai.engine.types import (
    BatchItem,
    BatchResult,
    ExecutionRequest,
    ExecutionResult,
)

__all__ = [
    # Types / 类型
    "ExecutionRequest",
    "ExecutionResult",
    "BatchItem",
    "BatchResult",
    # Engines / 引擎
    "BaseEngine",
    "ConversationEngine",
    "TaskEngine",
    "BatchEngine",
    # Dispatcher / 分发器
    "ExecutionDispatcher",
]
