/**
 * Multi-endpoint architecture - endpoint type definitions
 * 多端架构 - 端类型定义
 *
 * Defines type enums and related interfaces for the three system endpoints
 * 定义系统三端的类型枚举和相关接口
 * - ADMIN: Platform admin (super admin, system configuration) / 平台管理端（超级管理员、系统配置）
 * - TENANT: Tenant admin (tenant backend, merchant management) / 租户管理端（租户后台、商户管理）
 * - USER: User-facing (tenant end-users) / 用户端（租户C端用户）
 */

/**
 * Endpoint type enum
 * Identifies the three system endpoints
 * 端类型枚举
 * 用于标识系统的三个端
 */
export enum EndpointType {
  /** Platform admin / 平台管理端 */
  ADMIN = 'admin',
  /** Tenant admin / 租户管理端 */
  TENANT = 'tenant',
  /** User-facing / 用户端 */
  USER = 'user',
}

/**
 * Endpoint type literal type
 * Compatible with string literal types used in existing code
 * 端类型字面量类型
 * 兼容现有代码中使用的字符串字面量类型
 */
export type ApiEndpoint = `${EndpointType}`;

/**
 * Endpoint configuration interface
 * 端配置接口
 */
export interface EndpointConfig {
  /** Endpoint type / 端类型 */
  type: EndpointType;
  /** Endpoint name (for display) / 端名称（用于显示） */
  name: string;
  /** Endpoint description / 端描述 */
  description: string;
  /** Route prefix / 路由前缀 */
  routePrefix: string;
  /** Login path / 登录路径 */
  loginPath: string;
  /** Default home path / 默认首页路径 */
  homePath: string;
  /** API base path prefix / API 基础路径前缀 */
  apiPrefix: string;
}

/**
 * Endpoint metadata (for routing and permission checks)
 * 端元数据（用于路由和权限判断）
 */
export interface EndpointMeta {
  /** Endpoint type / 端类型 */
  endpoint: EndpointType;
  /** Whether authentication is required / 是否需要认证 */
  requiresAuth: boolean;
  /** Required roles (optional) / 所需角色（可选） */
  roles?: string[];
}

/**
 * All endpoint types array (for iteration)
 * 所有端类型数组（用于遍历）
 */
export const ALL_ENDPOINTS: EndpointType[] = [
  EndpointType.ADMIN,
  EndpointType.TENANT,
  EndpointType.USER,
];

/**
 * Check if value is a valid endpoint type
 * 检查是否为有效的端类型
 */
export function isValidEndpoint(value: string): value is ApiEndpoint {
  return ALL_ENDPOINTS.includes(value as EndpointType);
}
