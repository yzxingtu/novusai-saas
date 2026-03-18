"""
CRUD 代码生成配置模型 / CRUD Codegen Config Model

平台级配置，存储 YAML 解析后的完整配置 JSON
Platform-level config, stores full parsed YAML config as JSON.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.enums.codegen import CodegenConfigStatusEnum


class CodegenConfig(BaseModel):
    """
    CRUD 代码生成配置模型 / CRUD codegen config model.

    平台级资源，无企业隔离。用于存储和管理 CRUD 代码生成器的配置。
    Platform-level resource, no tenant isolation.
    """

    __tablename__ = "codegen_configs"

    # 可过滤字段 / Filterable fields
    __filterable__ = {
        "id": "id",
        "name": "name",
        "resource": "resource",
        "module": "module",
        "status": "status",
        "display_name": "display_name",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "last_generated_at": "last_generated_at",
    }

    __delete_deps__ = [
        DeletionDep(
            "CodegenConfigVersion",
            "config_id",
            DeletionStrategy.CASCADE_DELETE,
            label_field="id",
            i18n_key="codegen_config_version",
        ),
    ]

    # 可排序字段 / Sortable fields
    __sortable__ = [
        "id",
        "name",
        "resource",
        "module",
        "status",
        "display_name",
        "created_at",
        "updated_at",
        "last_generated_at",
        "generation_count",
    ]

    # 配置名称 / Config name
    name: Mapped[str] = mapped_column(
        String(100), comment="配置名称 / Config name"
    )
    # 资源名 snake_case / Resource name (snake_case)
    resource: Mapped[str] = mapped_column(
        String(100), index=True, unique=True, comment="资源名 / Resource name (snake_case)"
    )
    # 模块归属 / Module affiliation
    module: Mapped[str] = mapped_column(
        String(50), comment="模块归属 / Module affiliation"
    )
    # 中文显示名 / Display name (Chinese)
    display_name: Mapped[str] = mapped_column(
        String(100), comment="中文显示名 / Display name (Chinese)"
    )
    # 英文显示名 / Display name (English)
    display_name_en: Mapped[str] = mapped_column(
        String(100), comment="英文显示名 / Display name (English)"
    )
    # 状态: draft/generated/applied/rolled_back
    status: Mapped[str] = mapped_column(
        String(20),
        default=CodegenConfigStatusEnum.DRAFT.value,
        comment="状态 / Status: draft/generated/applied/rolled_back",
    )
    # 完整配置 JSON / Full config JSON
    config_json: Mapped[dict] = mapped_column(
        JSONB, comment="完整配置 JSON / Full config JSON"
    )
    # 上次生成时间 / Last generated at
    last_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="上次生成时间 / Last generated at"
    )
    # 生成次数 / Generation count
    generation_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="生成次数 / Generation count"
    )
    # 上次生成文件清单 / Last generated files manifest
    generated_files: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="上次生成文件清单 / Last generated files manifest"
    )
    # 配置哈希（用于检测变更）/ Config hash (for change detection)
    config_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="配置哈希 / Config hash"
    )
    # 上次生成错误信息 / Last generation error
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="上次生成错误 / Last generation error"
    )

    versions = relationship(
        "CodegenConfigVersion",
        back_populates="config",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CodegenConfig(id={self.id}, resource={self.resource})>"


__all__ = ["CodegenConfig"]
