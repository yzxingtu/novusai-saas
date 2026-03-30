/**
 * Platform admin user API / 平台管理员用户 API
 * Backend: /admin/users/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/users';

/**
 * Force logout platform admin / 强制下线平台管理员
 * POST /admin/users/{user_id}/force-logout
 */
export async function forceLogoutAdminApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `${API_PREFIX}/${userId}/force-logout`,
    {},
    options,
  );
}
