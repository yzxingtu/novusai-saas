"""
企业 Schema 模块 / Tenant Schema Module

导出企业相关的 Schema
Exports tenant related schemas.
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
    DevHostDomainStatus,
    DevHostMutationResponse,
    DevHostsRuntimeInfo,
    DevHostsStatusResponse,
    DevHostsSyncAllResponse,
    TenantDomainCreateRequest,
    TenantDomainResponse,
    TenantDomainSimpleResponse,
    TenantDomainUpdateRequest,
    TenantDomainVerificationInfo,
    TenantDomainVerifyRequest,
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
from app.schemas.tenant.tenant_permission_role import (
    TenantPermissionRoleCreateRequest,
    TenantPermissionRoleDetailResponse,
    TenantPermissionRolePermissionsRequest,
    TenantPermissionRoleResponse,
    TenantPermissionRoleUpdateRequest,
)
from app.schemas.tenant.tenant_org_node import (
    TenantOrgNodeAssignMemberRequest,
    TenantOrgNodeAuthorityPolicyRequest,
    TenantOrgNodeCreateMemberRequest,
    TenantOrgNodeCreateRequest,
    TenantOrgNodeDetailResponse,
    TenantOrgNodeLeaderResponse,
    TenantOrgNodeMemberResponse,
    TenantOrgNodeMoveRequest,
    TenantOrgNodeResetPasswordRequest,
    TenantOrgNodeResponse,
    TenantOrgNodeSetLeaderRequest,
    TenantOrgNodeToggleStatusRequest,
    TenantOrgNodeType,
    TenantOrgNodeUpdateMemberRequest,
    TenantOrgNodeUpdateRequest,
)
from app.schemas.tenant.ssl import (
    SslAutoRenewRequest,
    SslCertificateResponse,
    SslCertificateUploadRequest,
    SslReplaceRequest,
)
from app.schemas.tenant.user_role import (
    TenantUserRoleCreateRequest,
    TenantUserRoleDetailResponse,
    TenantUserRolePermissionsRequest,
    TenantUserRoleResponse,
    TenantUserRoleUpdateRequest,
)
from app.schemas.tenant.user import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TenantUserChangePasswordRequest,
    TenantUserCreateRequest,
    TenantUserLoginRequest,
    TenantUserProfileUpdateRequest,
    TenantUserRegisterRequest,
    TenantUserResponse,
    TenantUserUpdateRequest,
)

__all__ = [
    # TenantAdmin / 企业管理员
    "TenantAdminLoginRequest",
    "TenantAdminResponse",
    "TenantAdminCreateRequest",
    "TenantAdminUpdateRequest",
    "TenantAdminChangePasswordRequest",
    "TenantAdminUpdateProfileRequest",
    # TenantUser / 企业用户
    "TenantUserLoginRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
    "TenantUserRegisterRequest",
    "TenantUserProfileUpdateRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    # TenantOrgNode / 企业组织节点
    "TenantOrgNodeResponse",
    "TenantOrgNodeDetailResponse",
    "TenantOrgNodeCreateRequest",
    "TenantOrgNodeUpdateRequest",
    "TenantOrgNodeAuthorityPolicyRequest",
    "TenantOrgNodeMoveRequest",
    "TenantOrgNodeSetLeaderRequest",
    "TenantOrgNodeAssignMemberRequest",
    "TenantOrgNodeCreateMemberRequest",
    "TenantOrgNodeUpdateMemberRequest",
    "TenantOrgNodeResetPasswordRequest",
    "TenantOrgNodeToggleStatusRequest",
    "TenantOrgNodeMemberResponse",
    "TenantOrgNodeLeaderResponse",
    "TenantOrgNodeType",
    # TenantPermissionRole / 企业权限角色
    "TenantPermissionRoleResponse",
    "TenantPermissionRoleDetailResponse",
    "TenantPermissionRoleCreateRequest",
    "TenantPermissionRoleUpdateRequest",
    "TenantPermissionRolePermissionsRequest",
    # TenantUserRole / 企业用户角色
    "TenantUserRoleResponse",
    "TenantUserRoleDetailResponse",
    "TenantUserRoleCreateRequest",
    "TenantUserRoleUpdateRequest",
    "TenantUserRolePermissionsRequest",
    # Domain / 域名
    "TenantDomainSimpleResponse",
    "TenantDomainVerificationInfo",
    "TenantDomainResponse",
    "DevHostsRuntimeInfo",
    "DevHostDomainStatus",
    "DevHostsStatusResponse",
    "DevHostMutationResponse",
    "DevHostsSyncAllResponse",
    "TenantDomainCreateRequest",
    "TenantDomainUpdateRequest",
    "TenantDomainVerifyRequest",
    # Plan / 套餐
    "QuotaSchema",
    "FeaturesSchema",
    "TenantPlanResponse",
    "TenantPlanDetailResponse",
    "PermissionSimpleResponse",
    "TenantPlanCreateRequest",
    "TenantPlanUpdateRequest",
    "TenantPlanPermissionsRequest",
    "AttachmentAccessUrlResponse",
    # SSL / 证书
    "SslCertificateResponse",
    "SslCertificateUploadRequest",
    "SslAutoRenewRequest",
    "SslReplaceRequest",
]
