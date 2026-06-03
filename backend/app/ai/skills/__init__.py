"""
Skill Architecture Module / Skill 架构模块

Converts Skill (user-facing management unit) to ToolDefinition (LLM-facing calling protocol).
将 Skill（面向用户的管理单元）转换为 ToolDefinition（面向 LLM 的调用协议）。
"""

from app.ai.skills.resolver import (
    SkillResolver,
    SkillResolveResult,
)

__all__ = [
    "SkillResolver",
    "SkillResolveResult",
]
