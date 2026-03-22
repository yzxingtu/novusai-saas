/**
 * Multi-endpoint architecture - endpoint routing and path configuration
 * Unified management of route prefixes, login paths, home paths, etc. for each endpoint
 * 多端架构 - 端路由和路径配置
 * 统一管理各端的路由前缀、登录路径、首页路径等配置
 */

import type { ApiEndpoint, EndpointConfig } from '#/types/endpoint';

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

/** User legacy home alias / 用户端历史首页别名 */
export const USER_HOME_ALIAS_PATH = '/home';

// ============================================================
// API prefix constants / API 前缀常量
// ============================================================

/** Admin API prefix / 平台管理端 API 前缀 */
export const ADMIN_API_PREFIX = '/api/admin';

/** Tenant API prefix / 企业管理端 API 前缀 */
export const TENANT_API_PREFIX = '/api/tenant';

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
// Domain-aware endpoint resolver / 域名感知端解析器
// ============================================================

const LOCALHOST_HOSTNAMES = new Set(['127.0.0.1', '::1', 'localhost']);

function getCurrentHostname(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return (window.location.hostname || '').trim().toLowerCase();
}

function getPlatformDomainsFromEnv(): Set<string> {
  const raw = String(import.meta.env.VITE_PLATFORM_DOMAINS ?? '');
  const domains = raw
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  return new Set(domains);
}

function normalizePath(path: string): string {
  const [pathname = ''] = String(path || '').split(/[?#]/, 1);
  if (!pathname) {
    return '/';
  }
  return pathname.startsWith('/') ? pathname : `/${pathname}`;
}

function splitPathSuffix(path: string): { pathname: string; suffix: string } {
  const raw = String(path || '').trim();
  if (!raw) {
    return { pathname: '', suffix: '' };
  }

  const queryIndex = raw.indexOf('?');
  const hashIndex = raw.indexOf('#');
  const splitIndex =
    queryIndex === -1
      ? hashIndex
      : hashIndex === -1
        ? queryIndex
        : Math.min(queryIndex, hashIndex);

  if (splitIndex === -1) {
    return { pathname: raw, suffix: '' };
  }

  return {
    pathname: raw.slice(0, splitIndex),
    suffix: raw.slice(splitIndex),
  };
}

/**
 * Determine whether hostname should be treated as platform domain.
 * 判断域名是否应按平台域名处理。
 */
export function isPlatformHostname(hostname: string): boolean {
  const normalized = (hostname || '').trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  if (LOCALHOST_HOSTNAMES.has(normalized)) {
    return true;
  }
  return getPlatformDomainsFromEnv().has(normalized);
}

/**
 * Resolve endpoint owner for root path `/` by hostname.
 * 按域名解析根路径 `/` 的端归属。
 */
export function resolveRootEndpoint(hostname?: string): EndpointType {
  const currentHostname = (hostname ?? getCurrentHostname()).trim().toLowerCase();
  return isPlatformHostname(currentHostname)
    ? EndpointType.ADMIN
    : EndpointType.USER;
}

/**
 * Resolve endpoint from route path with root-domain ownership rule.
 * 基于路径并结合根路径域名归属规则解析端类型。
 */
export function resolveEndpointByPath(
  path: string,
  hostname?: string,
): EndpointType {
  const normalizedPath = normalizePath(path);

  if (normalizedPath.startsWith(ADMIN_ROUTE_PREFIX)) {
    return EndpointType.ADMIN;
  }
  if (normalizedPath.startsWith(TENANT_ROUTE_PREFIX)) {
    return EndpointType.TENANT;
  }
  if (normalizedPath === '/') {
    return resolveRootEndpoint(hostname);
  }
  return EndpointType.USER;
}

/**
 * Resolve login path for a route path.
 * 基于路由路径解析登录路径。
 */
export function resolveLoginPathByPath(
  path: string,
  hostname?: string,
): string {
  const endpoint = resolveEndpointByPath(path, hostname);
  return LOGIN_PATHS[endpoint];
}

/**
 * Resolve home path for a route path.
 * 基于路由路径解析首页路径。
 */
export function resolveHomePathByPath(path: string, hostname?: string): string {
  const endpoint = resolveEndpointByPath(path, hostname);
  return HOME_PATHS[endpoint];
}

/**
 * Normalize navigation target for an endpoint.
 * 规范化端内导航目标，收敛历史 `/home` 别名并阻止跨端错跳。
 */
export function normalizeEndpointNavigationPath(
  path: null | string | undefined,
  endpoint: ApiEndpoint,
  hostname?: string,
): string {
  const endpointKey = endpoint as EndpointType;
  const homePath = HOME_PATHS[endpointKey];
  const rawPath = String(path || '').trim();

  if (!rawPath) {
    return homePath;
  }

  const { pathname: rawPathname, suffix } = splitPathSuffix(rawPath);
  const pathname = normalizePath(rawPathname);

  if (endpointKey === EndpointType.USER && pathname === USER_HOME_ALIAS_PATH) {
    return `${USER_HOME_PATH}${suffix}`;
  }

  if (pathname === LOGIN_PATHS[endpointKey]) {
    return homePath;
  }

  if (endpointKey !== EndpointType.USER && pathname === USER_HOME_PATH) {
    return homePath;
  }

  const resolvedEndpoint = resolveEndpointByPath(pathname, hostname);
  if (resolvedEndpoint !== endpointKey) {
    return homePath;
  }

  return `${pathname}${suffix}`;
}

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
