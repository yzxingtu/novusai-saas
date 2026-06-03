/**
 * HTTP request type definitions
 * HTTP 请求类型定义
 *
 * @module utils/request/types
 */
import type { AxiosRequestConfig, AxiosResponse } from 'axios';

// ============================================================
// Request configuration types / 请求配置类型
// ============================================================

/**
 * Response data return mode
 * 响应数据的返回方式
 *
 * - raw: Original AxiosResponse including headers, status, etc.
 * - body: Return response BODY part (only checks HTTP status)
 * - data: Destructure response BODY, return only the data field (checks code)
 * - raw: 原始的 AxiosResponse，包括 headers、status 等
 * - body: 返回响应数据的 BODY 部分（只检查 HTTP status）
 * - data: 解构响应的 BODY 数据，只返回其中的 data 字段（检查 code）
 */
export type ResponseReturn = 'body' | 'data' | 'raw';

/**
 * Parameter serialization mode
 * 参数序列化方式
 *
 * - brackets: ids[]=1&ids[]=2&ids[]=3
 * - comma: ids=1,2,3
 * - indices: ids[0]=1&ids[1]=2&ids[2]=3
 * - repeat: ids=1&ids=2&ids=3
 */
export type ParamsSerializer = 'brackets' | 'comma' | 'indices' | 'repeat';

/**
 * Request extension options
 * 请求扩展选项
 */
export interface RequestOptions {
  /**
   * Whether to enable duplicate request cancellation
   * 是否开启取消重复请求
   * @default true
   */
  cancelDuplicateRequest?: boolean;

  /**
   * Whether to enable loading effect
   * 是否开启 Loading 效果
   * @default false
   */
  loading?: boolean;

  /**
   * Response data return mode
   * 响应数据的返回方式
   * @default 'data'
   */
  responseReturn?: ResponseReturn;

  /**
   * Whether to show HTTP error messages (network errors, timeout, etc.)
   * 是否显示 HTTP 错误消息（网络错误、超时等）
   * @default true
   */
  showErrorMessage?: boolean;

  /**
   * Whether to show business error messages (when code !== 0)
   * 是否显示业务错误消息（code !== 0 时）
   * @default true
   */
  showCodeMessage?: boolean;

  /**
   * Whether to show success messages (when code === 0)
   * 是否显示成功消息（code === 0 时）
   * @default false
   */
  showSuccessMessage?: boolean;

  /**
   * Success message content (used when showSuccessMessage is true)
   * 成功消息内容（showSuccessMessage 为 true 时使用）
   */
  successMessage?: string;

  /**
   * Parameter serialization mode
   * 参数序列化方式
   */
  paramsSerializer?: ParamsSerializer;
}

/**
 * Complete request configuration (Axios config + extension options)
 * 完整的请求配置（Axios 配置 + 扩展选项）
 */
export type RequestClientConfig<D = any> = AxiosRequestConfig<D> &
  RequestOptions;

/**
 * API function request options (simplified)
 * Used as optional parameters for API functions
 * API 函数使用的请求选项（简化版）
 * 用于 API 函数的可选参数
 */
export interface ApiRequestOptions {
  /**
   * Whether to enable loading effect
   * 是否开启 Loading 效果
   * @default false
   */
  loading?: boolean;

  /**
   * Whether to show success message
   * 是否显示成功消息
   * @default false
   */
  showSuccessMessage?: boolean;

  /**
   * Success message content
   * 成功消息内容
   */
  successMessage?: string;

  /**
   * Whether to show business error messages
   * 是否显示业务错误消息
   * @default true
   */
  showCodeMessage?: boolean;

  /**
   * Whether to show HTTP error messages
   * 是否显示 HTTP 错误消息
   * @default true
   */
  showErrorMessage?: boolean;

  /**
   * AbortSignal for request cancellation
   * 用于取消请求的 AbortSignal
   */
  signal?: AbortSignal;
}

/**
 * Request response type
 * 请求响应类型
 */
export type RequestResponse<T = any> = AxiosResponse<T> & {
  config: RequestClientConfig<T>;
};

// ============================================================
// Response data types / 响应数据类型
// ============================================================

/**
 * Standard HTTP response format
 * 标准 HTTP 响应格式
 */
export interface HttpResponse<T = any> {
  /** Business status code, 0 means success / 业务状态码，0 表示成功 */
  code: number;
  /** Response data / 响应数据 */
  data: T;
  /** Response message / 响应消息 */
  message: string;
  /** Trace ID for request correlation / 请求追踪 ID */
  trace_id?: string;
  /** Dev-only debug payload / 仅开发环境调试负载 */
  debug?: Record<string, unknown>;
  /** Whether the request succeeded / 请求是否成功 */
  success?: boolean;
}

// ============================================================
// Interceptor types / 拦截器类型
// ============================================================

/**
 * Request interceptor configuration
 * 请求拦截器配置
 */
export interface RequestInterceptorConfig {
  fulfilled?: (config: any) => any | Promise<any>;
  rejected?: (error: any) => any;
}

/**
 * Response interceptor configuration
 * 响应拦截器配置
 */
export interface ResponseInterceptorConfig {
  fulfilled?: (response: any) => any | Promise<any>;
  rejected?: (error: any) => any;
}

// ============================================================
// Token related types / Token 相关类型
// ============================================================

/**
 * Refresh token response (backend raw format)
 * 刷新 Token 响应（后端原始格式）
 */
export interface RefreshTokenResultRaw {
  access_token: string;
  refresh_token?: string;
}

// ============================================================
// Error handling types / 错误处理类型
// ============================================================

/**
 * Error message generator function
 * 错误消息生成函数
 */
export type MakeErrorMessageFn = (message: string, error: any) => void;

/**
 * Business error handler function
 * 业务错误处理函数
 */
export type BusinessErrorHandler = (
  code: number,
  message: string,
  data: any,
) => void;

// ============================================================
// SSE types / SSE 类型
// ============================================================

/**
 * SSE request options
 * SSE 请求选项
 */
export interface SseRequestOptions extends Omit<RequestInit, 'signal'> {
  /** Message callback（可 async，便于在回调内 await nextTick 以触发逐帧渲染）/ Message callback */
  onMessage?: (message: string) => Promise<void> | void;
  /** End callback / 结束回调 */
  onEnd?: () => Promise<void> | void;
  /** Error callback / 错误回调 */
  onError?: (error: Error) => void;
  /** AbortController for request cancellation / 用于取消请求的 AbortController */
  abortController?: AbortController;
}

// ============================================================
// File upload types / 文件上传类型
// ============================================================

/**
 * File upload data
 * 文件上传数据
 */
export interface UploadFileData extends Record<string, Blob | File | string> {
  file: Blob | File;
}

/**
 * Upload progress callback
 * 上传进度回调
 */
export type UploadProgressCallback = (progress: {
  loaded: number;
  percent: number;
  total: number;
}) => void;

// ============================================================
// Request client options / 请求客户端选项
// ============================================================

/**
 * Request client creation options
 * 请求客户端创建选项
 */
export interface RequestClientOptions extends RequestOptions {
  /** Base URL / 基础 URL */
  baseURL?: string;
  /** Timeout in milliseconds / 超时时间（毫秒） */
  timeout?: number;
  /** Default request headers / 默认请求头 */
  headers?: Record<string, string>;
}

export { type ApiEndpoint } from '#/types/endpoint';
