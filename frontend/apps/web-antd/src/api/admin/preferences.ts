/**
 * Platform admin preferences API / 平台管理端偏好设置 API
 * Backend: /admin/preferences/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

/** 偏好 JSON 对象 / Preferences JSON object */
export type PreferencesData = Record<string, boolean | number | string>;

/** 获取平台全局偏好 / Get platform global preferences */
export async function getAdminGlobalPreferencesApi(
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.get<PreferencesData>(
    '/admin/preferences/global',
    options,
  );
}

/** 更新平台全局偏好 / Update platform global preferences */
export async function updateAdminGlobalPreferencesApi(
  preferences: PreferencesData,
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.put<PreferencesData>(
    '/admin/preferences/global',
    { preferences },
    options,
  );
}

/** 获取当前管理员生效偏好 / Get current admin effective preferences */
export async function getAdminMyPreferencesApi(
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.get<PreferencesData>(
    '/admin/preferences/me',
    options,
  );
}

/** 更新当前管理员个人偏好 / Update current admin individual preferences */
export async function updateAdminMyPreferencesApi(
  preferences: PreferencesData,
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.put<PreferencesData>(
    '/admin/preferences/me',
    { preferences },
    options,
  );
}

/** 重置当前管理员偏好（恢复全局默认） / Reset current admin preferences to global defaults */
export async function resetAdminMyPreferencesApi(
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.delete<PreferencesData>(
    '/admin/preferences/me',
    options,
  );
}

/** 获取系统默认偏好 / Get system default preferences */
export async function getAdminDefaultPreferencesApi(
  options?: ApiRequestOptions,
): Promise<PreferencesData> {
  return await requestClient.get<PreferencesData>(
    '/admin/preferences/defaults',
    options,
  );
}
