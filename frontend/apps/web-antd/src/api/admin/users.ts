import type { SelectResponse } from '#/api/shared/types';
/**
 * Platform admin user API / 平台管理员用户 API
 * Backend: /admin/users/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/users';

export interface AdminIdentitySelectExtra {
  ai_enabled?: boolean;
  ai_unavailable_reason?: null | string;
  avatar?: null | string;
  display_name?: null | string;
  effective_ai_enabled?: boolean;
  display_role_name?: null | string;
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

export interface AdminIdentityDetail {
  ai_enabled?: boolean;
  ai_unavailable_reason?: null | string;
  avatar?: null | string;
  created_at?: null | string;
  display_name?: null | string;
  effective_ai_enabled?: boolean;
  display_role_name?: null | string;
  email?: null | string;
  id: number;
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
  is_super?: boolean;
  last_login_at?: null | string;
  last_login_ip?: null | string;
  nickname?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  phone?: null | string;
  role_id?: null | number;
  role_name?: null | string;
  updated_at?: null | string;
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

/**
 * Get platform admin identity detail / 获取平台管理员身份详情
 * GET /admin/users/{user_id}
 */
export async function getAdminIdentityDetailApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<AdminIdentityDetail> {
  return requestClient.get<AdminIdentityDetail>(
    `${API_PREFIX}/${userId}`,
    options,
  );
}
