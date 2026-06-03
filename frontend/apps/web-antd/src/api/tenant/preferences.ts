/**
 * Tenant preferences API / 租户端偏好设置 API
 * Backend: /tenant/preferences/*
 */
import type { PreferencesData } from '#/api/shared/types';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export type { PreferencesData };

/** 获取租户全局偏好 / Get tenant global preferences */
export async function getTenantGlobalPreferencesApi(
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.get<PreferencesData>(
    '/tenant/preferences/global',
    options,
  );
}

/** 更新租户全局偏好 / Update tenant global preferences */
export async function updateTenantGlobalPreferencesApi(
  preferences: PreferencesData,
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.put<PreferencesData>(
    '/tenant/preferences/global',
    { preferences },
    options,
  );
}

/** 获取当前租户管理员生效偏好 / Get current tenant admin effective preferences */
export async function getTenantMyPreferencesApi(
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.get<PreferencesData>(
    '/tenant/preferences/me',
    options,
  );
}

/** 更新当前租户管理员个人偏好 / Update current tenant admin individual preferences */
export async function updateTenantMyPreferencesApi(
  preferences: PreferencesData,
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.put<PreferencesData>(
    '/tenant/preferences/me',
    { preferences },
    options,
  );
}

/** 重置当前租户管理员偏好（恢复全局默认） / Reset current tenant admin preferences to global defaults */
export async function resetTenantMyPreferencesApi(
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.delete<PreferencesData>(
    '/tenant/preferences/me',
    options,
  );
}
