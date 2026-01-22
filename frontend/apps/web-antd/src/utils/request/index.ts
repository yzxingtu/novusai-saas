/**
 * HTTP 请求模块
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
 *   console.log(`上传进度: ${progress.percent}%`);
 * });
 *
 * // SSE 流式请求
 * await requestClient.postSSE('/api/chat', { message }, {
 *   onMessage: (msg) => console.log(msg),
 *   onEnd: () => console.log('结束'),
 * });
 * ```
 */

// 错误码导出
export {
  AUTH_ERROR_CODES,
  ErrorCode,
  isAuthError,
  isClientError,
  isServerError,
} from './error-codes';

// 请求实例导出
export { baseRequestClient, requestClient } from './instance';

// 拦截器导出
export {
  createAuthInterceptor,
  createBusinessErrorInterceptor,
  createErrorMessageInterceptor,
  createRequestInterceptor,
  createResponseDataInterceptor,
  createSuccessMessageInterceptor,
  getEndpointByPath,
  getEndpointByUrl,
} from './interceptors';

export type { AuthHandler, MessageHandler, TokenGetter } from './interceptors';

// 请求客户端导出
export { RequestClient } from './request-client';

// 类型导出
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
