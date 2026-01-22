/**
 * 多端架构 - 端工具函数
 *
 * 提供端检测、切换、判断等工具函数
 */

import type { ApiEndpoint, EndpointConfig } from '#/types/endpoint';

import {
  ADMIN_ROUTE_PREFIX,
  ENDPOINT_CONFIGS,
  HOME_PATHS,
  LOGIN_PATHS,
  TENANT_ROUTE_PREFIX,
} from '#/constants/endpoints';
import { ALL_ENDPOINTS, EndpointType, isValidEndpoint } from '#/types/endpoint';

// ============================================================
// 端检测函数
// ============================================================

/**
 * 根据路由路径获取端类型
 * @param path 路由路径
 * @returns 端类型
 */
export function getEndpointFromPath(path: string): EndpointType {
  if (path.startsWith(ADMIN_ROUTE_PREFIX)) {
    return EndpointType.ADMIN;
  }
  if (path.startsWith(TENANT_ROUTE_PREFIX)) {
    return EndpointType.TENANT;
  }
  return EndpointType.USER;
}

/**
 * 根据路由路径获取端类型（兼容旧代码的字符串字面量类型）
 * @param path 路由路径
 * @returns 端类型字符串
 * @deprecated 请使用 getEndpointFromPath 替代
 */
export function getApiEndpoint(path: string): ApiEndpoint {
  return getEndpointFromPath(path);
}

/**
 * 检查路径是否属于指定端
 * @param path 路由路径
 * @param endpoint 端类型
 */
export function isPathOfEndpoint(
  path: string,
  endpoint: EndpointType,
): boolean {
  return getEndpointFromPath(path) === endpoint;
}

/**
 * 检查路径是否为平台管理端路径
 * @param path 路由路径
 */
export function isAdminPath(path: string): boolean {
  return isPathOfEndpoint(path, EndpointType.ADMIN);
}

/**
 * 检查路径是否为租户管理端路径
 * @param path 路由路径
 */
export function isTenantPath(path: string): boolean {
  return isPathOfEndpoint(path, EndpointType.TENANT);
}

/**
 * 检查路径是否为用户端路径
 * @param path 路由路径
 */
export function isUserPath(path: string): boolean {
  return isPathOfEndpoint(path, EndpointType.USER);
}

// ============================================================
// 路径获取函数
// ============================================================

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

/**
 * 获取指定端的完整配置
 * @param endpoint 端类型
 */
export function getEndpointConfig(endpoint: EndpointType): EndpointConfig {
  return ENDPOINT_CONFIGS[endpoint];
}

// ============================================================
// 路径转换函数
// ============================================================

/**
 * 将路径从一个端转换到另一个端
 * @param path 原路径
 * @param fromEndpoint 源端类型
 * @param toEndpoint 目标端类型
 * @returns 转换后的路径
 *
 * @example
 * convertPath('/admin/dashboard', EndpointType.ADMIN, EndpointType.TENANT)
 * // 返回 '/tenant/dashboard'
 */
export function convertPath(
  path: string,
  fromEndpoint: EndpointType,
  toEndpoint: EndpointType,
): string {
  const fromConfig = getEndpointConfig(fromEndpoint);
  const toConfig = getEndpointConfig(toEndpoint);

  if (fromConfig.routePrefix && path.startsWith(fromConfig.routePrefix)) {
    return path.replace(fromConfig.routePrefix, toConfig.routePrefix);
  }

  return toConfig.routePrefix + path;
}

/**
 * 获取不带端前缀的相对路径
 * @param path 完整路径
 * @returns 相对路径
 *
 * @example
 * getRelativePath('/admin/system/user')
 * // 返回 '/system/user'
 */
export function getRelativePath(path: string): string {
  const endpoint = getEndpointFromPath(path);
  const config = getEndpointConfig(endpoint);

  if (config.routePrefix && path.startsWith(config.routePrefix)) {
    return path.slice(config.routePrefix.length) || '/';
  }

  return path;
}

// ============================================================
// 端遍历函数
// ============================================================

/**
 * 遍历所有端执行回调
 * @param callback 回调函数
 */
export function forEachEndpoint(
  callback: (endpoint: EndpointType, config: EndpointConfig) => void,
): void {
  for (const endpoint of ALL_ENDPOINTS) {
    callback(endpoint, ENDPOINT_CONFIGS[endpoint]);
  }
}

/**
 * 映射所有端到新数组
 * @param callback 映射函数
 */
export function mapEndpoints<T>(
  callback: (endpoint: EndpointType, config: EndpointConfig) => T,
): T[] {
  return ALL_ENDPOINTS.map((endpoint) =>
    callback(endpoint, ENDPOINT_CONFIGS[endpoint]),
  );
}

// ============================================================
// 类型导出（便于其他模块使用）
// ============================================================

export { ALL_ENDPOINTS, EndpointType, isValidEndpoint };
export type { ApiEndpoint, EndpointConfig };
