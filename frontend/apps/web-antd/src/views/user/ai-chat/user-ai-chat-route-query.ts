import type { LocationQuery } from 'vue-router';

export function parsePositiveQueryNumber(
  value: LocationQuery[string] | undefined,
): number | undefined {
  const rawValue = Array.isArray(value) ? value[0] : value;
  if (typeof rawValue !== 'string') {
    return undefined;
  }
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

export function parseQueryText(
  value: LocationQuery[string] | undefined,
): string | undefined {
  const rawValue = Array.isArray(value) ? value[0] : value;
  if (typeof rawValue !== 'string') {
    return undefined;
  }
  const normalized = rawValue.trim();
  return normalized.length > 0 ? normalized : undefined;
}
