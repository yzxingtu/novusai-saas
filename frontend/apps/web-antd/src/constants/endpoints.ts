/**
 * Multi-endpoint architecture - endpoint routing and path configuration
 * Unified management of route prefixes, login paths, home paths, etc. for each endpoint
 * 多端架构 - 端路由和路径配置
 * 统一管理各端的路由前缀、登录路径、首页路径等配置
 */

import type { EndpointConfig } from '#/types/endpoint';

import { EndpointType } from '#/types/endpoint';

// ============================================================
// Route prefix constants / 路由前缀常量
// ============================================================

/** Admin route prefix / 平台管理端路由前缀 */
export const ADMIN_ROUTE_PREFIX = '/admin';

/** Tenant route prefix / 企业管理端路由前缀 */
export const TENANT_ROUTE_PREFIX = '/tenant';

/** User route prefix (root path) / 用户端路由前缀（根路径） */
export const USER_ROUTE_PREFIX = '';

// ============================================================
// Login path constants / 登录路径常量
// ============================================================

/** Admin login path / 平台管理端登录路径 */
export const ADMIN_LOGIN_PATH = '/admin/login';

/** Tenant login path / 企业管理端登录路径 */
export const TENANT_LOGIN_PATH = '/tenant/login';

/** User login path / 用户端登录路径 */
export const USER_LOGIN_PATH = '/auth/login';

// ============================================================
// Default home path constants / 默认首页路径常量
// ============================================================

/** Admin default home / 平台管理端默认首页 */
export const ADMIN_HOME_PATH = '/admin/dashboard';

/** Tenant default home / 企业管理端默认首页 */
export const TENANT_HOME_PATH = '/tenant/dashboard';

/** User default home / 用户端默认首页 */
export const USER_HOME_PATH = '/';

// ============================================================
// API prefix constants / API 前缀常量
// ============================================================

/** Admin API prefix / 平台管理端 API 前缀 */
export const ADMIN_API_PREFIX = '/api/v1/admin';

/** Tenant API prefix / 企业管理端 API 前缀 */
export const TENANT_API_PREFIX = '/api/v1/tenant';

/** User API prefix / 用户端 API 前缀 */
export const USER_API_PREFIX = '/api/user';

// ============================================================
// Path mapping tables / 路径映射表
// ============================================================

/** Login path mapping for each endpoint / 各端登录路径映射 */
export const LOGIN_PATHS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_LOGIN_PATH,
  [EndpointType.TENANT]: TENANT_LOGIN_PATH,
  [EndpointType.USER]: USER_LOGIN_PATH,
};

/** Default home path mapping for each endpoint / 各端默认首页路径映射 */
export const HOME_PATHS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_HOME_PATH,
  [EndpointType.TENANT]: TENANT_HOME_PATH,
  [EndpointType.USER]: USER_HOME_PATH,
};

/** Route prefix mapping for each endpoint / 各端路由前缀映射 */
export const ROUTE_PREFIXES: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_ROUTE_PREFIX,
  [EndpointType.TENANT]: TENANT_ROUTE_PREFIX,
  [EndpointType.USER]: USER_ROUTE_PREFIX,
};

/** API prefix mapping for each endpoint / 各端 API 前缀映射 */
export const API_PREFIXES: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_API_PREFIX,
  [EndpointType.TENANT]: TENANT_API_PREFIX,
  [EndpointType.USER]: USER_API_PREFIX,
};

// ============================================================
// Full endpoint configuration / 完整端配置
// ============================================================

/** Full configuration for each endpoint / 各端完整配置 */
export const ENDPOINT_CONFIGS: Record<EndpointType, EndpointConfig> = {
  [EndpointType.ADMIN]: {
    apiPrefix: ADMIN_API_PREFIX,
    description: 'Platform super-admin portal for tenant and system management',
    homePath: ADMIN_HOME_PATH,
    loginPath: ADMIN_LOGIN_PATH,
    name: 'Platform Admin',
    routePrefix: ADMIN_ROUTE_PREFIX,
    type: EndpointType.ADMIN,
  },
  [EndpointType.TENANT]: {
    apiPrefix: TENANT_API_PREFIX,
    description: 'Tenant admin portal for tenant-level users and business',
    homePath: TENANT_HOME_PATH,
    loginPath: TENANT_LOGIN_PATH,
    name: 'Tenant Admin',
    routePrefix: TENANT_ROUTE_PREFIX,
    type: EndpointType.TENANT,
  },
  [EndpointType.USER]: {
    apiPrefix: USER_API_PREFIX,
    description: 'End-user portal for tenant-provided services',
    homePath: USER_HOME_PATH,
    loginPath: USER_LOGIN_PATH,
    name: 'User',
    routePrefix: USER_ROUTE_PREFIX,
    type: EndpointType.USER,
  },
};

/**
 * Get configuration for a specific endpoint
 * 获取指定端的配置
 * @param endpoint - Endpoint type / 端类型
 */
export function getEndpointConfig(endpoint: EndpointType): EndpointConfig {
  return ENDPOINT_CONFIGS[endpoint];
}

/**
 * Get login path for a specific endpoint
 * 获取指定端的登录路径
 * @param endpoint - Endpoint type / 端类型
 */
export function getLoginPath(endpoint: EndpointType): string {
  return LOGIN_PATHS[endpoint];
}

/**
 * Get home path for a specific endpoint
 * 获取指定端的首页路径
 * @param endpoint - Endpoint type / 端类型
 */
export function getHomePath(endpoint: EndpointType): string {
  return HOME_PATHS[endpoint];
}
