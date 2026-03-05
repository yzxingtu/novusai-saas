"""
租户 Schema 模块

导出租户相关的 Schema
"""

from app.schemas.tenant.admin import (
    TenantAdminChangePasswordRequest,
    TenantAdminCreateRequest,
    TenantAdminLoginRequest,
    TenantAdminResponse,
    TenantAdminUpdateProfileRequest,
    TenantAdminUpdateRequest,
)
from app.schemas.tenant.attachment import AttachmentAccessUrlResponse
from app.schemas.tenant.domain import (
    TenantDomainCreateRequest,
    TenantDomainResponse,
    TenantDomainSimpleResponse,
    TenantDomainUpdateRequest,
    TenantDomainVerificationInfo,
    TenantDomainVerifyRequest,
    TenantSettingsResponse,
    TenantSettingsUpdateRequest,
)
from app.schemas.tenant.plan import (
    FeaturesSchema,
    PermissionSimpleResponse,
    QuotaSchema,
    TenantPlanCreateRequest,
    TenantPlanDetailResponse,
    TenantPlanPermissionsRequest,
    TenantPlanResponse,
    TenantPlanUpdateRequest,
)
from app.schemas.tenant.role import (
    TenantAdminRoleAddMemberRequest,
    TenantAdminRoleCreateMemberRequest,
    TenantAdminRoleCreateRequest,
    TenantAdminRoleDetailResponse,
    TenantAdminRoleMemberResponse,
    TenantAdminRoleMoveRequest,
    TenantAdminRolePermissionsRequest,
    TenantAdminRoleResetPasswordRequest,
    TenantAdminRoleResponse,
    TenantAdminRoleSetLeaderRequest,
    TenantAdminRoleToggleStatusRequest,
    TenantAdminRoleTreeNode,
    TenantAdminRoleUpdateMemberRequest,
    TenantAdminRoleUpdateRequest,
)
from app.schemas.tenant.ssl import (
    SslAutoRenewRequest,
    SslCertificateResponse,
    SslCertificateUploadRequest,
    SslReplaceRequest,
)
from app.schemas.tenant.user import (
    TenantUserChangePasswordRequest,
    TenantUserCreateRequest,
    TenantUserLoginRequest,
    TenantUserResponse,
    TenantUserUpdateRequest,
)

__all__ = [
    # TenantAdmin
    "TenantAdminLoginRequest",
    "TenantAdminResponse",
    "TenantAdminCreateRequest",
    "TenantAdminUpdateRequest",
    "TenantAdminChangePasswordRequest",
    "TenantAdminUpdateProfileRequest",
    # TenantUser
    "TenantUserLoginRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
    # Role
    "TenantAdminRoleResponse",
    "TenantAdminRoleDetailResponse",
    "TenantAdminRoleTreeNode",
    "TenantAdminRoleCreateRequest",
    "TenantAdminRoleUpdateRequest",
    "TenantAdminRolePermissionsRequest",
    "TenantAdminRoleMoveRequest",
    "TenantAdminRoleSetLeaderRequest",
    "TenantAdminRoleAddMemberRequest",
    "TenantAdminRoleCreateMemberRequest",
    "TenantAdminRoleUpdateMemberRequest",
    "TenantAdminRoleResetPasswordRequest",
    "TenantAdminRoleToggleStatusRequest",
    "TenantAdminRoleMemberResponse",
    # Domain
    "TenantDomainSimpleResponse",
    "TenantDomainVerificationInfo",
    "TenantDomainResponse",
    "TenantDomainCreateRequest",
    "TenantDomainUpdateRequest",
    "TenantDomainVerifyRequest",
    "TenantSettingsResponse",
    "TenantSettingsUpdateRequest",
    # Plan
    "QuotaSchema",
    "FeaturesSchema",
    "TenantPlanResponse",
    "TenantPlanDetailResponse",
    "PermissionSimpleResponse",
    "TenantPlanCreateRequest",
    "TenantPlanUpdateRequest",
    "TenantPlanPermissionsRequest",
    "AttachmentAccessUrlResponse",
    # SSL
    "SslCertificateResponse",
    "SslCertificateUploadRequest",
    "SslAutoRenewRequest",
    "SslReplaceRequest",
]
