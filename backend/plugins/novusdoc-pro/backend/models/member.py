"""
NovusDoc Pro 文档成员权限模型

表名: px_novusdoc_pro_doc_members

协作角色策略（已确认）：
- 仅 tenant_admin 可参与文档协作（编辑/评论/查看）
- tenant_user 不支持进入协作会话（Socket.IO auth_scopes 限制）
- user_type 字段固定为 "tenant_admin"，预留扩展但当前不支持其他值
"""

from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class NovusdocProDocMember(TenantModel):
    """文档成员（权限控制）"""

    __tablename__ = "px_novusdoc_pro_doc_members"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "document_id": "document_id",
        "user_id": "user_id",
        "role": "role",
    }

    document_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="文档 ID",
    )
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="用户 ID",
    )
    user_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="tenant_admin",
        comment="用户类型: tenant_admin",
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="editor",
        comment="角色: owner / editor / commenter / viewer",
    )

    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_ndpro_doc_member"),
        Index("ix_ndpro_members_doc", "document_id", "tenant_id"),
    )
