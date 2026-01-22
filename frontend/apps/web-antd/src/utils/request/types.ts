/**
 * HTTP 请求类型定义
 *
 * @module utils/request/types
 */
import type { AxiosRequestConfig, AxiosResponse } from 'axios';

// ============================================================
// 请求配置类型
// ============================================================

/**
 * 响应数据的返回方式
 * - raw: 原始的 AxiosResponse，包括 headers、status 等
 * - body: 返回响应数据的 BODY 部分（只检查 HTTP status）
 * - data: 解构响应的 BODY 数据，只返回其中的 data 字段（检查 code）
 */
export type ResponseReturn = 'body' | 'data' | 'raw';

/**
 * 参数序列化方式
 * - brackets: ids[]=1&ids[]=2&ids[]=3
 * - comma: ids=1,2,3
 * - indices: ids[0]=1&ids[1]=2&ids[2]=3
 * - repeat: ids=1&ids=2&ids=3
 */
export type ParamsSerializer = 'brackets' | 'comma' | 'indices' | 'repeat';

/**
 * 请求扩展选项
 */
export interface RequestOptions {
  /**
   * 是否开启取消重复请求
   * @default true
   */
  cancelDuplicateRequest?: boolean;

  /**
   * 是否开启 Loading 效果
   * @default false
   */
  loading?: boolean;

  /**
   * 响应数据的返回方式
   * @default 'data'
   */
  responseReturn?: ResponseReturn;

  /**
   * 是否显示 HTTP 错误消息（网络错误、超时等）
   * @default true
   */
  showErrorMessage?: boolean;

  /**
   * 是否显示业务错误消息（code !== 0 时）
   * @default true
   */
  showCodeMessage?: boolean;

  /**
   * 是否显示成功消息（code === 0 时）
   * @default false
   */
  showSuccessMessage?: boolean;

  /**
   * 成功消息内容（showSuccessMessage 为 true 时使用）
   */
  successMessage?: string;

  /**
   * 参数序列化方式
   */
  paramsSerializer?: ParamsSerializer;
}

/**
 * 完整的请求配置（Axios 配置 + 扩展选项）
 */
export type RequestClientConfig<D = any> = AxiosRequestConfig<D> &
  RequestOptions;

/**
 * API 函数使用的请求选项（简化版）
 * 用于 API 函数的可选参数
 */
export interface ApiRequestOptions {
  /**
   * 是否开启 Loading 效果
   * @default false
   */
  loading?: boolean;

  /**
   * 是否显示成功消息
   * @default false
   */
  showSuccessMessage?: boolean;

  /**
   * 成功消息内容
   */
  successMessage?: string;

  /**
   * 是否显示业务错误消息
   * @default true
   */
  showCodeMessage?: boolean;

  /**
   * 是否显示 HTTP 错误消息
   * @default true
   */
  showErrorMessage?: boolean;
}

/**
 * 请求响应类型
 */
export type RequestResponse<T = any> = AxiosResponse<T> & {
  config: RequestClientConfig<T>;
};

// ============================================================
// 响应数据类型
// ============================================================

/**
 * 标准 HTTP 响应格式
 */
export interface HttpResponse<T = any> {
  /** 业务状态码，0 表示成功 */
  code: number;
  /** 响应数据 */
  data: T;
  /** 响应消息 */
  message: string;
  /** 请求是否成功 */
  success?: boolean;
}

// ============================================================
// 拦截器类型
// ============================================================

/**
 * 请求拦截器配置
 */
export interface RequestInterceptorConfig {
  fulfilled?: (config: any) => any | Promise<any>;
  rejected?: (error: any) => any;
}

/**
 * 响应拦截器配置
 */
export interface ResponseInterceptorConfig {
  fulfilled?: (response: any) => any | Promise<any>;
  rejected?: (error: any) => any;
}

// ============================================================
// Token 相关类型
// ============================================================

/**
 * API 端点类型
 */
export type ApiEndpoint = 'admin' | 'tenant' | 'user';

/**
 * 刷新 Token 响应（后端原始格式）
 */
export interface RefreshTokenResultRaw {
  access_token: string;
  refresh_token?: string;
}

// ============================================================
// 错误处理类型
// ============================================================

/**
 * 错误消息生成函数
 */
export type MakeErrorMessageFn = (message: string, error: any) => void;

/**
 * 业务错误处理函数
 */
export type BusinessErrorHandler = (
  code: number,
  message: string,
  data: any,
) => void;

// ============================================================
// SSE 类型
// ============================================================

/**
 * SSE 请求选项
 */
export interface SseRequestOptions extends Omit<RequestInit, 'signal'> {
  /** 消息回调 */
  onMessage?: (message: string) => void;
  /** 结束回调 */
  onEnd?: () => void;
  /** 错误回调 */
  onError?: (error: Error) => void;
  /** 用于取消请求的 AbortController */
  abortController?: AbortController;
}

// ============================================================
// 文件上传类型
// ============================================================

/**
 * 文件上传数据
 */
export interface UploadFileData extends Record<string, any> {
  file: Blob | File;
}

/**
 * 上传进度回调
 */
export type UploadProgressCallback = (progress: {
  loaded: number;
  percent: number;
  total: number;
}) => void;

// ============================================================
// 请求客户端选项
// ============================================================

/**
 * 请求客户端创建选项
 */
export interface RequestClientOptions extends RequestOptions {
  /** 基础 URL */
  baseURL?: string;
  /** 超时时间（毫秒） */
  timeout?: number;
  /** 默认请求头 */
  headers?: Record<string, string>;
}
