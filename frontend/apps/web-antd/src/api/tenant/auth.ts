/**
 * Tenant backend auth API / 租户后台认证 API
 * Backend: /tenant/auth/* / 对接后端 /tenant/auth/* 接口
 */
import type {
  ChangePasswordParams,
  LoginParams,
  LoginResult,
  LoginResultRaw,
  RefreshTokenResult,
  RefreshTokenResultRaw,
  TenantAdminInfo,
} from '../shared/types';

import type { ApiRequestOptions, HttpResponse } from '#/utils/request';

import { useAccessStore } from '@vben/stores';

import { $t } from '#/locales';
import { baseRequestClient, requestClient } from '#/utils/request';

// Logout uses baseRequestClient to avoid circular calls on 401 / 登出使用 baseRequestClient 避免循环调用

const API_PREFIX = '/tenant/auth';

/**
 * Tenant admin login / 租户管理员登录
 * Backend returns snake_case, converted to camelCase / 后端返回 snake_case，转换为 camelCase
 */
export async function tenantLoginApi(
  data: LoginParams,
  options?: ApiRequestOptions,
): Promise<LoginResult> {
  // Build request body, convert to snake_case / 构建请求体
  const requestBody: Record<string, unknown> = {
    password: data.password,
    username: data.username,
  };

  // Add tenant code (if present) / 添加租户编码
  if (data.tenantCode) {
    requestBody.tenant_code = data.tenantCode;
  }

  // Add captcha params (if present) / 添加验证码参数
  if (data.captchaChallengeId) {
    requestBody.captcha_challenge_id = data.captchaChallengeId;
  }
  if (data.captchaSolution) {
    requestBody.captcha_solution = data.captchaSolution;
  }
  if (data.captchaProviderCode) {
    requestBody.captcha_provider_code = data.captchaProviderCode;
  }

  const response = await requestClient.post<LoginResultRaw>(
    `${API_PREFIX}/login`,
    requestBody,
    options,
  );
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
  };
}

/**
 * Refresh token / 刷新 Token
 * Backend returns snake_case, converted to camelCase / 后端返回 snake_case，转换为 camelCase
 */
export async function tenantRefreshTokenApi(
  refreshToken: string,
): Promise<RefreshTokenResult> {
  const response = await baseRequestClient.post<RefreshTokenResultRaw>(
    `${API_PREFIX}/refresh`,
    { refresh_token: refreshToken },
  );
  const responseData = (response as unknown as { data: HttpResponse<RefreshTokenResultRaw> })
    .data;
  if (responseData.code !== 0) {
    throw new Error(
      responseData.message || $t('tenant.impersonate.refreshFailed'),
    );
  }
  const raw = responseData.data;
  return {
    accessToken: raw.access_token,
    refreshToken: raw.refresh_token,
  };
}

/**
 * Tenant admin logout / 租户管理员登出
 * Uses baseRequestClient to avoid circular calls on 401 / 使用 baseRequestClient 避免循环调用
 */
export async function tenantLogoutApi() {
  try {
    const accessStore = useAccessStore();
    const token = accessStore?.accessToken;
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    return await baseRequestClient.post(`${API_PREFIX}/logout`, undefined, {
      headers,
    });
  } catch {
    // Logout failure won't affect main flow / 登出失败不影响主流程
  }
}

/**
 * Tenant admin info raw format from backend / 后端返回的租户管理员信息原始格式
 */
interface TenantAdminInfoRaw {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active?: boolean;
  tenant_id?: number;
  tenant_name?: string;
  role_id?: number;
  last_login_at?: string;
  created_at?: string;
  /** Permission code list / 权限码列表 */
  permissions?: string[];
  /** Whether tenant has assigned plan / 租户是否已分配套餐 */
  has_plan?: boolean;
  /** Plan name / 套餐名称 */
  plan_name?: string;
}

/**
 * Get current tenant admin info / 获取当前租户管理员信息
 * Convert backend snake_case to frontend camelCase / 将后端格式转换为前端格式
 */
export async function getTenantAdminInfoApi(
  options?: ApiRequestOptions,
): Promise<TenantAdminInfo> {
  const raw = await requestClient.get<TenantAdminInfoRaw>(
    `${API_PREFIX}/me`,
    options,
  );
  return {
    id: raw.id,
    username: raw.username,
    realName: raw.nickname || raw.username,
    email: raw.email,
    avatar: raw.avatar,
    tenantId: raw.tenant_id || 0,
    tenantName: raw.tenant_name,
    roles: [],
    permissions: raw.permissions || [],
    hasPlan: raw.has_plan ?? true,
    planName: raw.plan_name,
  };
}

/**
 * Change password / 修改密码
 */
export async function tenantChangePasswordApi(
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

// ============================================================
// Profile update / 个人信息修改
// ============================================================

/** Update profile params / 修改个人信息参数 */
export interface UpdateProfileParams {
  nickname?: null | string;
  avatar?: null | string;
  email?: null | string;
  phone?: null | string;
}

/**
 * Update current tenant admin profile / 修改当前租户管理员个人信息
 * PUT /tenant/auth/profile
 */
export async function updateTenantProfileApi(
  data: UpdateProfileParams,
  options?: ApiRequestOptions,
) {
  return requestClient.put(`${API_PREFIX}/profile`, data, options);
}

// ============================================================
// Admin impersonate login / 平台管理员一键登录
// ============================================================

/** Impersonate token verification request / 一键登录 Token 验证请求 */
export interface ImpersonateTokenRequest {
  impersonate_token: string;
}

/**
 * Admin impersonate login / 平台管理员一键登录
 * POST /tenant/auth/impersonate
 * Verify impersonate token and exchange for formal token / 验证 impersonate token 并换取正式 Token
 */
export async function impersonateLoginApi(
  impersonateToken: string,
): Promise<LoginResult> {
  const response = await baseRequestClient.post<LoginResultRaw>(
    `${API_PREFIX}/impersonate`,
    { impersonate_token: impersonateToken },
  );
  const responseData = (response as unknown as { data: HttpResponse<LoginResultRaw> }).data;
  if (responseData.code !== 0) {
    throw new Error(
      responseData.message || $t('tenant.impersonate.loginFailed'),
    );
  }
  const raw = responseData.data;
  return {
    accessToken: raw.access_token,
    refreshToken: raw.refresh_token,
  };
}
