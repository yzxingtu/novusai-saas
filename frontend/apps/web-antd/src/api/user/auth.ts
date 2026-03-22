/**
 * Tenant user auth API / 企业用户端认证 API
 * Backend: /api/user/auth/* / 对接后端 /api/user/auth/* 接口
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

// Logout uses baseRequestClient to avoid circular calls on 401 / Logout 使用 baseRequestClient 避免 401 时循环调用

const API_PREFIX = '/api/user/auth';

/**
 * User login (JSON format) / 用户登录 (JSON 格式)
 * Backend returns snake_case, converted to camelCase / 后端返回 snake_case，转换为 camelCase
 */
export async function userLoginApi(
  data: LoginParams,
  options?: ApiRequestOptions,
): Promise<LoginResult> {
  // Build request body, convert to snake_case / 构建请求体，转换为 snake_case
  const requestBody: Record<string, unknown> = {
    password: data.password,
    username: data.username,
  };

  // Add tenant code (if present) / 添加企业编码（如果有）
  if (data.tenantCode) {
    requestBody.tenant_code = data.tenantCode;
  }

  // Add captcha params (if present) / 添加验证码参数（如果有）
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
    `${API_PREFIX}/login/json`,
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
export async function userRefreshTokenApi(
  refreshToken: string,
): Promise<RefreshTokenResult> {
  const response = await baseRequestClient.post<RefreshTokenResultRaw>(
    `${API_PREFIX}/refresh`,
    {
      refresh_token: refreshToken,
    },
  );
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
  };
}

/**
 * User logout / 用户登出
 * Uses baseRequestClient to avoid circular calls on 401 / 使用 baseRequestClient 避免 401 时触发循环调用
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
    // Logout failure does not affect main flow / 登出失败不影响主流程
  }
}

/**
 * User info raw format from backend / 后端返回的用户信息原始格式
 */
interface UserInfoRaw {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  gender?: number;
  is_active?: boolean;
  approval_status?: string;
  tenant_id?: number;
  role_id?: number;
  role_name?: string;
  last_login_at?: string;
  created_at?: string;
  updated_at?: string;
  /** Permission code list / 权限码列表 */
  permissions?: string[];
}

/**
 * User full profile info (frontend format) / 用户完整资料信息（前端格式）
 */
export interface UserProfileInfo {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  gender?: number;
  isActive?: boolean;
  approvalStatus?: string;
  tenantId?: number;
  roleId?: number;
  roleName?: string;
  lastLoginAt?: string;
  createdAt?: string;
  updatedAt?: string;
}

/**
 * Get current user info / 获取当前用户信息
 * Converts backend snake_case to frontend camelCase / 将后端 snake_case 转换为前端 camelCase
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
 * Get current user full profile / 获取当前用户完整资料
 */
export async function getUserProfileApi(
  options?: ApiRequestOptions,
): Promise<UserProfileInfo> {
  const raw = await requestClient.get<UserInfoRaw>(`${API_PREFIX}/me`, options);
  return {
    id: raw.id,
    username: raw.username,
    nickname: raw.nickname,
    email: raw.email,
    phone: raw.phone,
    avatar: raw.avatar,
    gender: raw.gender,
    isActive: raw.is_active,
    approvalStatus: raw.approval_status,
    tenantId: raw.tenant_id,
    roleId: raw.role_id,
    roleName: raw.role_name,
    lastLoginAt: raw.last_login_at,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/**
 * Update profile params / 更新个人资料参数
 */
export interface UpdateProfileParams {
  avatar?: string;
  email?: string;
  gender?: number;
  nickname?: string;
  phone?: string;
}

/**
 * Update user profile / 更新个人资料
 */
export async function updateUserProfileApi(
  data: UpdateProfileParams,
  options?: ApiRequestOptions,
): Promise<UserProfileInfo> {
  const raw = await requestClient.put<UserInfoRaw>(
    `${API_PREFIX}/profile`,
    data,
    options,
  );
  return {
    id: raw.id,
    username: raw.username,
    nickname: raw.nickname,
    email: raw.email,
    phone: raw.phone,
    avatar: raw.avatar,
    gender: raw.gender,
    isActive: raw.is_active,
    approvalStatus: raw.approval_status,
    tenantId: raw.tenant_id,
    roleId: raw.role_id,
    roleName: raw.role_name,
    lastLoginAt: raw.last_login_at,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/**
 * Register params / 注册参数
 */
export interface RegisterParams {
  captchaChallengeId?: string;
  captchaProviderCode?: string;
  captchaSolution?: string;
  captchaType?: string;
  confirmPassword: string;
  email: string;
  nickname?: string;
  password: string;
  phone?: string;
  tenantCode?: string;
  username: string;
}

/**
 * Register result (backend raw format) / 注册结果（后端原始格式）
 */
interface RegisterResultRaw {
  approval_status?: string;
  id?: number;
  message?: string;
  username?: string;
}

/**
 * Register result / 注册结果
 */
export interface RegisterResult {
  approvalStatus?: string;
  id?: number;
  message?: string;
  username?: string;
}

/**
 * User register / 用户注册
 */
export async function userRegisterApi(
  data: RegisterParams,
  options?: ApiRequestOptions,
): Promise<RegisterResult> {
  const requestBody: Record<string, unknown> = {
    confirm_password: data.confirmPassword,
    email: data.email,
    password: data.password,
    username: data.username,
  };

  if (data.tenantCode) {
    requestBody.tenant_code = data.tenantCode;
  }
  if (data.phone) {
    requestBody.phone = data.phone;
  }
  if (data.nickname) {
    requestBody.nickname = data.nickname;
  }
  if (data.captchaChallengeId) {
    requestBody.captcha_challenge_id = data.captchaChallengeId;
  }
  if (data.captchaSolution) {
    requestBody.captcha_solution = data.captchaSolution;
  }
  if (data.captchaType) {
    requestBody.captcha_type = data.captchaType;
  }
  if (data.captchaProviderCode) {
    requestBody.captcha_provider_code = data.captchaProviderCode;
  }

  const response = await baseRequestClient.post<RegisterResultRaw>(
    `${API_PREFIX}/register`,
    requestBody,
    options,
  );

  return {
    approvalStatus: response.approval_status,
    id: response.id,
    message: response.message,
    username: response.username,
  };
}

/**
 * Forgot password params / 忘记密码参数
 */
export interface ForgotPasswordParams {
  email: string;
  tenantCode?: string;
}

/**
 * Reset password params / 重置密码参数
 */
export interface ResetPasswordParams {
  code: string;
  confirmPassword: string;
  email: string;
  newPassword: string;
  tenantCode?: string;
}

/**
 * Forgot password - send verification code / 忘记密码 - 发送验证码
 */
export async function userForgotPasswordApi(
  data: ForgotPasswordParams,
  options?: ApiRequestOptions,
) {
  const requestBody: Record<string, unknown> = {
    channel: 'email',
    email: data.email,
  };

  if (data.tenantCode) {
    requestBody.tenant_code = data.tenantCode;
  }

  return requestClient.post(
    `${API_PREFIX}/forgot-password`,
    requestBody,
    options,
  );
}

/**
 * Reset password / 重置密码
 */
export async function userResetPasswordApi(
  data: ResetPasswordParams,
  options?: ApiRequestOptions,
) {
  const requestBody: Record<string, unknown> = {
    code: data.code,
    confirm_password: data.confirmPassword,
    email: data.email,
    new_password: data.newPassword,
  };

  if (data.tenantCode) {
    requestBody.tenant_code = data.tenantCode;
  }

  return requestClient.post(
    `${API_PREFIX}/reset-password`,
    requestBody,
    options,
  );
}

/**
 * Change password / 修改密码
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
