import type { ApiRequestOptions } from '#/utils/request';
import type {
  TenantUserInfo,
  TenantUserInfoRaw,
} from '#/api/tenant/tenant-users';

import { requestClient } from '#/utils/request';

import { transformUserInfo } from '#/api/tenant/tenant-users';

const API_PREFIX = '/admin/tenants';

/**
 * Get tenant user identity detail / 获取企业用户身份详情（管理端）
 * GET /admin/tenants/{tenant_id}/users/{user_id}
 */
export async function getAdminTenantUserIdentityDetailApi(
  tenantId: number,
  userId: number,
  options?: ApiRequestOptions,
): Promise<TenantUserInfo> {
  const raw = await requestClient.get<TenantUserInfoRaw>(
    `${API_PREFIX}/${tenantId}/users/${userId}`,
    options,
  );
  return transformUserInfo(raw);
}
