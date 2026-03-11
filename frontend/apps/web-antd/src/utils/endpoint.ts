/**
 * Multi-endpoint architecture - endpoint utility functions
 * 多端架构 - 端工具函数
 *
 * Provides endpoint detection, switching, and checking utilities.
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
// Endpoint detection functions / 端检测函数
// ============================================================

/**
 * Get endpoint type from route path
 * 根据路由路径获取端类型
 *
 * @param path - Route path / 路由路径
 * @returns Endpoint type / 端类型
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
 * Get endpoint type from route path (legacy string literal type for backward compatibility)
 * 根据路由路径获取端类型（兼容旧代码的字符串字面量类型）
 *
 * @param path - Route path / 路由路径
 * @returns Endpoint type string / 端类型字符串
 * @deprecated Use getEndpointFromPath instead / 请使用 getEndpointFromPath 替代
 */
export function getApiEndpoint(path: string): ApiEndpoint {
  return getEndpointFromPath(path);
}

/**
 * Check if a path belongs to the specified endpoint
 * 检查路径是否属于指定端
 *
 * @param path - Route path / 路由路径
 * @param endpoint - Endpoint type / 端类型
 */
export function isPathOfEndpoint(
  path: string,
  endpoint: EndpointType,
): boolean {
  return getEndpointFromPath(path) === endpoint;
}

/**
 * Check if the path is an admin endpoint path
 * 检查路径是否为平台管理端路径
 *
 * @param path - Route path / 路由路径
 */
export function isAdminPath(path: string): boolean {
  return isPathOfEndpoint(path, EndpointType.ADMIN);
}

/**
 * Check if the path is a tenant endpoint path
 * 检查路径是否为租户管理端路径
 *
 * @param path - Route path / 路由路径
 */
export function isTenantPath(path: string): boolean {
  return isPathOfEndpoint(path, EndpointType.TENANT);
}

/**
 * Check if the path is a user endpoint path
 * 检查路径是否为用户端路径
 *
 * @param path - Route path / 路由路径
 */
export function isUserPath(path: string): boolean {
  return isPathOfEndpoint(path, EndpointType.USER);
}

// ============================================================
// Path retrieval functions / 路径获取函数
// ============================================================

/**
 * Get login path for the specified endpoint
 * 获取指定端的登录路径
 *
 * @param endpoint - Endpoint type / 端类型
 */
export function getLoginPath(endpoint: EndpointType): string {
  return LOGIN_PATHS[endpoint];
}

/**
 * Get home page path for the specified endpoint
 * 获取指定端的首页路径
 *
 * @param endpoint - Endpoint type / 端类型
 */
export function getHomePath(endpoint: EndpointType): string {
  return HOME_PATHS[endpoint];
}

/**
 * Get full configuration for the specified endpoint
 * 获取指定端的完整配置
 *
 * @param endpoint - Endpoint type / 端类型
 */
export function getEndpointConfig(endpoint: EndpointType): EndpointConfig {
  return ENDPOINT_CONFIGS[endpoint];
}

// ============================================================
// Path conversion functions / 路径转换函数
// ============================================================

/**
 * Convert path from one endpoint to another
 * 将路径从一个端转换到另一个端
 *
 * @param path - Original path / 原路径
 * @param fromEndpoint - Source endpoint type / 源端类型
 * @param toEndpoint - Target endpoint type / 目标端类型
 * @returns Converted path / 转换后的路径
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
 * Get relative path without endpoint prefix
 * 获取不带端前缀的相对路径
 *
 * @param path - Full path / 完整路径
 * @returns Relative path / 相对路径
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
// Endpoint iteration functions / 端遍历函数
// ============================================================

/**
 * Iterate over all endpoints and execute callback
 * 遍历所有端执行回调
 *
 * @param callback - Callback function / 回调函数
 */
export function forEachEndpoint(
  callback: (endpoint: EndpointType, config: EndpointConfig) => void,
): void {
  for (const endpoint of ALL_ENDPOINTS) {
    callback(endpoint, ENDPOINT_CONFIGS[endpoint]);
  }
}

/**
 * Map all endpoints to a new array
 * 映射所有端到新数组
 *
 * @param callback - Mapping function / 映射函数
 */
export function mapEndpoints<T>(
  callback: (endpoint: EndpointType, config: EndpointConfig) => T,
): T[] {
  return ALL_ENDPOINTS.map((endpoint) =>
    callback(endpoint, ENDPOINT_CONFIGS[endpoint]),
  );
}

// ============================================================
// Type exports (for other modules) / 类型导出（便于其他模块使用）
// ============================================================

export { ALL_ENDPOINTS, EndpointType, isValidEndpoint };
export type { ApiEndpoint, EndpointConfig };
