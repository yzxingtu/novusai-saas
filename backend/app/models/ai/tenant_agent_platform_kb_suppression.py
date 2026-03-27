"""
企业按租户停用平台全局知识库 / Tenant opt-out from platform agent KB for RAG.

管理端在平台智能体上绑定的知识库（binding.tenant_id IS NULL）默认对所有可用企业生效；
本表记录「某企业选择不在对话 RAG 中使用某个平台全局 KB」。
"""

from sqlalchemy import ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class TenantAgentPlatformKbSuppression(TenantModel):
    """
    平台智能体知识库按企业停用 / Suppress platform KB for one tenant on one agent.

    部分唯一索引（PostgreSQL）：仅 is_deleted=false 时 (tenant_id, agent_id, knowledge_base_id) 唯一。
    """

    __tablename__ = "tenant_agent_platform_kb_suppressions"

    __table_args__ = (
        Index(
            "uq_tapks_active",
            "tenant_id",
            "agent_id",
            "knowledge_base_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "ix_tapks_tenant_agent",
            "tenant_id",
            "agent_id",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="企业ID / Tenant ID",
    )

    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="智能体 ID / Agent ID",
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="知识库 ID / Knowledge base ID",
    )

    def __repr__(self) -> str:
        return (
            f"<TenantAgentPlatformKbSuppression(tenant={self.tenant_id}, "
            f"agent={self.agent_id}, kb={self.knowledge_base_id})>"
        )


__all__ = ["TenantAgentPlatformKbSuppression"]
