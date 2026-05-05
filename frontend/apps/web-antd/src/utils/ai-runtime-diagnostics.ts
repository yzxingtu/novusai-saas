const RETIRED_RUNTIME_DIAGNOSTIC_EXACT = new Set([
  'fetch_url',
  'hosted_web_search',
  'native_web_search',
  'supports_hosted_web_search',
  'web_research',
  'web_search',
  'web_search_runtime',
]);

const RETIRED_RUNTIME_DIAGNOSTIC_FRAGMENTS = [
  'hosted_web_search',
  'native_web_search',
  'response_web_search_call',
  'web_research',
  'web_search_call',
  '联网搜索',
  '网页搜索',
  '原生搜索',
];

function normalizeRuntimeDiagnosticToken(value: string): string {
  return value.trim().toLowerCase().replaceAll(/[.\-:\s]+/g, '_');
}

export function isRetiredRuntimeDiagnosticText(value: unknown): boolean {
  if (typeof value !== 'string') {
    return false;
  }
  const text = value.trim();
  if (!text) {
    return false;
  }
  const normalized = normalizeRuntimeDiagnosticToken(text);
  return (
    RETIRED_RUNTIME_DIAGNOSTIC_EXACT.has(normalized) ||
    RETIRED_RUNTIME_DIAGNOSTIC_FRAGMENTS.some((fragment) =>
      normalized.includes(fragment),
    )
  );
}

export function visibleRuntimeDiagnosticTokens(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const out: string[] = [];
  for (const item of value) {
    const text = typeof item === 'string' ? item.trim() : '';
    if (!text || isRetiredRuntimeDiagnosticText(text) || out.includes(text)) {
      continue;
    }
    out.push(text);
  }
  return out;
}

export function containsRetiredRuntimeDiagnosticValue(value: unknown): boolean {
  if (isRetiredRuntimeDiagnosticText(value)) {
    return true;
  }
  if (Array.isArray(value)) {
    return value.some((item) => containsRetiredRuntimeDiagnosticValue(item));
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).some(
      ([key, item]) =>
        isRetiredRuntimeDiagnosticText(key) ||
        containsRetiredRuntimeDiagnosticValue(item),
    );
  }
  return false;
}
