/**
 * 多端架构 - 端路由和路径配置
 *
 * 统一管理各端的路由前缀、登录路径、首页路径等配置
 */

import type { EndpointConfig } from '#/types/endpoint';

import { EndpointType } from '#/types/endpoint';

// ============================================================
// 路由前缀常量
// ============================================================

/** 平台管理端路由前缀 */
export const ADMIN_ROUTE_PREFIX = '/admin';

/** 租户管理端路由前缀 */
export const TENANT_ROUTE_PREFIX = '/tenant';

/** 用户端路由前缀（根路径） */
export const USER_ROUTE_PREFIX = '';

// ============================================================
// 登录路径常量
// ============================================================

/** 平台管理端登录路径 */
export const ADMIN_LOGIN_PATH = '/admin/login';

/** 租户管理端登录路径 */
export const TENANT_LOGIN_PATH = '/tenant/login';

/** 用户端登录路径 */
export const USER_LOGIN_PATH = '/login';

// ============================================================
// 默认首页路径常量
// ============================================================

/** 平台管理端默认首页 */
export const ADMIN_HOME_PATH = '/admin/dashboard';

/** 租户管理端默认首页 */
export const TENANT_HOME_PATH = '/tenant/dashboard';

/** 用户端默认首页 */
export const USER_HOME_PATH = '/dashboard';

// ============================================================
// API 前缀常量
// ============================================================

/** 平台管理端 API 前缀 */
export const ADMIN_API_PREFIX = '/api/v1/admin';

/** 租户管理端 API 前缀 */
export const TENANT_API_PREFIX = '/api/v1/tenant';

/** 用户端 API 前缀 */
export const USER_API_PREFIX = '/api/v1/user';

// ============================================================
// 路径映射表
// ============================================================

/** 各端登录路径映射 */
export const LOGIN_PATHS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_LOGIN_PATH,
  [EndpointType.TENANT]: TENANT_LOGIN_PATH,
  [EndpointType.USER]: USER_LOGIN_PATH,
};

/** 各端默认首页路径映射 */
export const HOME_PATHS: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_HOME_PATH,
  [EndpointType.TENANT]: TENANT_HOME_PATH,
  [EndpointType.USER]: USER_HOME_PATH,
};

/** 各端路由前缀映射 */
export const ROUTE_PREFIXES: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_ROUTE_PREFIX,
  [EndpointType.TENANT]: TENANT_ROUTE_PREFIX,
  [EndpointType.USER]: USER_ROUTE_PREFIX,
};

/** 各端 API 前缀映射 */
export const API_PREFIXES: Record<EndpointType, string> = {
  [EndpointType.ADMIN]: ADMIN_API_PREFIX,
  [EndpointType.TENANT]: TENANT_API_PREFIX,
  [EndpointType.USER]: USER_API_PREFIX,
};

// ============================================================
// 完整端配置
// ============================================================

/** 各端完整配置 */
export const ENDPOINT_CONFIGS: Record<EndpointType, EndpointConfig> = {
  [EndpointType.ADMIN]: {
    apiPrefix: ADMIN_API_PREFIX,
    description: '平台超级管理员使用，管理租户、系统配置等',
    homePath: ADMIN_HOME_PATH,
    loginPath: ADMIN_LOGIN_PATH,
    name: '平台管理端',
    routePrefix: ADMIN_ROUTE_PREFIX,
    type: EndpointType.ADMIN,
  },
  [EndpointType.TENANT]: {
    apiPrefix: TENANT_API_PREFIX,
    description: '租户管理员使用，管理租户内部业务和用户',
    homePath: TENANT_HOME_PATH,
    loginPath: TENANT_LOGIN_PATH,
    name: '租户管理端',
    routePrefix: TENANT_ROUTE_PREFIX,
    type: EndpointType.TENANT,
  },
  [EndpointType.USER]: {
    apiPrefix: USER_API_PREFIX,
    description: '租户普通用户使用，使用租户提供的服务',
    homePath: USER_HOME_PATH,
    loginPath: USER_LOGIN_PATH,
    name: '用户端',
    routePrefix: USER_ROUTE_PREFIX,
    type: EndpointType.USER,
  },
};

/**
 * 获取指定端的配置
 * @param endpoint 端类型
 */
export function getEndpointConfig(endpoint: EndpointType): EndpointConfig {
  return ENDPOINT_CONFIGS[endpoint];
}

/**
 * 获取指定端的登录路径
 * @param endpoint 端类型
 */
export function getLoginPath(endpoint: EndpointType): string {
  return LOGIN_PATHS[endpoint];
}

/**
 * 获取指定端的首页路径
 * @param endpoint 端类型
 */
export function getHomePath(endpoint: EndpointType): string {
  return HOME_PATHS[endpoint];
}
