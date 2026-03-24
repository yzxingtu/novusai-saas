/**
 * Helpers for axios-style errors from requestClient / 解析 requestClient 抛出的类 Axios 错误
 */

import { message } from 'ant-design-vue';

import { $t } from '#/locales';
import {
  formatAppErrorMessage,
  normalizeHttpError,
} from '#/utils/request/app-error';

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

function isRequestLikeError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const candidate = error as Record<string, unknown>;
  return Boolean(
    candidate.appError ||
      candidate.response ||
      candidate.traceId ||
      candidate.trace_id,
  );
}

export function getErrorMessage(error: unknown, fallbackKey: string): string {
  const fallbackMessage = $t(fallbackKey);
  if (isRequestLikeError(error)) {
    return formatAppErrorMessage(
      normalizeHttpError(error, $t, fallbackMessage),
      $t,
    );
  }
  const errorMessage = (error as { message?: string } | undefined)?.message;
  return errorMessage || fallbackMessage;
}

export function showRequestError(
  error: unknown,
  fallbackKey: string,
): string {
  const errorMessage = getErrorMessage(error, fallbackKey);
  message.error(errorMessage);
  return errorMessage;
}
