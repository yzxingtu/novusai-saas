/**
 * Helpers for axios-style errors from requestClient / 解析 requestClient 抛出的类 Axios 错误
 */

import { $t } from '#/locales';

export function getErrorResponse(
  error: unknown,
): Record<string, unknown> | undefined {
  return (error as { response?: Record<string, unknown> } | undefined)
    ?.response;
}

export function getErrorStatus(error: unknown): number | undefined {
  return getErrorResponse(error)?.status as number | undefined;
}

export function getErrorData(
  error: unknown,
): Record<string, unknown> | undefined {
  return getErrorResponse(error)?.data as Record<string, unknown> | undefined;
}

export function getErrorMessage(error: unknown, fallbackKey: string): string {
  const responseMessage = getErrorData(error)?.message;
  if (typeof responseMessage === 'string' && responseMessage) {
    return responseMessage;
  }
  const errorMessage = (error as { message?: string } | undefined)?.message;
  return errorMessage || $t(fallbackKey);
}
