import type { ComputedRef, Ref } from 'vue';

import type { AIPageMode } from '@vben/types';

import type { PageOperation } from './page-operation-types';

import { computed, ref, watch } from 'vue';

import {
  getRuntimePageContextDiagnostics,
  getRuntimeThinPageContext,
} from '#/components/business/ai-runtime/runtime-bridge';
import { useDiagnosticsPolicy } from '#/composables/use-diagnostics-policy';
import { $t } from '#/locales';
import { filterPageOperationsByPolicy } from '#/utils/ai-page-capabilities';
import {
  buildPageOperation,
  buildRuntimePageOperationNames,
  hasRuntimePageState,
} from '#/utils/runtime-page-operations';

type ThinPageContextValue = ReturnType<typeof getRuntimeThinPageContext>;

export interface PageAIStatBadge {
  className: string;
  key: string;
  label: string;
}

export interface PageAIDiagnostics {
  finalBytes: number;
  interactablesCount: number;
  source: string;
  uiEpoch: number;
}

interface UsePageAICapabilityOptions {
  apiPrefix: Ref<string>;
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

function pageModeDisablesContext(mode: AIPageMode): boolean {
  return mode === 'disabled';
}

function resolveSummary(
  context: ThinPageContextValue,
  operationCount: number,
): string {
  if (!context) {
    return $t('common.aiPanel.pageAiNoOperations');
  }
  if (!hasRuntimePageState(context)) {
    const surfaceCount = context.surface_stack?.length ?? 0;
    if (surfaceCount > 1) {
      return $t('common.aiPanel.pageAiFallbackSummaryWithOps', {
        count: surfaceCount - 1,
      });
    }
    return $t('common.aiPanel.pageAiFallbackSummary');
  }
  if (operationCount > 0) {
    return $t('common.aiPanel.pageAiSummary', { count: operationCount });
  }
  return $t('common.aiPanel.pageAiNoOperations');
}

export function usePageAICapability(options: UsePageAICapabilityOptions) {
  void options.disabledCapabilities;
  void options.modalState;
  void options.pageContextLimitBytes;
  const { showDiagnostics } = useDiagnosticsPolicy({
    apiPrefix: options.apiPrefix,
  });

  const currentPageContext = computed(() => {
    if (pageModeDisablesContext(options.normalizedPageMode.value)) {
      return null;
    }
    return getRuntimeThinPageContext(options.pageContextKey.value);
  });

  const currentPageOperations = computed<PageOperation[]>(() => {
    const context = currentPageContext.value;
    if (!context) {
      return [];
    }
    const candidateNames = buildRuntimePageOperationNames(context);
    const operations: PageOperation[] = [];
    const seen = new Set<string>();
    for (const name of candidateNames) {
      const operation = buildPageOperation(name);
      if (!operation || seen.has(operation.name)) {
        continue;
      }
      seen.add(operation.name);
      operations.push(operation);
    }
    return filterPageOperationsByPolicy(operations, options.pageAIPolicy.value);
  });
  const pageAIOperationCount = computed(
    () => currentPageOperations.value.length,
  );

  const pageAIDiagnostics = computed<null | PageAIDiagnostics>(() => {
    if (!showDiagnostics.value || !currentPageContext.value) {
      return null;
    }
    const diagnostics = getRuntimePageContextDiagnostics();
    return {
      finalBytes: Number(diagnostics.size_bytes || 0),
      interactablesCount: Number(diagnostics.interactables_count || 0),
      source: String(diagnostics.source || 'ui_runtime'),
      uiEpoch: Number(diagnostics.ui_epoch || 0),
    };
  });

  const pageAIFallbackOnly = computed(() => {
    return (
      !!currentPageContext.value && !hasRuntimePageState(currentPageContext.value)
    );
  });
  const hasPageAI = computed(() => !!currentPageContext.value);
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

  const pageAIStatBadges = computed(() => {
    const badges: PageAIStatBadge[] = [];
    const activeForm = currentPageContext.value?.active_form_summary;
    if (activeForm?.mode) {
      badges.push({
        className: 'bg-primary/8 text-primary/80',
        key: 'form-mode',
        label: activeForm.mode,
      });
    }
    if ((currentPageContext.value?.surface_stack?.length ?? 0) > 1) {
      badges.push({
        className: 'bg-blue-500/10 text-blue-700',
        key: 'surfaces',
        label: $t('common.aiPanel.pageAiReadonlyCount', {
          count: (currentPageContext.value?.surface_stack?.length ?? 1) - 1,
        }),
      });
    }
    if (pageAIDiagnostics.value?.interactablesCount) {
      badges.push({
        className: 'bg-amber-500/10 text-amber-700',
        key: 'interactables',
        label: $t('common.aiPanel.pageAiOperationCount', {
          count: pageAIDiagnostics.value.interactablesCount,
        }),
      });
    }
    return badges;
  });

  const hasExpandablePageAIDetails = computed(
    () =>
      !!pageAIDiagnostics.value ||
      !!currentPageContext.value?.active_form_summary ||
      currentPageOperations.value.length > 0,
  );
  const pageAIVisibleOperations = computed<PageOperation[]>(() => {
    const operations = currentPageOperations.value;
    if (pageAIShowAllOperations.value) {
      return operations;
    }
    return operations.slice(0, 4);
  });
  const pageAIRemainingOperationCount = computed(() => {
    const remaining =
      currentPageOperations.value.length - pageAIVisibleOperations.value.length;
    return Math.max(remaining, 0);
  });
  const pageAISummary = computed(() =>
    resolveSummary(currentPageContext.value, pageAIOperationCount.value),
  );
  const resolvedPageAITitle = computed(() => {
    const rawTitle = currentPageContext.value?.page_title?.trim();
    return rawTitle || $t('common.aiPanel.pageAiCurrentPage');
  });
  const pageAIRailTooltip = computed(() => {
    if (pageAIOperationCount.value > 0) {
      return $t('common.aiPanel.pageAiOperationCount', {
        count: pageAIOperationCount.value,
      });
    }
    return $t('common.aiPanel.pageAiSupported');
  });

  function togglePageAIDetails() {
    pageAIDetailsExpanded.value = !pageAIDetailsExpanded.value;
    if (!pageAIDetailsExpanded.value) {
      pageAIShowAllOperations.value = false;
    }
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

export type UsePageAICapabilityReturn = ReturnType<typeof usePageAICapability>;
