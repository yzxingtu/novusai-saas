import { describe, expect, it } from 'vitest';

import {
  formatAppErrorMessage,
  normalizeHttpError,
  normalizeSseEventError,
} from '../app-error';

describe('request app-error', () => {
  it('normalizes HTTP error with body trace_id and code', () => {
    const appError = normalizeHttpError({
      response: {
        data: {
          code: 5000,
          message: 'AI provider failed',
          trace_id: 'trace-body-1',
        },
        status: 500,
      },
    });

    expect(appError.message).toBe('AI provider failed');
    expect(appError.code).toBe(5000);
    expect(appError.status).toBe(500);
    expect(appError.traceId).toBe('trace-body-1');
  });

  it('falls back to header trace id when body trace is missing', () => {
    const appError = normalizeHttpError({
      response: {
        data: {
          message: 'Server error',
        },
        headers: {
          'X-Trace-ID': 'trace-header-2',
        },
        status: 500,
      },
    });

    expect(appError.traceId).toBe('trace-header-2');
  });

  it('normalizes SSE event error payload', () => {
    const appError = normalizeSseEventError({
      code: 'STREAM_ERROR',
      error: true,
      message: 'stream broken',
      trace_id: 'trace-sse-3',
    });

    expect(appError.source).toBe('sse');
    expect(appError.message).toBe('stream broken');
    expect(appError.traceId).toBe('trace-sse-3');
    expect(formatAppErrorMessage(appError)).toContain('trace-sse-3');
  });

  it('keeps client-facing auth errors concise', () => {
    const message = formatAppErrorMessage({
      debugMessage: 'Request failed with status code 401',
      message: '用户名或密码错误',
      source: 'business',
      status: 401,
      traceId: 'trace-auth-4',
    });

    expect(message).toBe('用户名或密码错误');
  });

  it('preserves trace id for server errors', () => {
    const message = formatAppErrorMessage({
      message: '服务器开小差了',
      source: 'http',
      status: 500,
      traceId: 'trace-server-5',
    });

    expect(message).toContain('trace-server-5');
  });
});
