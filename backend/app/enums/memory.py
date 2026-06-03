"""
Long-term memory enums / 长期记忆枚举
"""

from app.enums.base import LabeledStrEnum


class MemoryScopeTypeEnum(LabeledStrEnum):
    CONVERSATION = ("conversation", "enum.memory.scope.conversation")
    USER_AGENT = ("user_agent", "enum.memory.scope.user_agent")
    TENANT_AGENT = ("tenant_agent", "enum.memory.scope.tenant_agent")
    TENANT_SHARED = ("tenant_shared", "enum.memory.scope.tenant_shared")


class MemoryTypeEnum(LabeledStrEnum):
    PREFERENCE = ("preference", "enum.memory.type.preference")
    CONSTRAINT = ("constraint", "enum.memory.type.constraint")
    FACT = ("fact", "enum.memory.type.fact")
    DECISION = ("decision", "enum.memory.type.decision")
    PATTERN = ("pattern", "enum.memory.type.pattern")
    TASK_SUMMARY = ("task_summary", "enum.memory.type.task_summary")
    CORRECTION = ("correction", "enum.memory.type.correction")
    RELATIONSHIP = ("relationship", "enum.memory.type.relationship")


class MemoryStatusEnum(LabeledStrEnum):
    CANDIDATE = ("candidate", "enum.memory.status.candidate")
    VERIFIED = ("verified", "enum.memory.status.verified")
    SUPPRESSED = ("suppressed", "enum.memory.status.suppressed")
    ARCHIVED = ("archived", "enum.memory.status.archived")
    EXPIRED = ("expired", "enum.memory.status.expired")


class MemorySourceKindEnum(LabeledStrEnum):
    CONVERSATION_TURN = ("conversation_turn", "enum.memory.source.conversation_turn")
    MANUAL_REMEMBER = ("manual_remember", "enum.memory.source.manual_remember")
    TOOL_OUTCOME = ("tool_outcome", "enum.memory.source.tool_outcome")
    KB_DERIVED = ("kb_derived", "enum.memory.source.kb_derived")
    ADMIN_CURATED = ("admin_curated", "enum.memory.source.admin_curated")


__all__ = [
    "MemoryScopeTypeEnum",
    "MemoryTypeEnum",
    "MemoryStatusEnum",
    "MemorySourceKindEnum",
]
