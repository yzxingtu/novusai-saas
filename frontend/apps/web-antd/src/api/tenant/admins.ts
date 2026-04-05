import type { SelectResponse } from '#/api/shared/types';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const API_PREFIX = '/tenant/admins';

export interface TenantAdminIdentitySelectExtra {
  avatar?: null | string;
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
