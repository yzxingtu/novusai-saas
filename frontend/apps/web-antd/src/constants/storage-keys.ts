/**
 * Multi-endpoint architecture - storage key constants
 * Unified management of Token, user info, and other storage keys for each endpoint
 * Naming convention: {namespace}_{endpoint}_{type}
 * 多端架构 - 存储键名常量
 * 统一管理各端的 Token、用户信息等存储键名
 * 命名规范：{namespace}_{endpoint}_{type}
 */

import { EndpointType } from '#/types/endpoint';

// ============================================================
// Token storage key suffixes / Token 存储键后缀
// ============================================================

/** Admin Access Token Key / 平台管理端 Access Token Key */
export const ADMIN_TOKEN_KEY = 'admin_token';
/** Admin Refresh Token Key / 平台管理端 Refresh Token Key */
export const ADMIN_REFRESH_TOKEN_KEY = 'admin_refresh_token';

/** Tenant Access Token Key / 企业管理端 Access Token Key */
export const TENANT_TOKEN_KEY = 'tenant_admin_token';
/** Tenant Refresh Token Key / 企业管理端 Refresh Token Key */
export const TENANT_REFRESH_TOKEN_KEY = 'tenant_admin_refresh_token';

/** User Access Token Key / 用户端 Access Token Key */
export const USER_TOKEN_KEY = 'tenant_user_token';
/** User Refresh Token Key / 用户端 Refresh Token Key */
export const USER_REFRESH_TOKEN_KEY = 'tenant_user_refresh_token';

// ============================================================
// User info storage key suffixes / 用户信息存储键后缀
// ============================================================

/** Admin user info Key / 平台管理端用户信息 Key */
export const ADMIN_USER_INFO_KEY = 'admin_user_info';

/** Tenant user info Key / 企业管理端用户信息 Key */
export const TENANT_USER_INFO_KEY = 'tenant_admin_user_info';

/** User user info Key / 用户端用户信息 Key */
export const USER_USER_INFO_KEY = 'tenant_user_info';

// ============================================================
// Other storage key suffixes / 其他存储键后缀
// ============================================================

/** Admin permissions Key / 平台管理端权限码 Key */
export const ADMIN_PERMISSIONS_KEY = 'admin_permissions';

/** Tenant permissions Key / 企业管理端权限码 Key */
export const TENANT_PERMISSIONS_KEY = 'tenant_admin_permissions';

/** User permissions Key / 用户端权限码 Key */
export const USER_PERMISSIONS_KEY = 'tenant_user_permissions';

/** Tenant info Key (shared between tenant and user endpoints) / 企业信息 Key（企业端和用户端共享） */
export const TENANT_INFO_KEY = 'tenant_info';

/** App settings Key / 应用设置 Key */
export const APP_SETTINGS_KEY = 'app_settings';

/** Theme settings Key / 主题设置 Key */
export const THEME_KEY = 'theme';

/** Locale settings Key / 语言设置 Key */
export const LOCALE_KEY = 'locale';

// ============================================================
// Token Key mapping tables / Token Key 映射表
// ============================================================

/** Access Token storage Key mapping for each endpoint / 各端 Access Token 存储 Key 映射 */
export const TOKEN_KEYS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_TOKEN_KEY,
  [EndpointType.TENANT]: TENANT_TOKEN_KEY,
  [EndpointType.USER]: USER_TOKEN_KEY,
};

/** Refresh Token storage Key mapping for each endpoint / 各端 Refresh Token 存储 Key 映射 */
export const REFRESH_TOKEN_KEYS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_REFRESH_TOKEN_KEY,
  [EndpointType.TENANT]: TENANT_REFRESH_TOKEN_KEY,
  [EndpointType.USER]: USER_REFRESH_TOKEN_KEY,
};

/** User info storage Key mapping for each endpoint / 各端用户信息存储 Key 映射 */
export const USER_INFO_KEYS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_USER_INFO_KEY,
  [EndpointType.TENANT]: TENANT_USER_INFO_KEY,
  [EndpointType.USER]: USER_USER_INFO_KEY,
};

/** Permissions storage Key mapping for each endpoint / 各端权限码存储 Key 映射 */
export const PERMISSIONS_KEYS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_PERMISSIONS_KEY,
  [EndpointType.TENANT]: TENANT_PERMISSIONS_KEY,
  [EndpointType.USER]: USER_PERMISSIONS_KEY,
};

// ============================================================
// Utility functions / 工具函数
// ============================================================

/**
 * Get Token Key for a specific endpoint
 * 获取指定端的 Token Key
 * @param endpoint - Endpoint type / 端类型
 */
export function getTokenKey(endpoint: EndpointType): string {
  return TOKEN_KEYS[endpoint];
}

/**
 * Get Refresh Token Key for a specific endpoint
 * 获取指定端的 Refresh Token Key
 * @param endpoint - Endpoint type / 端类型
 */
export function getRefreshTokenKey(endpoint: EndpointType): string {
  return REFRESH_TOKEN_KEYS[endpoint];
}

/**
 * Get user info Key for a specific endpoint
 * 获取指定端的用户信息 Key
 * @param endpoint - Endpoint type / 端类型
 */
export function getUserInfoKey(endpoint: EndpointType): string {
  return USER_INFO_KEYS[endpoint];
}

/**
 * Get permissions Key for a specific endpoint
 * 获取指定端的权限码 Key
 * @param endpoint - Endpoint type / 端类型
 */
export function getPermissionsKey(endpoint: EndpointType): string {
  return PERMISSIONS_KEYS[endpoint];
}
