/**
 * 多端 Token 分离存储机制
 *
 * 设计目标：
 * - 平台管理端、租户管理端、租户用户端的 Token 互不干扰
 * - 登出一个端不影响其他端的登录状态
 * - 支持一键登录跳转功能（M2-T21）
 *
 * 存储 Key 规范：
 * - {namespace}_admin_token / {namespace}_admin_refresh_token
 * - {namespace}_tenant_admin_token / {namespace}_tenant_admin_refresh_token
 * - {namespace}_tenant_user_token / {namespace}_tenant_user_refresh_token
 */

import type { ApiEndpoint } from '#/api';

// ============================================================
// 存储 Key 后缀常量
// ============================================================

/** 平台管理端 Token Key */
export const ADMIN_TOKEN_KEY = 'admin_token';
/** 平台管理端 Refresh Token Key */
export const ADMIN_REFRESH_TOKEN_KEY = 'admin_refresh_token';

/** 租户管理端 Token Key */
export const TENANT_ADMIN_TOKEN_KEY = 'tenant_admin_token';
/** 租户管理端 Refresh Token Key */
export const TENANT_ADMIN_REFRESH_TOKEN_KEY = 'tenant_admin_refresh_token';

/** 租户用户端 Token Key */
export const TENANT_USER_TOKEN_KEY = 'tenant_user_token';
/** 租户用户端 Refresh Token Key */
export const TENANT_USER_REFRESH_TOKEN_KEY = 'tenant_user_refresh_token';

// ============================================================
// Token Key 映射表
// ============================================================

/** 各端 Access Token 存储 Key 映射 */
export const TOKEN_KEYS: Record<ApiEndpoint, string> = {
  admin: ADMIN_TOKEN_KEY,
  tenant: TENANT_ADMIN_TOKEN_KEY,
  user: TENANT_USER_TOKEN_KEY,
};

/** 各端 Refresh Token 存储 Key 映射 */
export const REFRESH_TOKEN_KEYS: Record<ApiEndpoint, string> = {
  admin: ADMIN_REFRESH_TOKEN_KEY,
  tenant: TENANT_ADMIN_REFRESH_TOKEN_KEY,
  user: TENANT_USER_REFRESH_TOKEN_KEY,
};

// ============================================================
// Token 存储数据结构
// ============================================================

/** 单端 Token 数据 */
export interface EndpointTokenData {
  accessToken: null | string;
  refreshToken: null | string;
}

/** 所有端的 Token 数据 */
export interface AllTokensData {
  admin: EndpointTokenData;
  tenant: EndpointTokenData;
  user: EndpointTokenData;
}

// ============================================================
// TokenStorage 工具类
// ============================================================

/**
 * Token 存储工具类
 *
 * 提供按端存取 Token 的功能，使用 localStorage 作为存储介质
 */
class TokenStorageClass {
  private namespace: string = '';

  /**
   * 清除所有端的 Token
   */
  clearAllTokens(): void {
    const endpoints: ApiEndpoint[] = ['admin', 'tenant', 'user'];
    for (const endpoint of endpoints) {
      this.clearToken(endpoint);
    }
  }

  /**
   * 清除指定端的所有 Token（Access Token + Refresh Token）
   * @param endpoint API 端类型
   */
  clearToken(endpoint: ApiEndpoint): void {
    const tokenKey = this.getFullKey(TOKEN_KEYS[endpoint]);
    const refreshTokenKey = this.getFullKey(REFRESH_TOKEN_KEYS[endpoint]);
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(refreshTokenKey);
  }

  // ============================================================
  // Access Token 操作
  // ============================================================

  /**
   * 获取所有端的 Token 数据
   */
  getAllTokensData(): AllTokensData {
    return {
      admin: this.getTokenData('admin'),
      tenant: this.getTokenData('tenant'),
      user: this.getTokenData('user'),
    };
  }

  /**
   * 获取所有已登录的端
   */
  getAuthenticatedEndpoints(): ApiEndpoint[] {
    const endpoints: ApiEndpoint[] = ['admin', 'tenant', 'user'];
    return endpoints.filter((endpoint) => this.hasToken(endpoint));
  }

  // ============================================================
  // Refresh Token 操作
  // ============================================================

  /**
   * 获取指定端的 Refresh Token
   * @param endpoint API 端类型
   */
  getRefreshToken(endpoint: ApiEndpoint): null | string {
    const key = this.getFullKey(REFRESH_TOKEN_KEYS[endpoint]);
    return localStorage.getItem(key);
  }

  /**
   * 获取指定端的 Access Token
   * @param endpoint API 端类型
   */
  getToken(endpoint: ApiEndpoint): null | string {
    const key = this.getFullKey(TOKEN_KEYS[endpoint]);
    return localStorage.getItem(key);
  }

  // ============================================================
  // 清除操作
  // ============================================================

  /**
   * 获取指定端的完整 Token 数据
   * @param endpoint API 端类型
   */
  getTokenData(endpoint: ApiEndpoint): EndpointTokenData {
    return {
      accessToken: this.getToken(endpoint),
      refreshToken: this.getRefreshToken(endpoint),
    };
  }

  /**
   * 检查指定端是否有有效的 Access Token
   * @param endpoint API 端类型
   */
  hasToken(endpoint: ApiEndpoint): boolean {
    const token = this.getToken(endpoint);
    return token !== null && token !== '';
  }

  // ============================================================
  // 状态查询
  // ============================================================

  /**
   * 初始化 namespace
   * 应在应用启动时调用（bootstrap.ts 中）
   */
  init(namespace: string): void {
    this.namespace = namespace;
  }

  /**
   * 设置指定端的 Refresh Token
   * @param endpoint API 端类型
   * @param token Refresh Token
   */
  setRefreshToken(endpoint: ApiEndpoint, token: string): void {
    const key = this.getFullKey(REFRESH_TOKEN_KEYS[endpoint]);
    localStorage.setItem(key, token);
  }

  /**
   * 设置指定端的 Access Token
   * @param endpoint API 端类型
   * @param token Access Token
   */
  setToken(endpoint: ApiEndpoint, token: string): void {
    const key = this.getFullKey(TOKEN_KEYS[endpoint]);
    localStorage.setItem(key, token);
  }

  /**
   * 获取带 namespace 前缀的完整存储 key
   */
  private getFullKey(key: string): string {
    if (!this.namespace) {
      console.warn(
        '[TokenStorage] namespace 未初始化，请先调用 TokenStorage.init()',
      );
      return key;
    }
    return `${this.namespace}_${key}`;
  }
}

// 导出单例实例
export const TokenStorage = new TokenStorageClass();
