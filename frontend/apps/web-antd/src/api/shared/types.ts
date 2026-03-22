/**
 * Shared type definitions / 共享类型定义
 * Common types for multi-endpoint API / 用于多端 API 的通用类型
 */

import { resolveEndpointByPath } from '#/constants/endpoints';

/** Login request params / 登录请求参数 */
export interface LoginParams {
  username: string;
  password: string;
  /** Tenant code (optional, for scoping login) / 企业编码 */
  tenantCode?: string;
  /** Captcha challenge ID (optional) / 验证码挑战 ID */
  captchaChallengeId?: string;
  /** Captcha answer (optional) / 验证码答案 */
  captchaSolution?: string;
  /** Captcha provider code (optional) / 验证码提供方标识 */
  captchaProviderCode?: string;
  /** Captcha type (e.g. image) / 验证码类型 */
  captchaType?: string;
}

/** Login result (frontend format) / 登录响应 */
export interface LoginResult {
  accessToken: string;
  refreshToken?: string;
}

/** Login result (backend raw format) / 登录响应（后端原始格式） */
export interface LoginResultRaw {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
}

/** Refresh token request params / 刷新 Token 请求参数 */
export interface RefreshTokenParams {
  refreshToken: string;
}

/** Refresh token result (frontend format) / 刷新 Token 响应 */
export interface RefreshTokenResult {
  accessToken: string;
  refreshToken?: string;
}

/** Refresh token result (backend raw format) / 刷新 Token 响应（后端原始格式） */
export interface RefreshTokenResultRaw {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
}

/** Change password request params / 修改密码请求参数 */
export interface ChangePasswordParams {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
}

/** Base user info / 用户基本信息 */
export interface BaseUserInfo {
  id: number | string;
  username: string;
  realName: string;
  avatar?: string;
  email?: string;
  roles?: string[];
  /** Permission code list, for button-level access control / 权限码列表 */
  permissions?: string[];
  homePath?: string;
}

/** Platform admin info / 平台管理员信息 */
export interface AdminUserInfo extends BaseUserInfo {
  email?: string;
  isSuperAdmin?: boolean;
}

/** Tenant admin info / 企业管理员信息 */
export interface TenantAdminInfo extends BaseUserInfo {
  tenantId: number | string;
  tenantName?: string;
  email?: string;
  hasPlan: boolean;
  planName?: string;
}

/** Tenant user info / 企业用户信息 */
export interface TenantUserInfo extends BaseUserInfo {
  tenantId: number | string;
  email?: string;
}

/** API endpoint type / API 端类型 */
export type ApiEndpoint = 'admin' | 'tenant' | 'user';

/**
 * Get API endpoint type by route / 根据路由获取 API 端类型
 * @deprecated Use `getEndpointFromPath` or `getApiEndpoint` from '#/utils/endpoint'
 */
export function getApiEndpoint(path: string): ApiEndpoint {
  return resolveEndpointByPath(path);
}

/** 偏好 JSON 对象 / Preferences JSON object */
export type PreferencesData = Record<string, boolean | number | string>;
