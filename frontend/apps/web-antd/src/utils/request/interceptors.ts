/**
 * 请求/响应拦截器
 *
 * 包含：
 * - 请求拦截器：Token 自动携带、重复请求取消、Loading 管理
 * - 响应拦截器：数据格式解析、业务错误处理、Token 刷新、HTTP 错误提示
 *
 * @module utils/request/interceptors
 */
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';

import type { RequestClient } from './request-client';
import type { ApiEndpoint, RequestOptions } from './types';

import axios from 'axios';

import { isAuthError } from './error-codes';

// ============================================================
// 类型定义
// ============================================================

/** 扩展的请求配置（包含选项） */
interface ExtendedConfig extends InternalAxiosRequestConfig {
  __options?: RequestOptions;
  __isRetryRequest?: boolean;
  __loadingKey?: string;
}

// ============================================================
// Loading 管理
// ============================================================

/** Loading 实例管理 */
const loadingState = {
  count: 0,
  hideLoading: null as (() => void) | null,
};

/** Token 获取器 */
export interface TokenGetter {
  getToken: (endpoint: ApiEndpoint) => null | string;
  getRefreshToken: (endpoint: ApiEndpoint) => null | string;
}

/** 认证处理器 */
export interface AuthHandler {
  doRefreshToken: () => Promise<string>;
  doReAuthenticate: () => Promise<void>;
}

/** 消息处理器 */
export interface MessageHandler {
  showMessage: (type: 'error' | 'success', message: string) => void;
  showLoading: (message?: string) => () => void;
  t: (key: string) => string;
}

// ============================================================
// 工具函数
// ============================================================

/**
 * 根据请求 URL 判断端类型
 */
export function getEndpointByUrl(url: string): ApiEndpoint {
  if (url.startsWith('/admin')) return 'admin';
  if (url.startsWith('/tenant')) return 'tenant';
  return 'user';
}

/**
 * 根据路径获取端类型
 */
export function getEndpointByPath(path: string): ApiEndpoint {
  if (path.startsWith('/admin')) return 'admin';
  if (path.startsWith('/tenant')) return 'tenant';
  return 'user';
}

/**
 * 格式化 Token
 */
function formatToken(token: null | string): null | string {
  return token ? `Bearer ${token}` : null;
}

// ============================================================
// 请求拦截器
// ============================================================

/**
 * 创建请求拦截器
 */
export function createRequestInterceptor(
  client: RequestClient,
  tokenGetter: TokenGetter,
  getLocale: () => string,
  messageHandler: MessageHandler,
) {
  return {
    fulfilled: async (config: ExtendedConfig) => {
      const options = config?.__options || {};

      // 1. 重复请求取消
      if (options.cancelDuplicateRequest !== false) {
        client.removePending(config);
        client.addPending(config);
      }

      // 2. 自动携带 Token（根据 URL 判断端类型）
      const requestUrl = config.url || '';
      const endpoint = getEndpointByUrl(requestUrl);
      const token = tokenGetter.getToken(endpoint);
      if (token) {
        config.headers.Authorization = formatToken(token);
      }

      // 3. Accept-Language
      config.headers['Accept-Language'] = getLocale();

      // 4. Loading 管理
      if (options.loading) {
        loadingState.count++;
        if (loadingState.count === 1) {
          loadingState.hideLoading = messageHandler.showLoading(
            messageHandler.t('ui.fallback.http.loading'),
          );
        }
      }

      return config;
    },
    rejected: (error: any) => Promise.reject(error),
  };
}

/**
 * 关闭 Loading
 */
function closeLoading() {
  if (loadingState.count > 0) {
    loadingState.count--;
  }
  if (loadingState.count === 0 && loadingState.hideLoading) {
    loadingState.hideLoading();
    loadingState.hideLoading = null;
  }
}

/**
 * 创建 Loading 响应拦截器
 * 请求完成后关闭 Loading 并清理 pending
 */
export function createLoadingInterceptor(client: RequestClient) {
  return {
    fulfilled: (response: AxiosResponse) => {
      const config = response.config as ExtendedConfig;
      const options = config?.__options || {};

      // 清理 pending 请求
      client.removePending(config);

      if (options.loading) {
        closeLoading();
      }
      return response;
    },
    rejected: (error: any) => {
      const config = error.config as ExtendedConfig;
      const options = config?.__options || {};

      // 清理 pending 请求（即使失败也要清理）
      if (config) {
        client.removePending(config);
      }

      if (options?.loading) {
        closeLoading();
      }
      return Promise.reject(error);
    },
  };
}

// ============================================================
// 响应拦截器 - 数据格式解析
// ============================================================

/**
 * 创建响应数据拦截器
 * 处理 raw/body/data 三种返回模式
 */
export function createResponseDataInterceptor(
  successCode: number = 0,
  codeField: string = 'code',
  dataField: string = 'data',
) {
  return {
    fulfilled: (response: AxiosResponse) => {
      const config = response.config as ExtendedConfig;
      const options = config?.__options || {};
      const { data: responseData, status } = response;

      // raw 模式：返回原始 AxiosResponse
      if (options.responseReturn === 'raw') {
        return response;
      }

      // HTTP 状态码检查
      if (status >= 200 && status < 400) {
        // body 模式：返回响应体
        if (options.responseReturn === 'body') {
          return responseData;
        }

        // data 模式：检查业务 code 并解构 data 字段
        const code = responseData?.[codeField];
        if (code === successCode) {
          return responseData[dataField];
        }
      }

      // 业务错误，抛出供后续拦截器处理
      throw Object.assign({}, response, { response });
    },
  };
}

// ============================================================
// 响应拦截器 - Token 刷新
// ============================================================

/**
 * 创建 Token 刷新拦截器
 *
 * 认证错误判断逻辑（基于 API 错误码规范文档）：
 * - HTTP 401 状态码 + 业务错误码 4010/4011/4012
 * - 4010: UNAUTHORIZED - 未认证
 * - 4011: TOKEN_EXPIRED - 令牌已过期
 * - 4012: TOKEN_INVALID - 无效的令牌
 */
/** 登录接口路径（这些接口的 401 不应触发重新认证） */
const LOGIN_URLS = [
  '/admin/auth/login',
  '/tenant/auth/login',
  '/api/v1/auth/login',
];

/**
 * 检查是否为登录接口
 */
function isLoginUrl(url: string | undefined): boolean {
  if (!url) return false;
  return LOGIN_URLS.some((loginUrl) => url.includes(loginUrl));
}

export function createAuthInterceptor(
  client: RequestClient,
  _tokenGetter: TokenGetter,
  authHandler: AuthHandler,
  enableRefreshToken: boolean = true,
) {
  return {
    rejected: async (error: any) => {
      // 取消的请求不处理
      if (axios.isCancel(error)) {
        throw error;
      }

      const { config, response } = error;

      // 非 401 HTTP 状态码，继续传递
      if (response?.status !== 401) {
        throw error;
      }

      // 登录接口的 401 不应触发重新认证，应该显示错误消息
      if (isLoginUrl(config?.url)) {
        throw error;
      }

      // 检查业务错误码是否为认证错误 (4010/4011/4012)
      const businessCode = response?.data?.code;
      if (!isAuthError(businessCode)) {
        // 不是认证错误，继续传递给其他拦截器处理
        throw error;
      }

      // 4010 UNAUTHORIZED 或未启用刷新或已是重试请求 -> 直接重新认证
      if (
        businessCode === 4010 ||
        !enableRefreshToken ||
        config?.__isRetryRequest
      ) {
        await authHandler.doReAuthenticate();
        throw error;
      }

      // 4011 TOKEN_EXPIRED 或 4012 TOKEN_INVALID -> 尝试刷新 Token

      // 正在刷新中，加入队列等待
      if (client.isRefreshing) {
        return new Promise((resolve, reject) => {
          client.refreshTokenQueue.push({
            resolve: (newToken: string) => {
              config.headers.Authorization = formatToken(newToken);
              resolve(client.instance.request(config));
            },
            reject: (err: any) => {
              reject(err);
            },
          });
        });
      }

      // 开始刷新
      client.isRefreshing = true;
      config.__isRetryRequest = true;

      try {
        const newToken = await authHandler.doRefreshToken();

        // 刷新成功，处理队列中的请求
        client.refreshTokenQueue.forEach((item) => item.resolve(newToken));
        client.refreshTokenQueue = [];

        // 重试原请求
        config.headers.Authorization = formatToken(newToken);
        return client.instance.request(config);
      } catch (refreshError) {
        // 刷新失败，reject 队列中所有等待的请求
        client.refreshTokenQueue.forEach((item) => item.reject(refreshError));
        client.refreshTokenQueue = [];
        await authHandler.doReAuthenticate();
        throw refreshError;
      } finally {
        client.isRefreshing = false;
      }
    },
  };
}

// ============================================================
// 响应拦截器 - 错误消息
// ============================================================

/**
 * 创建错误消息拦截器
 * 注意：如果响应中有业务错误消息，则不显示 HTTP 错误消息
 */
export function createErrorMessageInterceptor(messageHandler: MessageHandler) {
  return {
    rejected: (error: any) => {
      // 取消的请求不处理
      if (axios.isCancel(error)) {
        return Promise.reject(error);
      }

      const config = error.config as ExtendedConfig;
      const options = config?.__options || {};

      // 网络错误
      const errStr = error?.toString?.() ?? '';
      if (errStr.includes('Network Error')) {
        if (options.showErrorMessage !== false) {
          messageHandler.showMessage(
            'error',
            messageHandler.t('ui.fallback.http.networkError'),
          );
        }
        return Promise.reject(error);
      }

      // 超时错误
      if (error?.message?.includes?.('timeout')) {
        if (options.showErrorMessage !== false) {
          messageHandler.showMessage(
            'error',
            messageHandler.t('ui.fallback.http.requestTimeout'),
          );
        }
        return Promise.reject(error);
      }

      // 如果有业务错误消息，跳过 HTTP 错误消息（已由 BusinessErrorInterceptor 处理）
      const responseData = error?.response?.data;
      const hasBusinessMessage =
        responseData?.message || responseData?.error || responseData?.msg;
      if (hasBusinessMessage) {
        return Promise.reject(error);
      }

      // HTTP 状态码错误（仅当没有业务错误消息时显示）
      const status = error?.response?.status;
      if (status && options.showErrorMessage !== false) {
        const statusMessages: Record<number, string> = {
          400: 'ui.fallback.http.badRequest',
          401: 'ui.fallback.http.unauthorized',
          403: 'ui.fallback.http.forbidden',
          404: 'ui.fallback.http.notFound',
          408: 'ui.fallback.http.requestTimeout',
          500: 'ui.fallback.http.internalServerError',
          502: 'ui.fallback.http.badGateway',
          503: 'ui.fallback.http.serviceUnavailable',
          504: 'ui.fallback.http.gatewayTimeout',
        };
        const messageKey =
          statusMessages[status] || 'ui.fallback.http.internalServerError';
        messageHandler.showMessage('error', messageHandler.t(messageKey));
      }

      return Promise.reject(error);
    },
  };
}

// ============================================================
// 响应拦截器 - 业务错误消息
// ============================================================

/**
 * 创建业务错误消息拦截器
 */
export function createBusinessErrorInterceptor(messageHandler: MessageHandler) {
  return {
    rejected: (error: any) => {
      // 取消的请求不处理
      if (axios.isCancel(error)) {
        return Promise.reject(error);
      }

      const config = error.config as ExtendedConfig;
      const options = config?.__options || {};
      const responseData = error?.response?.data;

      // 显示业务错误消息
      if (options.showCodeMessage !== false && responseData) {
        const errorMessage =
          responseData.message || responseData.error || responseData.msg;
        if (errorMessage) {
          messageHandler.showMessage('error', errorMessage);
        }
      }

      return Promise.reject(error);
    },
  };
}

// ============================================================
// 响应拦截器 - 成功消息
// ============================================================

/**
 * 创建成功消息拦截器
 */
export function createSuccessMessageInterceptor(
  messageHandler: MessageHandler,
  defaultSuccessMessage?: string,
) {
  return {
    fulfilled: (response: AxiosResponse | null | undefined) => {
      // 处理 data 模式下返回 null/undefined 的情况（如 DELETE 接口返回 data: null）
      if (response === null || response === undefined) {
        return response;
      }

      // 如果是解构后的数据（非 AxiosResponse），直接返回
      if (typeof response !== 'object' || !('config' in response)) {
        return response;
      }

      const config = response.config as ExtendedConfig;
      const options = config?.__options || {};

      // 显示成功消息
      if (options.showSuccessMessage) {
        const message =
          options.successMessage ||
          defaultSuccessMessage ||
          messageHandler.t('ui.fallback.http.operationSuccess');
        messageHandler.showMessage('success', message);
      }

      return response;
    },
  };
}
