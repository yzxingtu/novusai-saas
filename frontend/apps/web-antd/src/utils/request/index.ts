/**
 * HTTP request module
 * HTTP 请求模块
 *
 * Unified export of request client, interceptors, error codes, etc.
 * External modules only need to import from here.
 * 统一导出请求客户端、拦截器、错误码等。
 * 外部模块只需从此导入。
 *
 * @module utils/request
 *
 * @example
 * ```ts
 * import { requestClient } from '#/utils/request';
 *
 * // 基本请求
 * const data = await requestClient.get('/api/users');
 *
 * // 带选项的请求
 * const data = await requestClient.post('/api/users', userData, {
 *   loading: true,
 *   showSuccessMessage: true,
 *   successMessage: '创建成功',
 * });
 *
 * // 文件上传
 * await requestClient.upload('/api/upload', { file }, {}, (progress) => {
 *   // 上传进度: ${progress.percent}%
 * });
 *
 * // SSE 流式请求
 * await requestClient.postSSE('/api/chat', { message }, {
 *   onMessage: (msg) => {},
 *   onEnd: () => {},
 * });
 * ```
 */

export { isDevErrorMode } from './app-env';

export {
  formatAppErrorMessage,
  isAppErrorInfo,
  normalizeHttpError,
  normalizeSseEventError,
  normalizeSseTransportError,
  toErrorWithAppError,
} from './app-error';

export type { AppErrorInfo, AppErrorSource } from './app-error';

export { getEndpointByUrl } from './endpoint';
// Error codes / 错误码导出
export {
  AUTH_ERROR_CODES,
  ErrorCode,
  isAuthError,
  isClientError,
  isServerError,
} from './error-codes';
// 请求实例导出 / export configured request clients
export { baseRequestClient, requestClient } from './instance';
// Interceptor creation functions / 拦截器创建函数导出
export {
  createAuthInterceptor,
  createBusinessErrorInterceptor,
  createErrorMessageInterceptor,
  createRequestInterceptor,
  createResponseDataInterceptor,
  createSuccessMessageInterceptor,
} from './interceptors';

export type { AuthHandler, MessageHandler, TokenGetter } from './interceptors';

// Request client instances / 请求客户端实例导出
export { RequestClient } from './request-client';

// Types / 类型导出
export type {
  ApiEndpoint,
  ApiRequestOptions,
  BusinessErrorHandler,
  HttpResponse,
  MakeErrorMessageFn,
  ParamsSerializer,
  RefreshTokenResultRaw,
  RequestClientConfig,
  RequestClientOptions,
  RequestInterceptorConfig,
  RequestOptions,
  RequestResponse,
  ResponseInterceptorConfig,
  ResponseReturn,
  SseRequestOptions,
  UploadFileData,
  UploadProgressCallback,
} from './types';
