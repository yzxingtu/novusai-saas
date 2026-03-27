import type { ComputedRef, Ref } from 'vue';

import type { AIPageMode } from '@vben/types';

import type { PageOperation } from './page-operation-registry';

import { computed, ref, watch } from 'vue';

import { formStateTracker } from '#/composables/use-form-state-tracker';
import { $t } from '#/locales';
import {
  canExposePageOperations,
  filterPageOperationsByPolicy,
  shouldDisablePageContext,
} from '#/utils/ai-page-capabilities';
import { isDevErrorMode } from '#/utils/request/app-env';

import {
  collectVisualState,
  getPageContextHardLimitBytes,
  getPageContextSoftLimitBytes,
  getSerializedPageDataBytes,
  guardPageDataSize,
  truncateFormFields,
} from './page-context-budget';
import {
  pageContextVersion,
  resolvePageContext,
} from './page-context-registry';
import { normalizePageKey } from './page-key-utils';
import {
  listPageOperations,
  pageOperationVersion,
} from './page-operation-registry';

type PageContextValue = ReturnType<typeof resolvePageContext>;

const FALLBACK_PAGE_CONTEXT_SOURCES = new Set([
  'dom_snapshot',
  'minimal_fallback',
]);
const PAGE_AI_PREVIEW_LIMIT = 4;
const SHOW_PAGE_AI_DIAGNOSTICS = isDevErrorMode();

export interface PageAIStatBadge {
  className: string;
  key: string;
  label: string;
}

export interface PageAIDiagnostics {
  compressed: boolean;
  fallbackOnly: boolean;
  finalBytes: number;
  finalOperationCount: number;
  hardLimitBytes: number;
  rawBytes: number;
  rawOperationCount: number;
  softLimitBytes: number;
  source: string;
}

interface UsePageAICapabilityOptions {
  disabledCapabilities: Ref<string[] | undefined>;
  modalState: Ref<Array<{ type: string }>>;
  normalizedPageMode: ComputedRef<AIPageMode>;
  pageAIPolicy: ComputedRef<{
    disabledCapabilities?: string[];
    disabledOperations?: string[];
    mode: AIPageMode;
  }>;
  pageContextKey: Ref<string | undefined>;
  pageContextLimitBytes: ComputedRef<number | undefined>;
}

function getPageContextSource(ctx: PageContextValue): null | string {
  const source = ctx?.page_data?.source;
  return typeof source === 'string' ? source : null;
}

function isFallbackOnlyPageContext(ctx: PageContextValue): boolean {
  const source = getPageContextSource(ctx);
  return !!source && FALLBACK_PAGE_CONTEXT_SOURCES.has(source);
}

export function usePageAICapability(options: UsePageAICapabilityOptions) {
  const rawPageContext = computed(() => {
    void pageContextVersion.value;
    return resolvePageContext(options.pageContextKey.value);
  });

  const resolvedPageKey = computed(() => {
    return (
      rawPageContext.value?.page_key ??
      (options.pageContextKey.value
        ? normalizePageKey(options.pageContextKey.value)
        : undefined)
    );
  });

  const currentPageOperations = computed(() => {
    void pageOperationVersion.value;
    const pageKey = resolvedPageKey.value;
    if (!pageKey) {
      return [];
    }
    return filterPageOperationsByPolicy(
      listPageOperations(pageKey),
      options.pageAIPolicy.value,
    );
  });

  function buildEnrichedPageAIState(
    ctx: PageContextValue,
    ops: readonly PageOperation[] = [],
  ): {
    context: PageContextValue;
    diagnostics: null | PageAIDiagnostics;
  } {
    if (!ctx) {
      return { context: ctx, diagnostics: null };
    }
    if (
      options.normalizedPageMode.value === 'disabled' ||
      shouldDisablePageContext(options.disabledCapabilities.value)
    ) {
      return { context: null, diagnostics: null };
    }

    let liveFormFields = ctx.page_data?.form_fields;
    if (formStateTracker.isOpenWithFallback(ctx.page_key)) {
      const descriptors = formStateTracker.getFieldDescriptors(ctx.page_key);
      if (descriptors && Object.keys(descriptors).length > 0) {
        liveFormFields = descriptors;
      }
    }

    const {
      available_operations: _availableOperations,
      visual_state: _visualState,
      ...basePageData
    } = ctx.page_data ?? {};

    const rawPageData: Record<string, unknown> = {
      ...basePageData,
      ...(liveFormFields ? { form_fields: liveFormFields } : {}),
      visual_state: collectVisualState(
        Array.isArray(options.modalState.value) ? options.modalState.value : [],
      ),
      ...(canExposePageOperations(options.normalizedPageMode.value) &&
      ops.length > 0
        ? {
            available_operations: ops.map((operation) => ({
              name: operation.name,
              label: operation.label,
              description: operation.description,
              readonly: operation.readonly,
              ...(operation.params ? { params: operation.params } : {}),
            })),
          }
        : {}),
    };

    const pageContextHardLimit = getPageContextHardLimitBytes(
      options.pageContextLimitBytes.value,
    );
    const softLimitBytes = getPageContextSoftLimitBytes(pageContextHardLimit);
    const rawBytes = getSerializedPageDataBytes(rawPageData);
    const rawOperationCount = Array.isArray(rawPageData.available_operations)
      ? rawPageData.available_operations.length
      : 0;

    let pageData = truncateFormFields(rawPageData);
    pageData = guardPageDataSize(pageData, softLimitBytes);
    const finalBytes = getSerializedPageDataBytes(pageData);
    const finalOperationCount = Array.isArray(pageData.available_operations)
      ? pageData.available_operations.length
      : 0;
    const diagnostics: PageAIDiagnostics = {
      compressed:
        rawBytes !== finalBytes ||
        rawOperationCount !== finalOperationCount ||
        pageData !== rawPageData,
      fallbackOnly: isFallbackOnlyPageContext({ ...ctx, page_data: pageData }),
      finalBytes,
      finalOperationCount,
      hardLimitBytes: pageContextHardLimit,
      rawBytes,
      rawOperationCount,
      softLimitBytes,
      source:
        getPageContextSource({ ...ctx, page_data: pageData }) || 'registered',
    };

    return {
      context: { ...ctx, page_data: pageData },
      diagnostics,
    };
  }

  const enrichedPageAIState = computed(() =>
    buildEnrichedPageAIState(rawPageContext.value, currentPageOperations.value),
  );

  const currentPageContext = computed(() => enrichedPageAIState.value.context);

  const pageAIDiagnostics = computed(() =>
    SHOW_PAGE_AI_DIAGNOSTICS ? enrichedPageAIState.value.diagnostics : null,
  );

  const pageAIFallbackOnly = computed(
    () =>
      !!currentPageContext.value &&
      isFallbackOnlyPageContext(currentPageContext.value),
  );

  const hasPageAI = computed(
    () => !!currentPageContext.value || currentPageOperations.value.length > 0,
  );

  const writablePageOperations = computed(() =>
    currentPageOperations.value.filter((operation) => !operation.readonly),
  );

  const readonlyPageOperations = computed(() =>
    currentPageOperations.value.filter((operation) => operation.readonly),
  );

  const pageAIDetailsExpanded = ref(false);
  const pageAIShowAllOperations = ref(false);

  watch(options.pageContextKey, () => {
    pageAIDetailsExpanded.value = false;
    pageAIShowAllOperations.value = false;
  });

  watch(hasPageAI, (hasValue) => {
    if (!hasValue) {
      pageAIDetailsExpanded.value = false;
      pageAIShowAllOperations.value = false;
    }
  });

  watch(
    () => currentPageOperations.value.length,
    (operationCount) => {
      if (operationCount <= PAGE_AI_PREVIEW_LIMIT) {
        pageAIShowAllOperations.value = false;
      }
    },
  );

  const pageAIStatBadges = computed(() => {
    const badges: PageAIStatBadge[] = [];

    if (pageAIFallbackOnly.value) {
      badges.push({
        className: 'bg-amber-500/10 text-amber-700',
        key: 'fallback',
        label: $t('common.aiPanel.pageAiFallbackBadge'),
      });
    }

    if (currentPageOperations.value.length > 0) {
      badges.push({
        className: 'bg-primary/8 text-primary/80',
        key: 'total',
        label: $t('common.aiPanel.pageAiOperationCount', {
          count: currentPageOperations.value.length,
        }),
      });
    }

    if (writablePageOperations.value.length > 0) {
      badges.push({
        className: 'bg-amber-500/10 text-amber-700',
        key: 'writable',
        label: $t('common.aiPanel.pageAiWritableCount', {
          count: writablePageOperations.value.length,
        }),
      });
    }

    if (readonlyPageOperations.value.length > 0) {
      badges.push({
        className: 'bg-blue-500/10 text-blue-700',
        key: 'readonly',
        label: $t('common.aiPanel.pageAiReadonlyCount', {
          count: readonlyPageOperations.value.length,
        }),
      });
    }

    return badges;
  });

  const hasExpandablePageAIDetails = computed(
    () => currentPageOperations.value.length > 0 || !!pageAIDiagnostics.value,
  );

  const pageAIVisibleOperations = computed(() =>
    pageAIShowAllOperations.value
      ? currentPageOperations.value
      : currentPageOperations.value.slice(0, PAGE_AI_PREVIEW_LIMIT),
  );

  const pageAIRemainingOperationCount = computed(() =>
    Math.max(
      currentPageOperations.value.length - pageAIVisibleOperations.value.length,
      0,
    ),
  );

  const pageAISummary = computed(() => {
    if (pageAIFallbackOnly.value) {
      if (currentPageOperations.value.length > 0) {
        return $t('common.aiPanel.pageAiFallbackSummaryWithOps', {
          count: currentPageOperations.value.length,
        });
      }
      return $t('common.aiPanel.pageAiFallbackSummary');
    }
    if (currentPageOperations.value.length > 0) {
      return $t('common.aiPanel.pageAiSummary', {
        count: currentPageOperations.value.length,
      });
    }
    return $t('common.aiPanel.pageAiNoOperations');
  });

  const resolvedPageAITitle = computed(() => {
    const rawTitle = currentPageContext.value?.page_title?.trim();
    if (!rawTitle) {
      return $t('common.aiPanel.pageAiCurrentPage');
    }

    const translatedTitle = $t(rawTitle);
    if (translatedTitle !== rawTitle) {
      return translatedTitle;
    }

    return rawTitle.includes('.') ? translatedTitle : rawTitle;
  });

  const pageAIRailTooltip = computed(
    () => `${resolvedPageAITitle.value} · ${pageAISummary.value}`,
  );
  const pageAIOperationCount = computed(
    () => currentPageOperations.value.length,
  );

  function togglePageAIDetails() {
    if (pageAIDetailsExpanded.value) {
      pageAIDetailsExpanded.value = false;
      pageAIShowAllOperations.value = false;
      return;
    }

    pageAIDetailsExpanded.value = true;
  }

  function expandAllPageAIOperations() {
    pageAIDetailsExpanded.value = true;
    pageAIShowAllOperations.value = true;
  }

  return {
    currentPageContext,
    currentPageOperations,
    pageAIOperationCount,
    pageAIDiagnostics,
    expandAllPageAIOperations,
    pageAIFallbackOnly,
    hasExpandablePageAIDetails,
    hasPageAI,
    pageAIDetailsExpanded,
    pageAIRailTooltip,
    pageAIRemainingOperationCount,
    pageAISummary,
    pageAIStatBadges,
    pageAIVisibleOperations,
    resolvedPageAITitle,
    togglePageAIDetails,
  };
}
