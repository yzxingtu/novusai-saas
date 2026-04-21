import type { ToolCallEvent } from './types';

import { $t } from '#/locales';

export interface SearchResultItem {
  snippet?: string;
  title: string;
  url: string;
}

export interface SearchSummary {
  fallbackReason?: string;
  failureReason?: string;
  items: SearchResultItem[];
  nativeFailureKind?: string;
  provider?: string;
  providerChain?: string[];
  resultCount?: number;
  selectedBackend?: string;
  status?: string;
}

export function getToolCallSummaryPayload(
  tc: Pick<ToolCallEvent, 'summaryPayload'>,
) {
  return tc.summaryPayload && typeof tc.summaryPayload === 'object'
    ? tc.summaryPayload
    : null;
}

function toSearchResultItems(value: unknown): SearchResultItem[] {
  if (!Array.isArray(value)) return [];
  const items: SearchResultItem[] = [];
  for (const item of value) {
    if (!item || typeof item !== 'object') continue;
    const title = typeof item.title === 'string' ? item.title.trim() : '';
    const url = typeof item.url === 'string' ? item.url.trim() : '';
    const snippet = typeof item.snippet === 'string' ? item.snippet.trim() : '';
    if (!title || !url) continue;
    items.push({
      title,
      url,
      snippet: snippet || undefined,
    });
  }
  return items;
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0);
}

export function getSearchSummary(
  tc: Pick<ToolCallEvent, 'summaryPayload'>,
): null | SearchSummary {
  const summaryPayload = getToolCallSummaryPayload(tc);
  if (!summaryPayload) return null;

  const provider =
    typeof summaryPayload.provider === 'string'
      ? summaryPayload.provider.trim()
      : '';
  const status =
    typeof summaryPayload.status === 'string'
      ? summaryPayload.status.trim()
      : '';
  const failureReason =
    typeof summaryPayload.failure_reason === 'string'
      ? summaryPayload.failure_reason.trim()
      : '';
  const fallbackReason =
    typeof summaryPayload.fallback_reason === 'string'
      ? summaryPayload.fallback_reason.trim()
      : '';
  const selectedBackend =
    typeof summaryPayload.selected_backend === 'string'
      ? summaryPayload.selected_backend.trim()
      : '';
  const nativeFailureKind =
    typeof summaryPayload.native_failure_kind === 'string'
      ? summaryPayload.native_failure_kind.trim()
      : '';
  const providerChain = toStringList(summaryPayload.provider_chain);
  const items = toSearchResultItems(summaryPayload.items);
  let resultCount: number | undefined;
  if (typeof summaryPayload.result_count === 'number') {
    resultCount = summaryPayload.result_count;
  } else if (items.length > 0) {
    resultCount = items.length;
  }

  if (
    !provider &&
    !status &&
    !failureReason &&
    !fallbackReason &&
    !selectedBackend &&
    !nativeFailureKind &&
    providerChain.length === 0 &&
    items.length === 0
  ) {
    return null;
  }

  return {
    fallbackReason: fallbackReason || undefined,
    failureReason: failureReason || undefined,
    items,
    nativeFailureKind: nativeFailureKind || undefined,
    provider: provider || undefined,
    providerChain: providerChain.length > 0 ? providerChain : undefined,
    resultCount,
    selectedBackend: selectedBackend || undefined,
    status: status || undefined,
  };
}

export function getSearchFallbackNotice(summary: SearchSummary): null | string {
  const fallbackReason = summary.fallbackReason ?? '';
  if (!fallbackReason) {
    return null;
  }
  if (
    fallbackReason.includes('default_verified_target_unavailable') ||
    fallbackReason.includes('untrusted_openai_compatible_runtime_target')
  ) {
    return $t('common.globalAiChat.toolSearchFallbackNeedVerifiedNativeTarget');
  }
  if (
    summary.nativeFailureKind === 'unsupported' &&
    summary.selectedBackend?.startsWith('public:')
  ) {
    return $t('common.globalAiChat.toolSearchFallbackNativeUnsupported');
  }
  return null;
}

export function getSearchProviderLabel(provider?: string) {
  switch (provider) {
    case 'baidu_public': {
      return $t('common.globalAiChat.toolSearchSourceBaidu');
    }
    case 'native_hosted': {
      return $t('common.globalAiChat.toolSearchSourceNative');
    }
    case 'so360_public': {
      return $t('common.globalAiChat.toolSearchSource360');
    }
    default: {
      return provider || '';
    }
  }
}

export function getSearchStatusLabel(status?: string) {
  switch (status) {
    case 'no_results': {
      return $t('common.globalAiChat.toolSearchStatusNoResults');
    }
    case 'source_blocked': {
      return $t('common.globalAiChat.toolSearchStatusBlocked');
    }
    case 'source_challenged': {
      return $t('common.globalAiChat.toolSearchStatusChallenged');
    }
    case 'source_unavailable': {
      return $t('common.globalAiChat.toolSearchStatusUnavailable');
    }
    case 'success': {
      return $t('common.globalAiChat.toolSearchStatusSuccess');
    }
    default: {
      return status || '';
    }
  }
}
