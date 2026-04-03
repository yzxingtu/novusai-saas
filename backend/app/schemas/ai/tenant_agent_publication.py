"""
Tenant agent publication schema / 企业智能体用户发布 Schema
"""

from pydantic import BaseModel, Field


class TenantAgentPublicationUpdate(BaseModel):
    """Update tenant agent publication / 更新企业智能体用户发布配置."""

    enabled_for_users: bool = Field(..., description="Enabled for tenant users")
    access_type: str = Field(..., description="Publication access type")
    tenant_user_role_ids: list[int] | None = Field(
        None, description="Tenant user role IDs"
    )
    tenant_user_ids: list[int] | None = Field(None, description="Tenant user IDs")
    org_node_ids: list[int] | None = Field(None, description="Organization node IDs")


class TenantAgentPublicationResponse(BaseModel):
    """Tenant agent publication response / 企业智能体用户发布响应."""

    agent_id: int = Field(..., description="Agent ID")
    enabled_for_users: bool = Field(..., description="Enabled for tenant users")
    access_type: str = Field(..., description="Publication access type")
    tenant_user_role_ids: list[int] | None = Field(
        None, description="Tenant user role IDs"
    )
    tenant_user_ids: list[int] | None = Field(None, description="Tenant user IDs")
    org_node_ids: list[int] | None = Field(None, description="Organization node IDs")
    publication_id: int | None = Field(None, description="Publication ID")
    published_at: str | None = Field(None, description="Published at")
    published_by: int | None = Field(None, description="Published by")


__all__ = [
    "TenantAgentPublicationUpdate",
    "TenantAgentPublicationResponse",
]
