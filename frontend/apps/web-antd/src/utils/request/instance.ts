import type { ApiEndpoint, RefreshTokenResultRaw } from './types';

/**
 * Request instance configuration
 * 请求实例配置
 *
 * Creates and configures requestClient instance with:
 * - Multi-endpoint Token management
 * - Request/response interceptors
 * - Error handling
 * 创建并配置 requestClient 实例，集成：
 * - 多端 Token 管理
 * - 请求/响应拦截器
 * - 错误处理
 *
 * @module utils/request/instance
 */
import { useAppConfig } from '@vben/hooks';
import { $t } from '@vben/locales';
import { preferences } from '@vben/preferences';
import { useAccessStore } from '@vben/stores';

import { message } from 'ant-design-vue';

import {
  LOGIN_PATHS,
  resolveEndpointByPath,
  USER_HOME_ALIAS_PATH,
  USER_HOME_PATH,
} from '#/constants/endpoints';
import { TokenStorage } from '#/store/shared/token-storage';

import {
  createAuthInterceptor,
  createBusinessErrorInterceptor,
  createErrorMessageInterceptor,
  createLoadingInterceptor,
  createRequestInterceptor,
  createResponseDataInterceptor,
  createSuccessMessageInterceptor,
} from './interceptors';
import { RequestClient } from './request-client';

// ============================================================
// Configuration / 配置
// ============================================================

const { apiURL: rawApiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

/**
 * In dev mode, replace 127.0.0.1 with current page hostname,
 * ensuring API requests carry the correct Host header (tenant domain isolation relies on Host header).
 * Example: as.dakkii.cn:5666 → API sends to as.dakkii.cn:8000
 * Dev 模式下使用当前页面 hostname 替代 127.0.0.1，
 * 确保 API 请求携带正确的 Host header（企业域名隔离依赖 Host header）。
 * 例如：as.dakkii.cn:5666 → API 发送到 as.dakkii.cn:8000
 */
const apiURL = (() => {
  if (import.meta.env.PROD) return rawApiURL;
  try {
    const parsed = new URL(rawApiURL);
    parsed.hostname = window.location.hostname;
    return parsed.toString().replace(/\/+$/, '');
  } catch {
    return rawApiURL;
  }
})();

/** Refresh Token URL mapping / 刷新 Token URL 映射 */
const REFRESH_TOKEN_URLS: Record<ApiEndpoint, string> = {
  admin: '/admin/auth/refresh',
  tenant: '/tenant/auth/refresh',
  user: '/api/user/auth/refresh',
};

// ============================================================
// Token getter / Token 获取器
// ============================================================

const tokenGetter = {
  getToken: (endpoint: ApiEndpoint) => TokenStorage.getToken(endpoint),
  getRefreshToken: (endpoint: ApiEndpoint) =>
    TokenStorage.getRefreshToken(endpoint),
};

// ============================================================
// Authentication handler / 认证处理器
// ============================================================

/**
 * Re-authenticate (called when Token refresh fails)
 * 重新认证（Token 刷新失败时调用）
 */
async function doReAuthenticate() {
  console.warn('Access token or refresh token is invalid or expired.');
  const accessStore = useAccessStore();

  // 根据当前路由获取端类型 / resolve endpoint from current route
  const currentPath = window.location.pathname;
  const endpoint = resolveEndpointByPath(currentPath, window.location.hostname);
  const isPublicRootPath =
    currentPath === USER_HOME_PATH || currentPath === USER_HOME_ALIAS_PATH;

  // 仅清除当前端的 Token
  TokenStorage.clearToken(endpoint);
  accessStore.setAccessToken(null);
  accessStore.setRefreshToken(null);

  if (
    preferences.app.loginExpiredMode === 'modal' &&
    accessStore.isAccessChecked
  ) {
    // 弹窗模式 / login-expired modal
    accessStore.setLoginExpired(true);
  } else {
    // 重定向模式 / redirect to login
    const loginPath = LOGIN_PATHS[endpoint];
    if (isPublicRootPath) {
      return;
    }
    // 仅比较 pathname（忽略 query），避免已在登录页时创建嵌套 redirect 导致死循环
    if (currentPath === loginPath) {
      // 已在登录页，不重定向（保留原有 redirect 参数）
      return;
    }
    const redirect = `?redirect=${encodeURIComponent(currentPath)}`;
    window.location.href = loginPath + redirect;
  }
}

/**
 * Refresh Token
 * 刷新 Token
 */
async function doRefreshToken(): Promise<string> {
  const accessStore = useAccessStore();
  const currentPath = window.location.pathname;
  const endpoint = resolveEndpointByPath(currentPath, window.location.hostname);

  const refreshToken = TokenStorage.getRefreshToken(endpoint);
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  // 使用 baseRequestClient 避免循环依赖
  // baseRequestClient 没有拦截器，返回原始 AxiosResponse
  // AxiosResponse.data = HttpResponse { code, message, data: RefreshTokenResultRaw }
  const response = await baseRequestClient.post<{
    code: number;
    data: RefreshTokenResultRaw;
    message: string;
  }>(REFRESH_TOKEN_URLS[endpoint], { refresh_token: refreshToken });

  // 从响应中提取业务数据：response.data 是 HttpResponse，response.data.data 是实际数据
  const httpResponse = (response as unknown as { data: { code: number; data: RefreshTokenResultRaw; message: string } }).data;
  if (httpResponse.code !== 0) {
    throw new Error(httpResponse.message || 'Failed to refresh token');
  }
  const result = httpResponse.data;
  const newToken = result.access_token;

  // 更新 TokenStorage
  TokenStorage.setToken(endpoint, newToken);
  if (result.refresh_token) {
    TokenStorage.setRefreshToken(endpoint, result.refresh_token);
  }

  // 更新 accessStore
  accessStore.setAccessToken(newToken);
  if (result.refresh_token) {
    accessStore.setRefreshToken(result.refresh_token);
  }

  // Socket.IO 的 token getter 会自动从 TokenStorage 读取最新值，无需手动通知
  return newToken;
}

const authHandler = {
  doRefreshToken,
  doReAuthenticate,
};

// ============================================================
// Message handler / 消息处理器
// ============================================================

const messageHandler = {
  showMessage: (type: 'error' | 'success', msg: string) => {
    message[type](msg);
  },
  showLoading: (loadingMsg?: string): (() => void) => {
    const hide = message.loading(loadingMsg || $t('common.http.loading'), 0);
    return hide;
  },
  t: (key: string) => $t(key as never),
};

// ============================================================
// Create request instances / 创建请求实例
// ============================================================

/**
 * Create configured request client
 * 创建配置好的请求客户端
 */
function createConfiguredClient(
  withInterceptors: boolean = true,
): RequestClient {
  const client = new RequestClient({
    baseURL: apiURL,
    timeout: 15_000,
    responseReturn: 'data',
  });

  // SSE 请求通过 fetch 发送，不经过 Axios 拦截器，
  // 需要显式设置 Token 获取函数
  client.setTokenGetter(tokenGetter.getToken);
  client.setMessageHandler(messageHandler.showMessage);
  client.setI18n(messageHandler.t);

  if (withInterceptors) {
    // 请求拦截器 / request interceptors
    client.addRequestInterceptor(
      createRequestInterceptor(
        client,
        tokenGetter,
        () => preferences.app.locale,
        messageHandler,
      ),
    );

    // 响应拦截器：Loading 关闭 + 清理 pending
    client.addResponseInterceptor(createLoadingInterceptor(client));

    // 响应拦截器：成功消息（必须在数据解析之前，否则拿不到 config）
    client.addResponseInterceptor(
      createSuccessMessageInterceptor(messageHandler),
    );

    // 响应拦截器：数据格式解析 / response: unwrap { code, data }
    client.addResponseInterceptor(
      createResponseDataInterceptor(0, 'code', 'data'),
    );

    // 响应拦截器：Token 刷新
    client.addResponseInterceptor(
      createAuthInterceptor(
        client,
        tokenGetter,
        authHandler,
        preferences.app.enableRefreshToken,
      ),
    );

    // 响应拦截器：业务错误消息 / response: business error toast
    client.addResponseInterceptor(
      createBusinessErrorInterceptor(messageHandler),
    );

    // 响应拦截器：HTTP 错误消息
    client.addResponseInterceptor(
      createErrorMessageInterceptor(messageHandler),
    );
  }

  return client;
}

// ============================================================
// Export instances / 导出实例
// ============================================================

/**
 * Request client with full interceptors
 * 带完整拦截器的请求客户端
 */
export const requestClient = createConfiguredClient(true);

/**
 * Base request client (no interceptors, for Token refresh and special scenarios)
 * 基础请求客户端（无拦截器，用于 Token 刷新等特殊场景）
 */
export const baseRequestClient = createConfiguredClient(false);
