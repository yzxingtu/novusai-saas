import type { ApiEndpoint, RefreshTokenResultRaw } from './types';

/**
 * 请求实例配置
 *
 * 创建并配置 requestClient 实例，集成：
 * - 多端 Token 管理
 * - 请求/响应拦截器
 * - 错误处理
 *
 * @module utils/request/instance
 */
import { useAppConfig } from '@vben/hooks';
import { preferences } from '@vben/preferences';
import { useAccessStore } from '@vben/stores';

import { message } from 'ant-design-vue';

import { LOGIN_PATHS, TokenStorage } from '#/store';

import {
  createAuthInterceptor,
  createBusinessErrorInterceptor,
  createErrorMessageInterceptor,
  createLoadingInterceptor,
  createRequestInterceptor,
  createResponseDataInterceptor,
  createSuccessMessageInterceptor,
  getEndpointByPath,
} from './interceptors';
import { RequestClient } from './request-client';

// ============================================================
// 配置
// ============================================================

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

/** 刷新 Token URL 映射 */
const REFRESH_TOKEN_URLS: Record<ApiEndpoint, string> = {
  admin: '/admin/auth/refresh',
  tenant: '/tenant/auth/refresh',
  user: '/api/v1/auth/refresh',
};

// ============================================================
// Token 获取器
// ============================================================

const tokenGetter = {
  getToken: (endpoint: ApiEndpoint) => TokenStorage.getToken(endpoint),
  getRefreshToken: (endpoint: ApiEndpoint) =>
    TokenStorage.getRefreshToken(endpoint),
};

// ============================================================
// 认证处理器
// ============================================================

/**
 * 重新认证（Token 刷新失败时调用）
 */
async function doReAuthenticate() {
  console.warn('Access token or refresh token is invalid or expired.');
  const accessStore = useAccessStore();

  // 根据当前路由获取端类型
  const currentPath = window.location.pathname;
  const endpoint = getEndpointByPath(currentPath);

  // 仅清除当前端的 Token
  TokenStorage.clearToken(endpoint);
  accessStore.setAccessToken(null);
  accessStore.setRefreshToken(null);

  if (
    preferences.app.loginExpiredMode === 'modal' &&
    accessStore.isAccessChecked
  ) {
    // 弹窗模式
    accessStore.setLoginExpired(true);
  } else {
    // 重定向模式
    const loginPath = LOGIN_PATHS[endpoint];
    const currentFullPath = window.location.pathname + window.location.search;
    const redirect =
      currentFullPath === loginPath
        ? ''
        : `?redirect=${encodeURIComponent(currentFullPath)}`;
    window.location.href = loginPath + redirect;
  }
}

/**
 * 刷新 Token
 */
async function doRefreshToken(): Promise<string> {
  const accessStore = useAccessStore();
  const currentPath = window.location.pathname;
  const endpoint = getEndpointByPath(currentPath);

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
  const httpResponse = (response as any).data;
  if (httpResponse.code !== 0) {
    throw new Error(httpResponse.message || 'Failed to refresh token');
  }
  const result = httpResponse.data as RefreshTokenResultRaw;
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

  return newToken;
}

const authHandler = {
  doRefreshToken,
  doReAuthenticate,
};

// ============================================================
// 消息处理器
// ============================================================

const messageHandler = {
  showMessage: (type: 'error' | 'success', msg: string) => {
    message[type](msg);
  },
  showLoading: (loadingMsg?: string): (() => void) => {
    const hide = message.loading(loadingMsg || '加载中...', 0);
    return hide;
  },
  t: (key: string) => {
    // 简单的 fallback，实际使用时可以接入 i18n
    const fallbacks: Record<string, string> = {
      'ui.fallback.http.networkError': '网络错误',
      'ui.fallback.http.requestTimeout': '请求超时',
      'ui.fallback.http.badRequest': '请求参数错误',
      'ui.fallback.http.unauthorized': '未授权',
      'ui.fallback.http.forbidden': '禁止访问',
      'ui.fallback.http.notFound': '资源不存在',
      'ui.fallback.http.internalServerError': '服务器内部错误',
      'ui.fallback.http.badGateway': '网关错误',
      'ui.fallback.http.serviceUnavailable': '服务不可用',
      'ui.fallback.http.gatewayTimeout': '网关超时',
      'ui.fallback.http.loading': '加载中...',
      'ui.fallback.http.operationSuccess': '操作成功',
    };
    return fallbacks[key] || key;
  },
};

// ============================================================
// 创建请求实例
// ============================================================

/**
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

  if (withInterceptors) {
    // 请求拦截器
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

    // 响应拦截器：数据格式解析
    client.addResponseInterceptor(
      createResponseDataInterceptor(0, 'code', 'data'),
    );

    // 响应拦截器：成功消息
    client.addResponseInterceptor(
      createSuccessMessageInterceptor(messageHandler),
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

    // 响应拦截器：业务错误消息
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
// 导出实例
// ============================================================

/**
 * 带完整拦截器的请求客户端
 */
export const requestClient = createConfiguredClient(true);

/**
 * 基础请求客户端（无拦截器，用于 Token 刷新等特殊场景）
 */
export const baseRequestClient = createConfiguredClient(false);
