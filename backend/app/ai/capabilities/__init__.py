"""
Capability awareness module / 能力感知模块

Provides dynamic capability description generation for LLM context.
为 LLM 上下文提供动态能力描述生成。
"""

from .description_builder import (
    CapabilityDescription,
    CapabilityDescriptionBuilder,
)

__all__ = [
    "CapabilityDescription",
    "CapabilityDescriptionBuilder",
]
