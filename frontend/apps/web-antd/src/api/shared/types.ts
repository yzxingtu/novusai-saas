/**
 * 共享类型定义
 * 用于多端 API 的通用类型
 */

/** 登录请求参数 */
export interface LoginParams {
  username: string;
  password: string;
}

/** 登录响应（前端使用） */
export interface LoginResult {
  accessToken: string;
  refreshToken?: string;
}

/** 登录响应（后端原始格式） */
export interface LoginResultRaw {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
}

/** 刷新 Token 请求参数 */
export interface RefreshTokenParams {
  refreshToken: string;
}

/** 刷新 Token 响应（前端使用） */
export interface RefreshTokenResult {
  accessToken: string;
  refreshToken?: string;
}

/** 刷新 Token 响应（后端原始格式） */
export interface RefreshTokenResultRaw {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
}

/** 修改密码请求参数 */
export interface ChangePasswordParams {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
}

/** 用户基本信息 */
export interface BaseUserInfo {
  id: number | string;
  username: string;
  realName: string;
  avatar?: string;
  email?: string;
  roles?: string[];
  /** 权限码列表，用于按钮级别权限控制 */
  permissions?: string[];
  homePath?: string;
}

/** 平台管理员信息 */
export interface AdminUserInfo extends BaseUserInfo {
  email?: string;
  isSuperAdmin?: boolean;
}

/** 租户管理员信息 */
export interface TenantAdminInfo extends BaseUserInfo {
  tenantId: number | string;
  tenantName?: string;
  email?: string;
}

/** 租户用户信息 */
export interface TenantUserInfo extends BaseUserInfo {
  tenantId: number | string;
  email?: string;
}

/** API 端类型 */
export type ApiEndpoint = 'admin' | 'tenant' | 'user';

/** 根据路由获取 API 端类型 */
export function getApiEndpoint(path: string): ApiEndpoint {
  if (path.startsWith('/admin')) {
    return 'admin';
  }
  if (path.startsWith('/tenant')) {
    return 'tenant';
  }
  return 'user';
}
