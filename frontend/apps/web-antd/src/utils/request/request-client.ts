/**
 * HTTP request client
 * HTTP 请求客户端
 *
 * Axios-based wrapper with support for:
 * - Multi-endpoint auto Token attachment
 * - Duplicate request cancellation
 * - Loading state management
 * - Business error code handling
 * - Auto Token refresh
 * - File upload/download
 * - SSE streaming requests
 * 基于 axios 封装，支持：
 * - 多端 Token 自动携带
 * - 重复请求取消
 * - Loading 状态管理
 * - 业务错误码处理
 * - Token 自动刷新
 * - 文件上传下载
 * - SSE 流式请求
 *
 * @module utils/request/request-client
 */
import type {
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';

import type {
  ApiEndpoint,
  HttpResponse,
  ParamsSerializer,
  RequestClientConfig,
  RequestClientOptions,
  RequestInterceptorConfig,
  RequestOptions,
  ResponseInterceptorConfig,
  SseRequestOptions,
  UploadFileData,
  UploadProgressCallback,
} from './types';

import axios from 'axios';
import qs from 'qs';

import {
  formatAppErrorMessage,
  normalizeHttpError,
  normalizeSseTransportError,
  toErrorWithAppError,
} from './app-error';
import { getEndpointByUrl } from './endpoint';
import { ensureTraceIdHeader } from './trace';

// ============================================================
// Default configuration / 默认配置
// ============================================================

/** Default request options / 默认请求选项 */
const DEFAULT_OPTIONS: Required<RequestOptions> = {
  cancelDuplicateRequest: true,
  loading: false,
  responseReturn: 'data',
  showErrorMessage: true,
  showCodeMessage: true,
  showSuccessMessage: false,
  successMessage: '',
  paramsSerializer: 'brackets',
};

// ============================================================
// Utility functions / 工具函数
// ============================================================

/**
 * Get parameter serializer
 * 获取参数序列化器
 */
function getParamsSerializer(type: ParamsSerializer) {
  const formatMap: Record<
    ParamsSerializer,
    'brackets' | 'comma' | 'indices' | 'repeat'
  > = {
    brackets: 'brackets',
    comma: 'comma',
    indices: 'indices',
    repeat: 'repeat',
  };
  return (params: any) =>
    qs.stringify(params, { arrayFormat: formatMap[type] });
}

/**
 * Generate unique request key (for duplicate request detection)
 * 生成请求唯一标识（用于重复请求判断）
 */
function getPendingKey(config: InternalAxiosRequestConfig): string {
  const { url, method, params, data, headers } = config;
  const dataStr = typeof data === 'string' ? data : JSON.stringify(data);
  return [
    url,
    method,
    JSON.stringify(params),
    dataStr,
    (headers as any)?.Authorization || '',
  ].join('&');
}

// ============================================================
// RequestClient class / RequestClient 类
// ============================================================

export class RequestClient {
  /** Re-authenticate function (used by interceptors) / 重新认证函数（拦截器使用） */
  public doReAuthenticate?: () => Promise<void>;

  /** Token refresh function (used by interceptors) / Token 刷新函数（拦截器使用） */
  public doRefreshToken?: () => Promise<string>;

  /** Refresh Token getter function (used by interceptors) / Refresh Token 获取函数（拦截器使用） */
  public getRefreshToken?: (endpoint: ApiEndpoint) => null | string;

  /** Axios instance / Axios 实例 */
  public readonly instance: AxiosInstance;

  /** Currently refreshing Token / 正在刷新 Token */
  public isRefreshing = false;

  /** Token refresh queue (stores resolve/reject callbacks) / Token 刷新队列（存储 resolve/reject 回调） */
  public refreshTokenQueue: Array<{
    reject: (error: any) => void;
    resolve: (token: string) => void;
  }> = [];

  /** Show message (used by interceptors) / 显示消息（拦截器使用） */
  public showMessage?: (type: 'error' | 'success', message: string) => void;

  /** i18n function (used by interceptors) / 国际化函数（拦截器使用） */
  public t?: (key: string) => string;

  /** Default options / 默认选项 */
  private readonly defaultOptions: Required<RequestOptions>;

  /** Token getter function / Token 获取函数 */
  private getToken?: (endpoint: ApiEndpoint) => null | string;

  /** Pending requests Map (for cancelling duplicate requests) / 待处理请求 Map（用于取消重复请求） */
  private pendingMap = new Map<string, AbortController>();

  constructor(options: RequestClientOptions = {}) {
    const { baseURL, timeout = 10_000, headers = {}, ...restOptions } = options;

    // 合并默认选项 / merge default request options
    this.defaultOptions = { ...DEFAULT_OPTIONS, ...restOptions };

    // 创建 Axios 实例 / create axios instance
    this.instance = axios.create({
      baseURL,
      timeout,
      headers: {
        'Content-Type': 'application/json;charset=utf-8',
        'Cache-Control': 'no-cache',
        Pragma: 'no-cache',
        ...headers,
      },
      paramsSerializer: getParamsSerializer(
        this.defaultOptions.paramsSerializer,
      ),
    });

    // 绑定方法 / bind HTTP helpers to instance
    this.bindMethods();
  }

  /** Add pending request (used by interceptors) / 添加待处理请求（拦截器使用） */
  public addPending(config: InternalAxiosRequestConfig) {
    const key = getPendingKey(config);
    if (this.pendingMap.has(key)) {
      // 取消之前的请求 / abort prior duplicate
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      const controller = this.pendingMap.get(key)!;
      controller.abort();
      this.pendingMap.delete(key);
    }
    const controller = new AbortController();
    config.signal = controller.signal;
    this.pendingMap.set(key, controller);
  }

  // ============================================================
  // Configuration methods / 配置方法
  // ============================================================

  /** Add request interceptor / 添加请求拦截器 */
  addRequestInterceptor(config: RequestInterceptorConfig) {
    this.instance.interceptors.request.use(
      config.fulfilled as any,
      config.rejected,
    );
    return this;
  }

  /** Add response interceptor / 添加响应拦截器 */
  addResponseInterceptor(config: ResponseInterceptorConfig) {
    this.instance.interceptors.response.use(
      config.fulfilled as any,
      config.rejected,
    );
    return this;
  }

  /** DELETE request / DELETE 请求 */
  delete<T = any>(url: string, config?: RequestClientConfig): Promise<T> {
    return this.request<T>(url, { ...config, method: 'DELETE' });
  }

  /**
   * File download
   * 文件下载
   *
   * @param url - Download URL / 下载 URL
   * @param config - Request configuration / 请求配置
   */
  async download<T = Blob>(
    url: string,
    config?: RequestClientConfig & { data?: any; method?: 'GET' | 'POST' },
  ): Promise<T> {
    const { method = 'GET', data, ...restConfig } = config || {};
    const headers = { ...restConfig.headers };
    ensureTraceIdHeader(headers);

    try {
      const response = await this.instance.request<T>({
        url,
        method,
        data,
        responseType: 'blob',
        ...restConfig,
        headers,
        // 下载请求：raw 模式跳过业务 code 解析，避免 Blob 被误判为错误
        ...({
          __options: {
            showErrorMessage: false,
            showCodeMessage: false,
            responseReturn: 'raw',
          },
        } as any),
      });

      // 检查响应是否为错误（某些后端返回 JSON 错误而不是 Blob）/ JSON error masquerading as blob
      const blob = response.data as Blob;
      if (blob.type === 'application/json') {
        // 解析 JSON 错误 / parse error JSON
        const text = await blob.text();
        const errorData = JSON.parse(text);
        const wrappedError = {
          response: {
            data: errorData,
            headers: response.headers,
            status: response.status,
          },
        };
        throw toErrorWithAppError(normalizeHttpError(wrappedError, this.t));
      }

      return response.data;
    } catch (error: any) {
      // 显示友好的错误提示 / user-facing download error
      if (this.showMessage) {
        const appError = normalizeHttpError(
          error,
          this.t,
          this.t?.('common.http.downloadFailed') || 'Download failed',
        );
        this.showMessage('error', formatAppErrorMessage(appError, this.t));
      }
      throw error;
    }
  }

  /** GET request / GET 请求 */
  get<T = any>(url: string, config?: RequestClientConfig): Promise<T> {
    return this.request<T>(url, { ...config, method: 'GET' });
  }

  /** Get base URL / 获取基础 URL */
  getBaseUrl(): string | undefined {
    return this.instance.defaults.baseURL;
  }

  // ============================================================
  // Interceptor methods / 拦截器方法
  // ============================================================

  /** PATCH request / PATCH 请求 */
  patch<T = any>(
    url: string,
    data?: any,
    config?: RequestClientConfig,
  ): Promise<T> {
    return this.request<T>(url, { ...config, data, method: 'PATCH' });
  }

  /** POST request / POST 请求 */
  post<T = any>(
    url: string,
    data?: any,
    config?: RequestClientConfig,
  ): Promise<T> {
    return this.request<T>(url, { ...config, data, method: 'POST' });
  }

  // ============================================================
  // Duplicate request cancellation / 重复请求取消
  // ============================================================

  /**
   * SSE POST request
   * SSE POST 请求
   */
  async postSSE(url: string, data?: any, options?: SseRequestOptions) {
    return this.requestSSE(url, data, { ...options, method: 'POST' });
  }

  /** PUT request / PUT 请求 */
  put<T = any>(
    url: string,
    data?: any,
    config?: RequestClientConfig,
  ): Promise<T> {
    return this.request<T>(url, { ...config, data, method: 'PUT' });
  }

  // ============================================================
  // HTTP methods / HTTP 方法
  // ============================================================

  /** Remove pending request (used by interceptors) / 移除待处理请求（拦截器使用） */
  public removePending(config: InternalAxiosRequestConfig) {
    const key = getPendingKey(config);
    this.pendingMap.delete(key);
  }

  /**
   * Generic request method
   * Loading is managed uniformly by interceptors
   * 通用请求方法
   * Loading 由拦截器统一管理
   */
  async request<T = any>(
    url: string,
    config: RequestClientConfig = {},
  ): Promise<T> {
    const headers = { ...config.headers };
    ensureTraceIdHeader(headers);

    // 合并选项 / merge per-request options
    const options: Required<RequestOptions> = {
      ...this.defaultOptions,
      ...config,
    };

    const response = await this.instance.request<
      T,
      AxiosResponse<HttpResponse<T>>
    >({
      url,
      ...config,
      headers,
      // 存储选项到 config 中，供拦截器使用
      ...({ __options: options } as any),
    });

    return response as unknown as T;
  }

  /**
   * SSE request
   * SSE 请求
   *
   * @param url - Request URL / 请求 URL
   * @param data - Request data / 请求数据
   * @param options - SSE options with onMessage/onEnd/onError/abortController / SSE 选项
   */
  async requestSSE(url: string, data?: any, options?: SseRequestOptions) {
    const { onMessage, onEnd, onError, abortController, ...fetchOptions } =
      options || {};

    try {
      const baseUrl = this.instance.defaults.baseURL || '';
      const fullUrl = baseUrl
        ? `${baseUrl.replace(/\/+$/, '')}/${url.replace(/^\/+/, '')}`
        : url;

      // 构建请求头 / SSE fetch headers
      const headers = new Headers();
      headers.set('Accept', 'text/event-stream');
      headers.set('Content-Type', 'application/json');

      // 添加 Token / attach Bearer
      if (this.getToken) {
        const endpoint = getEndpointByUrl(url);
        const token = this.getToken(endpoint);
        if (token) {
          headers.set('Authorization', `Bearer ${token}`);
        }
      }

      // 合并自定义 headers / merge caller headers
      if (fetchOptions?.headers) {
        new Headers(fetchOptions.headers).forEach((v, k) => headers.set(k, v));
      }
      ensureTraceIdHeader(headers);

      // 准备请求体 / serialize body
      let body: BodyInit | null = null;
      if (data && fetchOptions?.method !== 'GET') {
        body = typeof data === 'string' ? data : JSON.stringify(data);
      }

      const response = await fetch(fullUrl, {
        ...fetchOptions,
        method: fetchOptions?.method || 'GET',
        headers,
        body,
        signal: abortController?.signal,
      });

      if (!response.ok) {
        // 尝试解析响应体并归一化错误对象 / parse error JSON if any
        let responseBody: null | Record<string, unknown> = null;
        try {
          responseBody = await response.json();
        } catch {
          // ignore JSON parse errors / 非 JSON 则忽略解析失败
        }
        const normalized = normalizeHttpError(
          {
            response: {
              data: responseBody,
              headers: response.headers,
              status: response.status,
            },
          },
          this.t,
        );
        throw toErrorWithAppError(normalized);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No reader available');
      }

      let isEnd = false;
      while (!isEnd) {
        const { done, value } = await reader.read();
        if (done) {
          const tail = decoder.decode(new Uint8Array(), { stream: false });
          if (tail) {
            await Promise.resolve(onMessage?.(tail));
          }
          isEnd = true;
          await Promise.resolve(onEnd?.());
          break;
        }
        const content = decoder.decode(value, { stream: true });
        await Promise.resolve(onMessage?.(content));
      }
    } catch (error: any) {
      // 检查是否为取消操作 / user abort
      if (error.name === 'AbortError') {
        // 请求被取消，不触发错误回调 / silent on cancel
        return;
      }
      const appError = normalizeSseTransportError(error, this.t);
      // 触发错误回调 / delegate to onError
      if (onError) {
        onError(toErrorWithAppError(appError));
      } else {
        // 没有错误回调时抛出错误 / rethrow if no handler
        throw toErrorWithAppError(appError);
      }
    }
  }

  /** Set i18n function / 设置国际化函数 */
  setI18n(fn: (key: string) => string) {
    this.t = fn;
    return this;
  }

  /** Set message handler function / 设置消息提示函数 */
  setMessageHandler(fn: (type: 'error' | 'success', message: string) => void) {
    this.showMessage = fn;
    return this;
  }

  /** Set re-authenticate handler / 设置重新认证函数 */
  setReAuthenticateHandler(fn: () => Promise<void>) {
    this.doReAuthenticate = fn;
    return this;
  }

  // ============================================================
  // File upload / 文件上传
  // ============================================================

  /** Set Refresh Token getter / 设置 Refresh Token 获取函数 */
  setRefreshTokenGetter(fn: (endpoint: ApiEndpoint) => null | string) {
    this.getRefreshToken = fn;
    return this;
  }

  // ============================================================
  // File download / 文件下载
  // ============================================================

  /** Set Token refresh handler / 设置 Token 刷新函数 */
  setRefreshTokenHandler(fn: () => Promise<string>) {
    this.doRefreshToken = fn;
    return this;
  }

  // ============================================================
  // SSE streaming requests / SSE 流式请求
  // ============================================================

  /** Set Token getter function / 设置 Token 获取函数 */
  setTokenGetter(fn: (endpoint: ApiEndpoint) => null | string) {
    this.getToken = fn;
    return this;
  }

  /**
   * File upload
   * 文件上传
   */
  async upload<T = unknown>(
    url: string,
    data: UploadFileData,
    config?: RequestClientConfig,
    onProgress?: UploadProgressCallback,
  ): Promise<T> {
    const formData = new FormData();

    Object.entries(data).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          value.forEach((item, index) => {
            formData.append(`${key}[${index}]`, item);
          });
        } else {
          formData.append(key, value);
        }
      }
    });

    return this.post<T>(url, formData, {
      ...config,
      headers: {
        'Content-Type': 'multipart/form-data',
        ...config?.headers,
      },
      onUploadProgress: onProgress
        ? (progressEvent: { loaded: number; total?: number }) => {
            const { loaded, total } = progressEvent;
            if (total) {
              onProgress({
                loaded,
                total,
                percent: Math.round((loaded * 100) / total),
              });
            }
          }
        : undefined,
    });
  }

  // ============================================================
  // Helper methods / 辅助方法
  // ============================================================

  /** Bind method context / 绑定方法上下文 */
  private bindMethods() {
    this.get = this.get.bind(this);
    this.post = this.post.bind(this);
    this.put = this.put.bind(this);
    this.delete = this.delete.bind(this);
    this.request = this.request.bind(this);
    this.upload = this.upload.bind(this);
    this.download = this.download.bind(this);
    this.requestSSE = this.requestSSE.bind(this);
    this.postSSE = this.postSSE.bind(this);
  }
}
