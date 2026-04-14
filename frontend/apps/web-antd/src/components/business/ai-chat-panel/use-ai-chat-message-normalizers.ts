export function normalizeMergedTextPart(
  value: null | string | undefined,
): string {
  return String(value ?? '')
    .replaceAll('\r\n', '\n')
    .trim();
}

export function appendDistinctMergedTextPart(
  parts: string[],
  value: null | string | undefined,
): void {
  const normalized = normalizeMergedTextPart(value);
  if (!normalized) {
    return;
  }
  const previous = parts.length > 0 ? parts[parts.length - 1] : undefined;
  if (normalizeMergedTextPart(previous) === normalized) {
    return;
  }
  parts.push(String(value ?? ''));
}

export function normalizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item ?? '').trim())
    .filter((item) => item.length > 0);
}

export function normalizeOptionalString(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}

export function normalizeObjectRecord(
  value: unknown,
): null | Record<string, unknown> {
  if (!value || typeof value !== 'object') {
    return null;
  }
  return { ...(value as Record<string, unknown>) };
}

export function normalizeObjectRecordList(
  value: unknown,
): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => {
      return !!item && typeof item === 'object';
    })
    .map((item) => ({ ...item }));
}
