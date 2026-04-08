import { $t } from '#/locales';

const AI_RUNTIME_LOCALE_PREFIX = 'common.aiRuntime';

export function tAiRuntime(
  key: string,
  params?: Record<string, unknown>,
): string {
  const localeKey = `${AI_RUNTIME_LOCALE_PREFIX}.${key}`;
  return params ? $t(localeKey, params) : $t(localeKey);
}

export function tAiRuntimeSurfaceKind(kind: string): string {
  return tAiRuntime(`surfaceKind.${kind}`);
}
