interface ApiEnvelope<T = unknown> {
  code: number;
  data: T;
  message: string;
}

function isApiEnvelope(value: unknown): value is ApiEnvelope {
  if (!value || typeof value !== 'object') return false;
  return 'code' in value && 'data' in value && 'message' in value;
}

export function unwrapApiData<T>(payload: unknown): T {
  let current: unknown = payload;
  let depth = 0;
  while (isApiEnvelope(current) && depth < 8) {
    current = current.data;
    depth += 1;
  }
  return current as T;
}
