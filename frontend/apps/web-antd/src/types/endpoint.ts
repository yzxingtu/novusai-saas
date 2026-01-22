/**
 * 多端架构 - 端类型定义
 *
 * 定义系统三端的类型枚举和相关接口
 * - ADMIN: 平台管理端（超级管理员、系统配置）
 * - TENANT: 租户管理端（租户后台、商户管理）
 * - USER: 用户端（租户C端用户）
 */

/**
 * 端类型枚举
 * 用于标识系统的三个端
 */
export enum EndpointType {
  /** 平台管理端 */
  ADMIN = 'admin',
  /** 租户管理端 */
  TENANT = 'tenant',
  /** 用户端 */
  USER = 'user',
}

/**
 * 端类型字面量类型
 * 兼容现有代码中使用的字符串字面量类型
 */
export type ApiEndpoint = `${EndpointType}`;

/**
 * 端配置接口
 */
export interface EndpointConfig {
  /** 端类型 */
  type: EndpointType;
  /** 端名称（用于显示） */
  name: string;
  /** 端描述 */
  description: string;
  /** 路由前缀 */
  routePrefix: string;
  /** 登录路径 */
  loginPath: string;
  /** 默认首页路径 */
  homePath: string;
  /** API 基础路径前缀 */
  apiPrefix: string;
}

/**
 * 端元数据（用于路由和权限判断）
 */
export interface EndpointMeta {
  /** 端类型 */
  endpoint: EndpointType;
  /** 是否需要认证 */
  requiresAuth: boolean;
  /** 所需角色（可选） */
  roles?: string[];
}

/**
 * 所有端类型数组（用于遍历）
 */
export const ALL_ENDPOINTS: EndpointType[] = [
  EndpointType.ADMIN,
  EndpointType.TENANT,
  EndpointType.USER,
];

/**
 * 检查是否为有效的端类型
 */
export function isValidEndpoint(value: string): value is ApiEndpoint {
  return ALL_ENDPOINTS.includes(value as EndpointType);
}
