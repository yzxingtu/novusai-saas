import { generateUUID } from '#/utils/common';

type HeaderLike =
  | Headers
  | Record<string, unknown>
  | {
      get?: (name: string) => null | string | undefined;
      set?: (name: string, value: string) => void;
    };

function normalizeTraceId(value: unknown): string {
  if (Array.isArray(value)) {
    for (const item of value) {
      const normalized = normalizeTraceId(item);
      if (normalized) return normalized;
    }
    return '';
  }

  const text = typeof value === 'string' ? value : String(value ?? '');
  const parts = text
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
  return parts[0] || '';
}

export function getTraceIdFromHeaders(headers?: HeaderLike | null): string {
  if (!headers) return '';

  if (typeof headers.get === 'function') {
    return (
      normalizeTraceId(headers.get('X-Trace-ID')) ||
      normalizeTraceId(headers.get('x-trace-id'))
    );
  }

  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === 'x-trace-id') {
      return normalizeTraceId(value);
    }
  }

  return '';
}

export function ensureTraceIdHeader(headers?: HeaderLike | null): string {
  const existing = getTraceIdFromHeaders(headers);
  if (existing) return existing;

  const traceId = generateUUID();
  if (!headers) return traceId;

  if (typeof headers.set === 'function') {
    headers.set('X-Trace-ID', traceId);
    return traceId;
  }

  (headers as Record<string, unknown>)['X-Trace-ID'] = traceId;
  return traceId;
}
