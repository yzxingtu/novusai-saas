import type { SupportedLanguagesType } from '@vben/locales';

import { loadLocaleMessages } from '@vben/locales';
import { preferences } from '@vben/preferences';

import { i18n } from './index';

export function resolveRuntimeLocale(): string {
  const runtimeLocale = String(i18n.global.locale.value || '').trim();

  if (runtimeLocale) {
    return runtimeLocale;
  }

  return String(preferences.app.locale || '').trim();
}

export async function syncRuntimeLocale(locale?: null | string): Promise<void> {
  const targetLocale =
    String(locale || '').trim() || String(preferences.app.locale || '').trim();

  if (!targetLocale) {
    return;
  }

  await loadLocaleMessages(targetLocale as SupportedLanguagesType);
}
