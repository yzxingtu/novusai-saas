/**
 * Multi-endpoint token separated storage / 多端 Token 分离存储机制
 *
 * Design goals / 设计目标：
 * - Admin, tenant admin, and tenant user tokens don't interfere with each other.
 * - Logging out of one endpoint doesn't affect others.
 * - Supports impersonate login (M2-T21).
 *
 * Storage key convention / 存储 Key 规范：
 * - {namespace}_admin_token / {namespace}_admin_refresh_token
 * - {namespace}_tenant_admin_token / {namespace}_tenant_admin_refresh_token
 * - {namespace}_tenant_user_token / {namespace}_tenant_user_refresh_token
 */

import type { ApiEndpoint } from '#/api';

// ============================================================
// Storage key suffix constants / 存储 Key 后缀常量
// ============================================================

/** Admin token key / 平台管理端 Token Key */
export const ADMIN_TOKEN_KEY = 'admin_token';
/** Admin refresh token key / 平台管理端 Refresh Token Key */
export const ADMIN_REFRESH_TOKEN_KEY = 'admin_refresh_token';

/** Tenant admin token key / 租户管理端 Token Key */
export const TENANT_ADMIN_TOKEN_KEY = 'tenant_admin_token';
/** Tenant admin refresh token key / 租户管理端 Refresh Token Key */
export const TENANT_ADMIN_REFRESH_TOKEN_KEY = 'tenant_admin_refresh_token';

/** Tenant user token key / 租户用户端 Token Key */
export const TENANT_USER_TOKEN_KEY = 'tenant_user_token';
/** Tenant user refresh token key / 租户用户端 Refresh Token Key */
export const TENANT_USER_REFRESH_TOKEN_KEY = 'tenant_user_refresh_token';

// ============================================================
// Token key mapping / Token Key 映射表
// ============================================================

/** Access token storage key mapping per endpoint / 各端 Access Token 存储 Key 映射 */
export const TOKEN_KEYS: Record<ApiEndpoint, string> = {
  admin: ADMIN_TOKEN_KEY,
  tenant: TENANT_ADMIN_TOKEN_KEY,
  user: TENANT_USER_TOKEN_KEY,
};

/** Refresh token storage key mapping per endpoint / 各端 Refresh Token 存储 Key 映射 */
export const REFRESH_TOKEN_KEYS: Record<ApiEndpoint, string> = {
  admin: ADMIN_REFRESH_TOKEN_KEY,
  tenant: TENANT_ADMIN_REFRESH_TOKEN_KEY,
  user: TENANT_USER_REFRESH_TOKEN_KEY,
};

// ============================================================
// Token storage data structures / Token 存储数据结构
// ============================================================

/** Single endpoint token data / 单端 Token 数据 */
export interface EndpointTokenData {
  accessToken: null | string;
  refreshToken: null | string;
}

/** All endpoints token data / 所有端的 Token 数据 */
export interface AllTokensData {
  admin: EndpointTokenData;
  tenant: EndpointTokenData;
  user: EndpointTokenData;
}

// ============================================================
// TokenStorage utility class / TokenStorage 工具类
// ============================================================

/**
 * Token storage utility class / Token 存储工具类
 *
 * Provides per-endpoint token storage using localStorage.
 * 提供按端存取 Token 的功能。
 */
class TokenStorageClass {
  private namespace: string = '';

  /**
   * Clear all endpoints' tokens / 清除所有端的 Token
   */
  clearAllTokens(): void {
    const endpoints: ApiEndpoint[] = ['admin', 'tenant', 'user'];
    for (const endpoint of endpoints) {
      this.clearToken(endpoint);
    }
  }

  /**
   * Clear specified endpoint's tokens (Access + Refresh) / 清除指定端 Token
   * @param endpoint API endpoint type / API 端类型
   */
  clearToken(endpoint: ApiEndpoint): void {
    const tokenKey = this.getFullKey(TOKEN_KEYS[endpoint]);
    const refreshTokenKey = this.getFullKey(REFRESH_TOKEN_KEYS[endpoint]);
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(refreshTokenKey);
  }

  // ============================================================
  // Access token operations / Access Token 操作
  // ============================================================

  /**
   * Get all endpoints' token data / 获取所有端的 Token 数据
   */
  getAllTokensData(): AllTokensData {
    return {
      admin: this.getTokenData('admin'),
      tenant: this.getTokenData('tenant'),
      user: this.getTokenData('user'),
    };
  }

  /**
   * Get all authenticated endpoints / 获取所有已登录的端
   */
  getAuthenticatedEndpoints(): ApiEndpoint[] {
    const endpoints: ApiEndpoint[] = ['admin', 'tenant', 'user'];
    return endpoints.filter((endpoint) => this.hasToken(endpoint));
  }

  // ============================================================
  // Refresh token operations / Refresh Token 操作
  // ============================================================

  /**
   * Get specified endpoint's refresh token / 获取指定端 Refresh Token
   * @param endpoint API endpoint type / API 端类型
   */
  getRefreshToken(endpoint: ApiEndpoint): null | string {
    const key = this.getFullKey(REFRESH_TOKEN_KEYS[endpoint]);
    return localStorage.getItem(key);
  }

  /**
   * Get specified endpoint's access token / 获取指定端 Access Token
   * @param endpoint API endpoint type / API 端类型
   */
  getToken(endpoint: ApiEndpoint): null | string {
    const key = this.getFullKey(TOKEN_KEYS[endpoint]);
    return localStorage.getItem(key);
  }

  // ============================================================
  // Clear operations / 清除操作
  // ============================================================

  /**
   * Get specified endpoint's full token data / 获取指定端的完整 Token 数据
   * @param endpoint API endpoint type / API 端类型
   */
  getTokenData(endpoint: ApiEndpoint): EndpointTokenData {
    return {
      accessToken: this.getToken(endpoint),
      refreshToken: this.getRefreshToken(endpoint),
    };
  }

  /**
   * Check if specified endpoint has a valid access token / 检查指定端是否有有效 Token
   * @param endpoint API endpoint type / API 端类型
   */
  hasToken(endpoint: ApiEndpoint): boolean {
    const token = this.getToken(endpoint);
    return token !== null && token !== '';
  }

  // ============================================================
  // State queries / 状态查询
  // ============================================================

  /**
   * Initialize namespace (should be called at app startup in bootstrap.ts)
   * 初始化 namespace（应在应用启动时调用）
   */
  init(namespace: string): void {
    this.namespace = namespace;
  }

  /**
   * Set specified endpoint's refresh token / 设置指定端 Refresh Token
   * @param endpoint API endpoint type / API 端类型
   * @param token Refresh Token
   */
  setRefreshToken(endpoint: ApiEndpoint, token: string): void {
    const key = this.getFullKey(REFRESH_TOKEN_KEYS[endpoint]);
    localStorage.setItem(key, token);
  }

  /**
   * Set specified endpoint's access token / 设置指定端 Access Token
   * @param endpoint API endpoint type / API 端类型
   * @param token Access Token
   */
  setToken(endpoint: ApiEndpoint, token: string): void {
    const key = this.getFullKey(TOKEN_KEYS[endpoint]);
    localStorage.setItem(key, token);
  }

  /**
   * Get full storage key with namespace prefix / 获取带 namespace 前缀的完整 key
   */
  private getFullKey(key: string): string {
    if (!this.namespace) {
      console.warn(
        '[TokenStorage] namespace not initialized, call TokenStorage.init() first / namespace 未初始化',
      );
      return key;
    }
    return `${this.namespace}_${key}`;
  }
}

// Export singleton instance / 导出单例实例
export const TokenStorage = new TokenStorageClass();
