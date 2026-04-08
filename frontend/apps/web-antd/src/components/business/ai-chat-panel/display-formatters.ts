import { $t } from '#/locales';

function normalizeListItem(value: null | string | undefined): string {
  return typeof value === 'string' ? value.trim() : '';
}

function resolveListLocale(): string {
  const documentLocale =
    typeof document !== 'undefined'
      ? document.documentElement?.lang?.trim()
      : '';
  if (documentLocale) {
    return documentLocale;
  }

  const navigatorLocale =
    typeof navigator !== 'undefined' ? navigator.language?.trim() : '';
  if (navigatorLocale) {
    return navigatorLocale;
  }

  return 'en-US';
}

export function formatLocalizedList(
  values: Array<null | string | undefined>,
): string {
  const items = values.map(normalizeListItem).filter(Boolean);
  if (items.length === 0) {
    return '';
  }

  const locale = resolveListLocale();
  if (typeof Intl !== 'undefined' && typeof Intl.ListFormat === 'function') {
    try {
      return new Intl.ListFormat(locale, {
        style: 'long',
        type: 'conjunction',
      }).format(items);
    } catch {
      // Fall through to the plain-text fallback below.
    }
  }

  return items.join(', ');
}

export function formatKnowledgeBaseName(
  name?: null | string,
  knowledgeBaseId?: null | number | string,
): string {
  const normalizedName = normalizeListItem(name);
  if (normalizedName) {
    return normalizedName;
  }
  if (knowledgeBaseId === null || knowledgeBaseId === undefined) {
    return $t('common.notSet');
  }
  return $t('common.globalAiChat.knowledgeBaseFallback', {
    id: String(knowledgeBaseId),
  });
}

export function formatDurationSeconds(durationMs?: null | number): string {
  const duration = Number(durationMs ?? 0);
  return $t('common.globalAiChat.durationSeconds', {
    seconds: (duration / 1000).toFixed(1),
  });
}

export function formatToolStatusLabel(
  status?: null | string,
  waitingForConsent = false,
): string {
  if (status === 'running') {
    return waitingForConsent
      ? $t('common.globalAiChat.toolWaitingConfirm')
      : $t('common.globalAiChat.toolExecuting');
  }
  if (status === 'success') {
    return $t('common.globalAiChat.toolStatusOk');
  }
  if (status === 'error') {
    return $t('common.globalAiChat.toolStatusErr');
  }
  return normalizeListItem(status) || $t('common.globalAiChat.toolFailed');
}
