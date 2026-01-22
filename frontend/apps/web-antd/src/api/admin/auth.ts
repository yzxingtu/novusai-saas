/**
 * 平台管理端认证 API
 * 对接后端 /admin/auth/* 接口
 */
import type {
  AdminUserInfo,
  ChangePasswordParams,
  LoginParams,
  LoginResult,
  LoginResultRaw,
  RefreshTokenResult,
  RefreshTokenResultRaw,
} from '../shared/types';

import type { ApiRequestOptions } from '#/utils/request';

import { useAccessStore } from '@vben/stores';

import { baseRequestClient, requestClient } from '#/utils/request';

// Logout 使用 baseRequestClient 避免 401 时循环调用

const API_PREFIX = '/admin/auth';

/**
 * 管理员登录
 * 后端返回 snake_case，转换为 camelCase
 */
export async function adminLoginApi(
  data: LoginParams,
  options?: ApiRequestOptions,
): Promise<LoginResult> {
  const response = await requestClient.post<LoginResultRaw>(
    `${API_PREFIX}/login`,
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
export async function adminRefreshTokenApi(
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
 * 管理员登出
 * 使用 baseRequestClient 避免 401 时触发循环调用
 */
export async function adminLogoutApi() {
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
 * 后端返回的管理员信息原始格式
 */
interface AdminUserInfoRaw {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active?: boolean;
  is_super?: boolean;
  role_id?: number;
  last_login_at?: string;
  created_at?: string;
  /** 权限码列表 */
  permissions?: string[];
}

/**
 * 获取当前管理员信息
 * 将后端 snake_case 转换为前端 camelCase
 */
export async function getAdminInfoApi(
  options?: ApiRequestOptions,
): Promise<AdminUserInfo> {
  const raw = await requestClient.get<AdminUserInfoRaw>(
    `${API_PREFIX}/me`,
    options,
  );
  return {
    id: raw.id,
    username: raw.username,
    realName: raw.nickname || raw.username,
    email: raw.email,
    avatar: raw.avatar,
    isSuperAdmin: raw.is_super,
    roles: raw.is_super ? ['super_admin'] : [],
    // 超级管理员拥有所有权限，普通管理员使用后端返回的权限码
    permissions: raw.is_super ? ['*'] : raw.permissions || [],
  };
}

/**
 * 修改密码
 */
export async function adminChangePasswordApi(
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
