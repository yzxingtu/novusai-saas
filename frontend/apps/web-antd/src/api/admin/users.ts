import type { SelectResponse } from '#/api/shared/types';
/**
 * Platform admin user API / 平台管理员用户 API
 * Backend: /admin/users/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/users';

export interface AdminIdentitySelectExtra {
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
 * Force logout platform admin / 强制下线平台管理员
 * POST /admin/users/{user_id}/force-logout
 */
export async function forceLogoutAdminApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(`${API_PREFIX}/${userId}/force-logout`, {}, options);
}

/**
 * Get platform admin identity select options / 获取平台管理员身份下拉
 * GET /admin/users/select
 */
export async function getAdminIdentitySelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SelectResponse<AdminIdentitySelectExtra>> {
  return requestClient.get<SelectResponse<AdminIdentitySelectExtra>>(
    `${API_PREFIX}/select`,
    { params, ...options },
  );
}
