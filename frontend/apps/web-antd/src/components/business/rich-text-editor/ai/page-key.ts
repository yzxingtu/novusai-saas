/**
 * Normalize page keys to dot-notation so runtime adapters and route policies
 * can share the same lookup key.
 */
export function normalizeRuntimePageKey(raw: string): string {
  return String(raw ?? '')
    .trim()
    .replace(/^\//, '')
    .replaceAll('/', '.');
}
