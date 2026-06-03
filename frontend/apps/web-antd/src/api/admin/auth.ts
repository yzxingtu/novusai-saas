/**
 * Platform admin authentication API / 平台管理端认证 API
 * Backend: /admin/auth/*
 */
import type {
  AdminUserInfo,
  AIAvailabilityInfo,
  AIAvailabilityRawFields,
  ChangePasswordParams,
  LoginParams,
  LoginResult,
  LoginResultRaw,
  RefreshTokenResult,
  RefreshTokenResultRaw,
} from '../shared/types';

import type { ApiRequestOptions } from '#/utils/request';

import { TokenStorage } from '#/store/shared/token-storage';
import { baseRequestClient, requestClient } from '#/utils/request';

// Logout uses baseRequestClient to avoid circular calls on 401 / Logout 使用 baseRequestClient 避免 401 时循环调用

const API_PREFIX = '/admin/auth';

/**
 * Admin login / 管理员登录
 * Backend returns snake_case, converted to camelCase
 */
export async function adminLoginApi(
  data: LoginParams,
  options?: ApiRequestOptions,
): Promise<LoginResult> {
  // Build request body, convert to snake_case / 构建请求体，转换为 snake_case
  const requestBody: Record<string, unknown> = {
    password: data.password,
    username: data.username,
  };

  // Add captcha params if present / 添加验证码参数（如果有）
  if (data.captchaChallengeId) {
    requestBody.captcha_challenge_id = data.captchaChallengeId;
  }
  if (data.captchaSolution) {
    requestBody.captcha_solution = data.captchaSolution;
  }
  if (data.captchaProviderCode) {
    requestBody.captcha_provider_code = data.captchaProviderCode;
  }
  if (data.captchaType) {
    requestBody.captcha_type = data.captchaType;
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
 * Backend returns snake_case, converted to camelCase
 */
export async function adminRefreshTokenApi(
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
 * Admin logout / 管理员登出
 * Uses baseRequestClient to avoid circular calls on 401
 */
export async function adminLogoutApi() {
  try {
    const token = TokenStorage.getToken('admin');
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    return await baseRequestClient.post(`${API_PREFIX}/logout`, undefined, {
      headers,
    });
  } catch {
    // Logout failure doesn't affect main flow / 登出失败不影响主流程
  }
}

/**
 * Raw admin user info format from backend / 后端返回的管理员信息原始格式
 */
interface AdminUserInfoRaw extends AIAvailabilityRawFields {
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
  /** Permission code list / 权限码列表 */
  permissions?: string[];
}

function mapAdminAIAvailability(
  raw: AIAvailabilityRawFields,
): AIAvailabilityInfo {
  const accountAIEnabled = raw.ai_enabled ?? true;
  const tenantPlanAIEnabled = true;
  const aiChatEnabled =
    raw.effective_ai_enabled ??
    raw.ai_chat_enabled ??
    (accountAIEnabled && tenantPlanAIEnabled);

  return {
    accountAIEnabled,
    aiChatEnabled,
    aiUnavailableReason: raw.ai_unavailable_reason ?? undefined,
    tenantPlanAIEnabled,
  };
}

/**
 * Get current admin info / 获取当前管理员信息
 * Converts backend snake_case to frontend camelCase
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
    ...mapAdminAIAvailability(raw),
    isSuperAdmin: raw.is_super,
    roles: raw.is_super ? ['super_admin'] : [],
    // Super admin has all permissions; regular admin uses backend permission codes / 超级管理员拥有所有权限，普通管理员使用后端返回的权限码
    permissions: raw.is_super ? ['*'] : raw.permissions || [],
  };
}

/**
 * Change password / 修改密码
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

/** Update profile params / 修改个人信息参数 */
export interface UpdateAdminProfileParams {
  nickname?: null | string;
  avatar?: null | string;
  email?: null | string;
  phone?: null | string;
}

/**
 * Update current admin profile / 修改当前管理员个人信息
 * PUT /admin/auth/profile
 */
export async function updateAdminProfileApi(
  data: UpdateAdminProfileParams,
  options?: ApiRequestOptions,
) {
  return requestClient.put(`${API_PREFIX}/profile`, data, options);
}
