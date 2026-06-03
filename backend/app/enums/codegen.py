"""
CRUD 代码生成器枚举 / CRUD Codegen Enum

定义代码生成器配置状态枚举
Defines codegen config status enum.
"""

from app.enums.base import LabeledStrEnum


class CodegenConfigStatusEnum(LabeledStrEnum):
    """Codegen config status enum / 代码生成配置状态枚举"""

    DRAFT = ("draft", "codegen.status.draft")
    GENERATED = ("generated", "codegen.status.generated")
    APPLIED = ("applied", "codegen.status.applied")
    ROLLED_BACK = ("rolled_back", "codegen.status.rolled_back")


__all__ = ["CodegenConfigStatusEnum"]
