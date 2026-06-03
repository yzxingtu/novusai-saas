"""
Execution decision enums / 执行决策枚举
"""

from app.enums.base import LabeledStrEnum


class ExecutionDecisionTypeEnum(LabeledStrEnum):
    CONSENT = ("consent", "")
    CONFIRMATION = ("confirmation", "")


class ExecutionDecisionSubjectEnum(LabeledStrEnum):
    TOOL_CALL = ("tool_call", "")
    DATA_ACTION = ("data_action", "")


class ExecutionDecisionStatusEnum(LabeledStrEnum):
    PENDING = ("pending", "")
    APPROVED = ("approved", "")
    REJECTED = ("rejected", "")
    EXPIRED = ("expired", "")
    AUTO_APPROVED = ("auto_approved", "")


class ExecutionDecisionScopeEnum(LabeledStrEnum):
    ONCE = ("once", "")
    CONVERSATION = ("conversation", "")
    POLICY = ("policy", "")


__all__ = [
    "ExecutionDecisionTypeEnum",
    "ExecutionDecisionSubjectEnum",
    "ExecutionDecisionStatusEnum",
    "ExecutionDecisionScopeEnum",
]
