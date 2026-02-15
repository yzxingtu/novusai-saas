"""
代码生成器枚举模块

定义 CRUD 代码生成相关的枚举类型
"""

from app.enums.base import LabeledStrEnum


class CodegenOperationType(LabeledStrEnum):
    """代码生成操作类型"""

    PREVIEW = ("preview", "enum.codegen.operation.preview")
    GENERATE = ("generate", "enum.codegen.operation.generate")
    ROLLBACK = ("rollback", "enum.codegen.operation.rollback")
    DELETE = ("delete", "enum.codegen.operation.delete")


class CodegenRecordStatus(LabeledStrEnum):
    """代码生成记录状态"""

    SUCCESS = ("success", "enum.codegen.status.success")
    PARTIAL_FAILURE = ("partial_failure", "enum.codegen.status.partial_failure")
    FAILED = ("failed", "enum.codegen.status.failed")
    ROLLED_BACK = ("rolled_back", "enum.codegen.status.rolled_back")


__all__ = [
    "CodegenOperationType",
    "CodegenRecordStatus",
]
