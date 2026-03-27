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

import {
  collectVisualState,
  getPageContextHardLimitBytes,
  getPageContextSoftLimitBytes,
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

export interface PageAIStatBadge {
  className: string;
  key: string;
  label: string;
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

  function enrichPageContextWithOperations(
    ctx: PageContextValue,
    ops: readonly PageOperation[] = [],
  ): PageContextValue {
    if (!ctx) {
      return ctx;
    }
    if (
      options.normalizedPageMode.value === 'disabled' ||
      shouldDisablePageContext(options.disabledCapabilities.value)
    ) {
      return null;
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

    let pageData: Record<string, unknown> = {
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

    pageData = truncateFormFields(pageData);
    const pageContextHardLimit = getPageContextHardLimitBytes(
      options.pageContextLimitBytes.value,
    );
    pageData = guardPageDataSize(
      pageData,
      getPageContextSoftLimitBytes(pageContextHardLimit),
    );
    return { ...ctx, page_data: pageData };
  }

  const currentPageContext = computed(() =>
    enrichPageContextWithOperations(
      rawPageContext.value,
      currentPageOperations.value,
    ),
  );

  const hasFormalPageAIContext = computed(
    () =>
      !!rawPageContext.value &&
      !isFallbackOnlyPageContext(rawPageContext.value),
  );

  const hasPageAI = computed(
    () =>
      hasFormalPageAIContext.value || currentPageOperations.value.length > 0,
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
    () => currentPageOperations.value.length > 0,
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
    expandAllPageAIOperations,
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
