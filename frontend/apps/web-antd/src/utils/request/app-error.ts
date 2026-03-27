import type { AxiosResponseHeaders, RawAxiosResponseHeaders } from 'axios';

import { isDevErrorMode } from './app-env';

export type AppErrorSource =
  | 'business'
  | 'http'
  | 'network'
  | 'sse'
  | 'timeout'
  | 'unknown';

/**
 * Unified app error payload for HTTP/SSE/UI.
 * 统一错误对象，覆盖 HTTP/SSE/UI 展示。
 */
export interface AppErrorInfo {
  code?: number | string;
  debugData?: unknown;
  debugMessage?: string;
  message: string;
  raw?: unknown;
  source: AppErrorSource;
  status?: number;
  traceId?: string;
}

type Translator = (key: string) => string;

function getFallbackByStatus(status?: number, t?: Translator): string {
  const map: Record<number, string> = {
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
  const key = status ? map[status] : undefined;
  if (key) {
    return t ? t(key) : key;
  }
  return t ? t('common.requestFailed') : 'Request failed';
}

function maybeExtractMessage(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function toHeadersLike(
  headers: unknown,
): AxiosResponseHeaders | Headers | RawAxiosResponseHeaders | undefined {
  if (!headers) return undefined;
  if (headers instanceof Headers) return headers;
  return headers as AxiosResponseHeaders | RawAxiosResponseHeaders;
}

function getTraceIdFromHeadersLike(
  headers?: AxiosResponseHeaders | Headers | RawAxiosResponseHeaders,
): string {
  if (!headers) return '';
  if (headers instanceof Headers) {
    return headers.get('x-trace-id') || headers.get('X-Trace-ID') || '';
  }
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() !== 'x-trace-id') continue;
    if (Array.isArray(value)) return String(value[0] ?? '');
    return typeof value === 'string' ? value : String(value ?? '');
  }
  return '';
}

export function getTraceIdFromErrorBody(data: any): string | undefined {
  const traceId = data?.trace_id ?? data?.traceId;
  return typeof traceId === 'string' && traceId.trim() ? traceId : undefined;
}

export function normalizeHttpError(
  error: any,
  t?: Translator,
  fallbackMessage?: string,
): AppErrorInfo {
  if (isAppErrorInfo(error?.appError)) {
    return error.appError;
  }
  const responseData = error?.response?.data;
  const status = error?.response?.status as number | undefined;
  const headers = toHeadersLike(error?.response?.headers);
  const traceId =
    getTraceIdFromErrorBody(responseData) ||
    getTraceIdFromHeadersLike(headers) ||
    undefined;

  let source: AppErrorSource = 'business';
  if (error?.message?.includes?.('timeout')) {
    source = 'timeout';
  } else if ((error?.toString?.() ?? '').includes('Network Error')) {
    source = 'network';
  } else if (responseData?.code === null || responseData?.code === undefined) {
    source = 'http';
  }

  const message =
    maybeExtractMessage(responseData?.message) ||
    maybeExtractMessage(responseData?.error) ||
    maybeExtractMessage(responseData?.msg) ||
    maybeExtractMessage(fallbackMessage) ||
    getFallbackByStatus(status, t);

  const debugPayload = responseData?.debug ?? responseData?.data;
  const debugMessage =
    maybeExtractMessage(responseData?.debug?.message) ||
    maybeExtractMessage(responseData?.debug?.detail) ||
    maybeExtractMessage(error?.message);

  return {
    code: responseData?.code,
    debugData: isDevErrorMode() ? debugPayload : undefined,
    debugMessage: isDevErrorMode() ? debugMessage : undefined,
    message,
    raw: error,
    source,
    status,
    traceId,
  };
}

export function normalizeSseEventError(
  event: Record<string, unknown>,
  t?: Translator,
): AppErrorInfo {
  const message =
    maybeExtractMessage(event.message) ||
    maybeExtractMessage(event.error) ||
    (t ? t('common.requestFailed') : 'Request failed');

  return {
    code: (event.code as number | string | undefined) ?? undefined,
    debugData: isDevErrorMode() ? event.debug : undefined,
    debugMessage: isDevErrorMode()
      ? maybeExtractMessage((event.debug as any)?.detail)
      : undefined,
    message,
    raw: event,
    source: 'sse',
    traceId: maybeExtractMessage(event.trace_id) || undefined,
  };
}

export function normalizeSseTransportError(
  error: unknown,
  t?: Translator,
): AppErrorInfo {
  if (isAppErrorInfo(error)) {
    return error;
  }
  if (error && typeof error === 'object') {
    return normalizeHttpError(
      error as any,
      t,
      (error as Error).message ||
        (t ? t('common.requestFailed') : 'Request failed'),
    );
  }
  const fallback = t ? t('common.requestFailed') : 'Request failed';
  return {
    message: typeof error === 'string' && error ? error : fallback,
    raw: error,
    source: 'unknown',
  };
}

export function isAppErrorInfo(error: unknown): error is AppErrorInfo {
  if (!error || typeof error !== 'object') return false;
  return typeof (error as AppErrorInfo).message === 'string';
}

export function formatAppErrorMessage(
  appError: AppErrorInfo,
  t?: Translator,
): string {
  const traceLabel = t ? t('common.http.traceId') : 'Trace ID';
  const traceSuffix = appError.traceId
    ? ` (${traceLabel}: ${appError.traceId})`
    : '';
  if (isDevErrorMode() && appError.debugMessage) {
    return `${appError.message}${traceSuffix}\n${appError.debugMessage}`;
  }
  return `${appError.message}${traceSuffix}`;
}

export function toErrorWithAppError(
  appError: AppErrorInfo,
): Error & { appError: AppErrorInfo; traceId?: string } {
  const err = new Error(appError.message) as Error & {
    appError: AppErrorInfo;
    traceId?: string;
  };
  err.appError = appError;
  if (appError.traceId) {
    err.traceId = appError.traceId;
  }
  return err;
}
