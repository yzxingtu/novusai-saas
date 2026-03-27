/**
 * Request/response interceptors
 * 请求/响应拦截器
 *
 * Includes:
 * - Request interceptors: auto Token attachment, duplicate request cancellation, Loading management
 * - Response interceptors: data format parsing, business error handling, Token refresh, HTTP error messages
 * 包含：
 * - 请求拦截器：Token 自动携带、重复请求取消、Loading 管理
 * - 响应拦截器：数据格式解析、业务错误处理、Token 刷新、HTTP 错误提示
 *
 * @module utils/request/interceptors
 */
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';

import type { RequestClient } from './request-client';
import type { ApiEndpoint, RequestOptions } from './types';

import { h } from 'vue';

import { Button, notification } from 'ant-design-vue';
import axios from 'axios';

import { isDevErrorMode } from './app-env';
import { formatAppErrorMessage, normalizeHttpError } from './app-error';
import { getEndpointByUrl } from './endpoint';
import { isAuthError } from './error-codes';
import { ensureTraceIdHeader } from './trace';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Extended request config (with options) / 扩展的请求配置（包含选项） */
interface ExtendedConfig extends InternalAxiosRequestConfig {
  __options?: RequestOptions;
  __isRetryRequest?: boolean;
  __loadingKey?: string;
}

// ============================================================
// Loading management / Loading 管理
// ============================================================

/** Loading instance management / Loading 实例管理 */
const loadingState = {
  count: 0,
  hideLoading: null as (() => void) | null,
};

/** Token getter / Token 获取器 */
export interface TokenGetter {
  getToken: (endpoint: ApiEndpoint) => null | string;
  getRefreshToken: (endpoint: ApiEndpoint) => null | string;
}

/** Authentication handler / 认证处理器 */
export interface AuthHandler {
  doRefreshToken: () => Promise<string>;
  doReAuthenticate: () => Promise<void>;
}

/** Message handler / 消息处理器 */
export interface MessageHandler {
  showMessage: (type: 'error' | 'success', message: string) => void;
  showLoading: (message?: string) => () => void;
  t: (key: string) => string;
}

// ============================================================
// Utility functions / 工具函数
// ============================================================

/**
 * Format Token
 * 格式化 Token
 */
function formatToken(token: null | string): null | string {
  return token ? `Bearer ${token}` : null;
}

function showServerErrorNotification(
  message: string,
  traceId: string,
  debugMessage: string | undefined,
  messageHandler: MessageHandler,
) {
  const detailNodes: any[] = [h('span', message)];

  if (traceId) {
    detailNodes.push(
      h('div', { class: 'flex items-center gap-2' }, [
        h(
          'span',
          { class: 'text-gray-500 text-sm' },
          `${messageHandler.t('common.http.traceId')}: ${traceId}`,
        ),
        h(
          Button,
          {
            size: 'small',
            type: 'link',
            onClick: () => {
              navigator.clipboard
                .writeText(traceId)
                .then(() =>
                  messageHandler.showMessage(
                    'success',
                    messageHandler.t('common.http.copied'),
                  ),
                )
                .catch(() =>
                  messageHandler.showMessage(
                    'error',
                    messageHandler.t('common.http.copyFailed'),
                  ),
                );
            },
          },
          () => messageHandler.t('common.http.copyTraceId'),
        ),
      ]),
    );
  }

  if (isDevErrorMode() && debugMessage) {
    detailNodes.push(
      h(
        'pre',
        {
          class:
            'max-h-40 overflow-auto rounded bg-black/5 p-2 text-xs text-red-500 whitespace-pre-wrap break-all',
        },
        debugMessage,
      ),
    );
  }

  notification.error({
    message,
    description: h('div', { class: 'flex flex-col gap-2' }, detailNodes),
    duration: 0,
  });
}

// ============================================================
// Request interceptor / 请求拦截器
// ============================================================

/**
 * Create request interceptor
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

      // 0. 注入 X-Trace-ID（用于请求关联与问题反馈）/ Inject for request correlation
      ensureTraceIdHeader(config.headers as never);

      // 1. 重复请求取消 / cancel duplicate in-flight requests
      if (options.cancelDuplicateRequest !== false) {
        client.removePending(config);
        client.addPending(config);
      }

      // 2. 自动携带 Token（根据 URL 判断端类型）/ attach Bearer by endpoint
      const requestUrl = config.url || '';
      const endpoint = getEndpointByUrl(requestUrl);
      const token = tokenGetter.getToken(endpoint);
      if (token) {
        config.headers.Authorization = formatToken(token);
      }

      // 3. Accept-Language / 协商语言头
      config.headers['Accept-Language'] = getLocale();

      // 4. Loading 管理 / global loading counter
      if (options.loading) {
        loadingState.count++;
        if (loadingState.count === 1) {
          loadingState.hideLoading = messageHandler.showLoading(
            messageHandler.t('common.http.loading'),
          );
        }
      }

      return config;
    },
    rejected: (error: any) => Promise.reject(error),
  };
}

/**
 * Close Loading
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
 * Create Loading response interceptor
 * Close Loading and clean up pending after request completion
 * 创建 Loading 响应拦截器
 * 请求完成后关闭 Loading 并清理 pending
 */
export function createLoadingInterceptor(client: RequestClient) {
  return {
    fulfilled: (response: AxiosResponse) => {
      const config = response.config as ExtendedConfig;
      const options = config?.__options || {};

      // 清理 pending 请求 / clear duplicate-cancel slot
      client.removePending(config);

      if (options.loading) {
        closeLoading();
      }
      return response;
    },
    rejected: (error: any) => {
      const config = error.config as ExtendedConfig;
      const options = config?.__options || {};

      // 清理 pending 请求（即使失败也要清理）/ clear pending on error too
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
// Response interceptor - data format parsing / 响应拦截器 - 数据格式解析
// ============================================================

/**
 * Create response data interceptor
 * Handles raw/body/data return modes
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

      // raw 模式：返回原始 AxiosResponse / return full AxiosResponse
      if (options.responseReturn === 'raw') {
        return response;
      }

      // HTTP 状态码检查 / HTTP status gate
      if (status >= 200 && status < 400) {
        // body 模式：返回响应体 / return response body JSON
        if (options.responseReturn === 'body') {
          return responseData;
        }

        // data 模式：检查业务 code 并解构 data 字段 / unwrap { code, data }
        const code = responseData?.[codeField];
        if (code === successCode) {
          return responseData[dataField];
        }
      }

      // 业务错误，抛出供后续拦截器处理 / business error → downstream interceptors
      throw Object.assign({}, response, { response });
    },
  };
}

// ============================================================
// Response interceptor - Token refresh / 响应拦截器 - Token 刷新
// ============================================================

/**
 * Create Token refresh interceptor
 * 创建 Token 刷新拦截器
 *
 * Auth error detection logic (based on API error code spec):
 * - HTTP 401 status code + business error code 4010/4011/4012
 * - 4010: UNAUTHORIZED - not authenticated
 * - 4011: TOKEN_EXPIRED - token expired
 * - 4012: TOKEN_INVALID - invalid token
 * 认证错误判断逻辑（基于 API 错误码规范文档）：
 * - HTTP 401 状态码 + 业务错误码 4010/4011/4012
 * - 4010: UNAUTHORIZED - 未认证
 * - 4011: TOKEN_EXPIRED - 令牌已过期
 * - 4012: TOKEN_INVALID - 无效的令牌
 */
/** Login endpoint paths (401 from these should not trigger re-authentication) / 登录接口路径（这些接口的 401 不应触发重新认证） */
const LOGIN_URLS = [
  '/admin/auth/login',
  '/tenant/auth/login',
  '/api/user/auth/login',
];

/**
 * Check if URL is a login endpoint
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
      // 取消的请求不处理 / skip cancelled requests
      if (axios.isCancel(error)) {
        throw error;
      }

      const { config, response } = error;

      // 非 401 HTTP 状态码，继续传递 / pass through non-401
      if (response?.status !== 401) {
        throw error;
      }

      // 登录接口的 401 不应触发重新认证，应该显示错误消息 / login 401 → show error, no re-auth flow
      if (isLoginUrl(config?.url)) {
        throw error;
      }

      // 检查业务错误码是否为认证错误 (4010/4011/4012) / map biz codes to auth errors
      const businessCode = response?.data?.code;
      if (!isAuthError(businessCode)) {
        // 不是认证错误，继续传递给其他拦截器处理 / not auth-related → pass through
        throw error;
      }

      // 4010 UNAUTHORIZED 或未启用刷新或已是重试请求 -> 直接重新认证 / re-auth path
      if (
        businessCode === 4010 ||
        !enableRefreshToken ||
        config?.__isRetryRequest
      ) {
        await authHandler.doReAuthenticate();
        throw error;
      }

      // 4011 TOKEN_EXPIRED 或 4012 TOKEN_INVALID -> 尝试刷新 Token / refresh token path

      // 正在刷新中，加入队列等待 / queue while refresh in progress
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

      // 开始刷新 / start token refresh
      client.isRefreshing = true;
      config.__isRetryRequest = true;

      try {
        const newToken = await authHandler.doRefreshToken();

        // 刷新成功，处理队列中的请求 / flush queued retries
        client.refreshTokenQueue.forEach((item) => item.resolve(newToken));
        client.refreshTokenQueue = [];

        // 重试原请求 / retry original request
        config.headers.Authorization = formatToken(newToken);
        return client.instance.request(config);
      } catch (refreshError) {
        // 刷新失败，reject 队列中所有等待的请求 / reject queued on refresh failure
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
// Response interceptor - error messages / 响应拦截器 - 错误消息
// ============================================================

/**
 * Create error message interceptor
 * Note: If the response contains a business error message, HTTP error message is not shown
 * 创建错误消息拦截器
 * 注意：如果响应中有业务错误消息，则不显示 HTTP 错误消息
 */
export function createErrorMessageInterceptor(messageHandler: MessageHandler) {
  return {
    rejected: (error: any) => {
      // 取消的请求不处理 / skip cancelled
      if (axios.isCancel(error)) {
        return Promise.reject(error);
      }

      const config = error.config as ExtendedConfig;
      const options = config?.__options || {};
      const appError = normalizeHttpError(error, messageHandler.t);

      // 网络错误 / network failure
      const errStr = error?.toString?.() ?? '';
      if (errStr.includes('Network Error')) {
        if (options.showErrorMessage !== false) {
          messageHandler.showMessage(
            'error',
            formatAppErrorMessage(appError, messageHandler.t),
          );
        }
        return Promise.reject(Object.assign(error, { appError }));
      }

      // 超时错误 / request timeout
      if (error?.message?.includes?.('timeout')) {
        if (options.showErrorMessage !== false) {
          messageHandler.showMessage(
            'error',
            formatAppErrorMessage(appError, messageHandler.t),
          );
        }
        return Promise.reject(Object.assign(error, { appError }));
      }

      // 如果有业务错误消息，跳过 HTTP 错误消息（已由 BusinessErrorInterceptor 处理）/ defer to biz interceptor
      const responseData = error?.response?.data;
      const status = error?.response?.status;
      const hasBusinessMessage =
        responseData?.message || responseData?.error || responseData?.msg;
      if (hasBusinessMessage) {
        if (status >= 500 && options.showErrorMessage !== false) {
          showServerErrorNotification(
            appError.message,
            appError.traceId || '',
            appError.debugMessage,
            messageHandler,
          );
        }
        return Promise.reject(Object.assign(error, { appError }));
      }

      // HTTP 状态码错误（仅当没有业务错误消息时显示）/ HTTP status toast fallback
      if (status && options.showErrorMessage !== false) {
        const statusMessages: Record<number, string> = {
          400: 'common.http.badRequest',
          401: 'common.http.unauthorized',
          403: 'common.http.forbidden',
          404: 'common.http.notFound',
          408: 'common.http.requestTimeout',
          500: 'common.http.internalServerError',
          502: 'common.http.badGateway',
          503: 'common.http.serviceUnavailable',
          504: 'common.http.gatewayTimeout',
        };
        const messageKey =
          statusMessages[status] || 'common.http.internalServerError';
        const msg = messageHandler.t(messageKey);
        const displayError = {
          ...appError,
          message: appError.message || msg,
        };

        // 5xx：notification + 追踪 ID + 复制（不自动关闭）/ trace-aware server error notification
        if (status >= 500) {
          showServerErrorNotification(
            displayError.message,
            displayError.traceId || '',
            displayError.debugMessage,
            messageHandler,
          );
        } else {
          messageHandler.showMessage(
            'error',
            formatAppErrorMessage(displayError, messageHandler.t),
          );
        }
      }

      return Promise.reject(Object.assign(error, { appError }));
    },
  };
}

// ============================================================
// Response interceptor - business error messages / 响应拦截器 - 业务错误消息
// ============================================================

/**
 * Create business error message interceptor
 * 创建业务错误消息拦截器
 */
export function createBusinessErrorInterceptor(messageHandler: MessageHandler) {
  return {
    rejected: (error: any) => {
      // 取消的请求不处理 / skip cancelled
      if (axios.isCancel(error)) {
        return Promise.reject(error);
      }

      const config = error.config as ExtendedConfig;
      const options = config?.__options || {};
      const responseData = error?.response?.data;
      const status = error?.response?.status;
      const appError = normalizeHttpError(error, messageHandler.t);

      // 显示业务错误消息 / show biz error toast
      if (
        options.showCodeMessage !== false &&
        responseData &&
        appError.message &&
        (!status || status < 500)
      ) {
        messageHandler.showMessage(
          'error',
          formatAppErrorMessage(appError, messageHandler.t),
        );
      }

      return Promise.reject(Object.assign(error, { appError }));
    },
  };
}

// ============================================================
// Response interceptor - success messages / 响应拦截器 - 成功消息
// ============================================================

/**
 * Create success message interceptor
 * 创建成功消息拦截器
 */
export function createSuccessMessageInterceptor(
  messageHandler: MessageHandler,
  defaultSuccessMessage?: string,
) {
  return {
    fulfilled: (response: AxiosResponse | null | undefined) => {
      // 处理 data 模式下返回 null/undefined 的情况（如 DELETE 接口返回 data: null）/ allow empty DELETE data
      if (response === null || response === undefined) {
        return response;
      }

      // 如果是解构后的数据（非 AxiosResponse），直接返回 / plain payload passthrough
      if (typeof response !== 'object' || !('config' in response)) {
        return response;
      }

      const config = response.config as ExtendedConfig;
      const options = config?.__options || {};

      // 显示成功消息 / success toast
      if (options.showSuccessMessage) {
        const message =
          options.successMessage ||
          defaultSuccessMessage ||
          messageHandler.t('common.http.operationSuccess');
        messageHandler.showMessage('success', message);
      }

      return response;
    },
  };
}
