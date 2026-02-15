"""
CRUD 代码生成记录模型

记录每次 CRUD 代码生成操作的完整信息，用于审计追溯。
"""

from sqlalchemy import ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class CrudGenerationRecord(BaseModel):
    """
    CRUD 代码生成记录

    记录每次代码生成操作（预览、写盘、回滚、删除）的完整信息，
    包括配置快照、文件清单、操作人、执行结果等。
    """

    __tablename__ = "crud_generation_records"

    __table_args__ = (
        Index(
            "ix_cgr_operator_created",
            "operator_id",
            "created_at",
        ),
        Index("ix_cgr_operation_type", "operation_type"),
        Index("ix_cgr_status", "status"),
    )

    __filterable__ = {
        "id": "id",
        "operator_id": "operator_id",
        "operation_type": "operation_type",
        "status": "status",
        "module_name": "module_name",
        "table_name": "table_name",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "duration_ms": "duration_ms",
    }

    # ==================== 操作人 ====================

    operator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("admins.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作人 ID（关联 admin 用户）",
    )

    operator_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="操作人用户名（冗余存储，便于展示）",
    )

    # ==================== 操作信息 ====================

    operation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="操作类型: preview / generate / rollback / delete",
    )

    module_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="模块名称（从 config 提取，便于搜索）",
    )

    table_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="表名（从 config 提取，便于搜索）",
    )

    # ==================== 配置快照 ====================

    config_snapshot: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="生成时的 CrudConfig JSON 快照（完整配置冻结）",
    )

    batch_project_snapshot: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="批量生成时的 BatchCrudProject 快照",
    )

    # ==================== 文件清单 ====================

    file_manifest: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="生成的文件清单 JSON（路径、操作类型、文件大小）",
    )

    file_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="文件总数",
    )

    # ==================== 执行结果 ====================

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        comment="执行状态: success / partial_failure / failed / rolled_back",
    )

    error_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="失败时的错误详情",
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="执行耗时（毫秒）",
    )

    # ==================== 关联与元数据 ====================

    parent_record_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("crud_generation_records.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联父记录（回滚操作关联原生成记录）",
    )

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="扩展元数据 JSON（模板版本、生成器版本等）",
    )

    def __repr__(self) -> str:
        return (
            f"<CrudGenerationRecord(id={self.id}, "
            f"type={self.operation_type}, status={self.status}, "
            f"module={self.module_name})>"
        )


__all__ = ["CrudGenerationRecord"]
