import type { SelectResponse } from '#/api/shared/types';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const API_PREFIX = '/tenant/admins';

export interface TenantAdminIdentitySelectExtra {
  avatar?: null | string;
  display_name?: null | string;
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
  nickname?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  role_name?: null | string;
  user_type?: null | string;
  username?: null | string;
}

export interface TenantAdminIdentityDetail {
  avatar?: null | string;
  created_at?: null | string;
  display_name?: null | string;
  email?: null | string;
  id: number;
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
  last_login_at?: null | string;
  last_login_ip?: null | string;
  nickname?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  permission_role_id?: null | number;
  permission_role_name?: null | string;
  phone?: null | string;
  role_id?: null | number;
  role_name?: null | string;
  tenant_id?: null | number;
  updated_at?: null | string;
  user_type?: null | string;
  username?: null | string;
}

/**
 * Get tenant admin identity select options / 获取企业管理员身份下拉
 * GET /tenant/admins/select
 */
export async function getTenantAdminIdentitySelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SelectResponse<TenantAdminIdentitySelectExtra>> {
  return requestClient.get<SelectResponse<TenantAdminIdentitySelectExtra>>(
    `${API_PREFIX}/select`,
    { params, ...options },
  );
}

/**
 * Get tenant admin identity detail / 获取企业管理员身份详情
 * GET /tenant/admins/{admin_id}
 */
export async function getTenantAdminIdentityDetailApi(
  adminId: number,
  options?: ApiRequestOptions,
): Promise<TenantAdminIdentityDetail> {
  return requestClient.get<TenantAdminIdentityDetail>(
    `${API_PREFIX}/${adminId}`,
    options,
  );
}
