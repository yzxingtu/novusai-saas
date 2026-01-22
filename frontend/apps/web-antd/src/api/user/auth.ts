/**
 * 租户用户端认证 API
 * 对接后端 /api/v1/auth/* 接口
 */
import type {
  ChangePasswordParams,
  LoginParams,
  LoginResult,
  LoginResultRaw,
  RefreshTokenResult,
  RefreshTokenResultRaw,
  TenantUserInfo,
} from '../shared/types';

import type { ApiRequestOptions } from '#/utils/request';

import { useAccessStore } from '@vben/stores';

import { baseRequestClient, requestClient } from '#/utils/request';

// Logout 使用 baseRequestClient 避免 401 时循环调用

const API_PREFIX = '/api/v1/auth';

/**
 * 用户登录 (JSON 格式)
 * 后端返回 snake_case，转换为 camelCase
 */
export async function userLoginApi(
  data: LoginParams,
  options?: ApiRequestOptions,
): Promise<LoginResult> {
  const response = await requestClient.post<LoginResultRaw>(
    `${API_PREFIX}/login/json`,
    data,
    options,
  );
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
  };
}

/**
 * 刷新 Token
 * 后端返回 snake_case，转换为 camelCase
 */
export async function userRefreshTokenApi(
  refreshToken: string,
): Promise<RefreshTokenResult> {
  const response = await baseRequestClient.post<{
    data: RefreshTokenResultRaw;
  }>(`${API_PREFIX}/refresh`, {
    refresh_token: refreshToken,
  });
  const raw = (response as any).data;
  return {
    accessToken: raw.access_token,
    refreshToken: raw.refresh_token,
  };
}

/**
 * 用户登出
 * 使用 baseRequestClient 避免 401 时触发循环调用
 */
export async function userLogoutApi() {
  try {
    const accessStore = useAccessStore();
    const token = accessStore?.accessToken;
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    return await baseRequestClient.post(`${API_PREFIX}/logout`, undefined, {
      headers,
    });
  } catch {
    // 登出失败不影响主流程
  }
}

/**
 * 后端返回的用户信息原始格式
 */
interface UserInfoRaw {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active?: boolean;
  tenant_id?: number;
  role_id?: number;
  last_login_at?: string;
  created_at?: string;
  /** 权限码列表 */
  permissions?: string[];
}

/**
 * 获取当前用户信息
 * 将后端 snake_case 转换为前端 camelCase
 */
export async function getUserInfoApi(
  options?: ApiRequestOptions,
): Promise<TenantUserInfo> {
  const raw = await requestClient.get<UserInfoRaw>(`${API_PREFIX}/me`, options);
  return {
    id: raw.id,
    username: raw.username,
    realName: raw.nickname || raw.username,
    email: raw.email,
    avatar: raw.avatar,
    tenantId: raw.tenant_id || 0,
    roles: [],
    permissions: raw.permissions || [],
  };
}

/**
 * 修改密码
 */
export async function userChangePasswordApi(
  data: ChangePasswordParams,
  options?: ApiRequestOptions,
) {
  return requestClient.put(
    `${API_PREFIX}/password`,
    {
      old_password: data.oldPassword,
      new_password: data.newPassword,
      confirm_password: data.confirmPassword,
    },
    options,
  );
}
