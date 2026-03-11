"""
知识库租户访问关联表 / Knowledge Base Tenant Access Model

当 KnowledgeBase.visibility='assigned' 时，通过此表控制哪些租户可以访问该知识库。
Controls which tenants can access a KB when KnowledgeBase.visibility='assigned'.
"""

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.core.i18n import _


class KnowledgeBaseTenantAccess(BaseModel):
    """
    知识库租户访问关联表

    用于 visibility='assigned' 的知识库，指定哪些租户可以访问。
    """

    __tablename__ = "knowledge_base_tenant_access"

    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("knowledge_base.tenant_access.knowledge_base_id"),
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment=_("knowledge_base.tenant_access.tenant_id"),
    )

    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "tenant_id", name="uq_kb_tenant_access"),
        Index("ix_kb_tenant_access_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<KBTenantAccess(kb_id={self.knowledge_base_id}, tenant_id={self.tenant_id})>"


__all__ = ["KnowledgeBaseTenantAccess"]
