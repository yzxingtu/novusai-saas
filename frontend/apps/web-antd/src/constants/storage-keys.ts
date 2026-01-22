/**
 * 多端架构 - 存储键名常量
 *
 * 统一管理各端的 Token、用户信息等存储键名
 * 命名规范：{namespace}_{endpoint}_{type}
 */

import { EndpointType } from '#/types/endpoint';

// ============================================================
// Token 存储键后缀
// ============================================================

/** 平台管理端 Access Token Key */
export const ADMIN_TOKEN_KEY = 'admin_token';
/** 平台管理端 Refresh Token Key */
export const ADMIN_REFRESH_TOKEN_KEY = 'admin_refresh_token';

/** 租户管理端 Access Token Key */
export const TENANT_TOKEN_KEY = 'tenant_admin_token';
/** 租户管理端 Refresh Token Key */
export const TENANT_REFRESH_TOKEN_KEY = 'tenant_admin_refresh_token';

/** 用户端 Access Token Key */
export const USER_TOKEN_KEY = 'tenant_user_token';
/** 用户端 Refresh Token Key */
export const USER_REFRESH_TOKEN_KEY = 'tenant_user_refresh_token';

// ============================================================
// 用户信息存储键后缀
// ============================================================

/** 平台管理端用户信息 Key */
export const ADMIN_USER_INFO_KEY = 'admin_user_info';

/** 租户管理端用户信息 Key */
export const TENANT_USER_INFO_KEY = 'tenant_admin_user_info';

/** 用户端用户信息 Key */
export const USER_USER_INFO_KEY = 'tenant_user_info';

// ============================================================
// 其他存储键后缀
// ============================================================

/** 平台管理端权限码 Key */
export const ADMIN_PERMISSIONS_KEY = 'admin_permissions';

/** 租户管理端权限码 Key */
export const TENANT_PERMISSIONS_KEY = 'tenant_admin_permissions';

/** 用户端权限码 Key */
export const USER_PERMISSIONS_KEY = 'tenant_user_permissions';

/** 租户信息 Key（租户端和用户端共享） */
export const TENANT_INFO_KEY = 'tenant_info';

/** 应用设置 Key */
export const APP_SETTINGS_KEY = 'app_settings';

/** 主题设置 Key */
export const THEME_KEY = 'theme';

/** 语言设置 Key */
export const LOCALE_KEY = 'locale';

// ============================================================
// Token Key 映射表
// ============================================================

/** 各端 Access Token 存储 Key 映射 */
export const TOKEN_KEYS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_TOKEN_KEY,
  [EndpointType.TENANT]: TENANT_TOKEN_KEY,
  [EndpointType.USER]: USER_TOKEN_KEY,
};

/** 各端 Refresh Token 存储 Key 映射 */
export const REFRESH_TOKEN_KEYS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_REFRESH_TOKEN_KEY,
  [EndpointType.TENANT]: TENANT_REFRESH_TOKEN_KEY,
  [EndpointType.USER]: USER_REFRESH_TOKEN_KEY,
};

/** 各端用户信息存储 Key 映射 */
export const USER_INFO_KEYS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_USER_INFO_KEY,
  [EndpointType.TENANT]: TENANT_USER_INFO_KEY,
  [EndpointType.USER]: USER_USER_INFO_KEY,
};

/** 各端权限码存储 Key 映射 */
export const PERMISSIONS_KEYS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_PERMISSIONS_KEY,
  [EndpointType.TENANT]: TENANT_PERMISSIONS_KEY,
  [EndpointType.USER]: USER_PERMISSIONS_KEY,
};

// ============================================================
// 工具函数
// ============================================================

/**
 * 获取指定端的 Token Key
 * @param endpoint 端类型
 */
export function getTokenKey(endpoint: EndpointType): string {
  return TOKEN_KEYS[endpoint];
}

/**
 * 获取指定端的 Refresh Token Key
 * @param endpoint 端类型
 */
export function getRefreshTokenKey(endpoint: EndpointType): string {
  return REFRESH_TOKEN_KEYS[endpoint];
}

/**
 * 获取指定端的用户信息 Key
 * @param endpoint 端类型
 */
export function getUserInfoKey(endpoint: EndpointType): string {
  return USER_INFO_KEYS[endpoint];
}

/**
 * 获取指定端的权限码 Key
 * @param endpoint 端类型
 */
export function getPermissionsKey(endpoint: EndpointType): string {
  return PERMISSIONS_KEYS[endpoint];
}
