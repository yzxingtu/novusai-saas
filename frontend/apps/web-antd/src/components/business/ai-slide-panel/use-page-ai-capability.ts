import type { ComputedRef, Ref } from 'vue';

import type { AIPageMode } from '@vben/types';

import type { PageOperation } from './page-operation-types';

import { computed, ref, watch } from 'vue';

import { $t } from '#/locales';
import {
  getRuntimePageContextDiagnostics,
  getRuntimeThinPageContext,
} from '#/components/business/ai-runtime/runtime-bridge';
import { filterPageOperationsByPolicy } from '#/utils/ai-page-capabilities';
import { isDevErrorMode } from '#/utils/request/app-env';

type ThinPageContextValue = ReturnType<typeof getRuntimeThinPageContext>;

const SHOW_PAGE_AI_DIAGNOSTICS = isDevErrorMode();

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

const UI_TOOL_META: Record<
  string,
  Omit<PageOperation, 'description' | 'handler' | 'label' | 'name'>
> = {
  ui_click: { readonly: false },
  ui_fill_form: { readonly: false },
  ui_get_form_state: { readonly: true },
  ui_get_snapshot: { readonly: true },
  ui_list_interactables: { readonly: true },
  ui_open_surface: { readonly: false },
  ui_read_region: { readonly: true },
  ui_read_table: { readonly: true },
  ui_set_field: { readonly: false },
  ui_submit_form: { readonly: false },
};

function toToolLabel(name: string): string {
  if (!name) {
    return '';
  }
  const fallback = name
    .replace(/^ui_/, '')
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
  const key = `common.aiPanel.toolLabel.${name}`;
  const translated = $t(key);
  return translated === key ? fallback : translated;
}

function toToolDescription(name: string): string {
  const key = `common.aiPanel.toolDesc.${name}`;
  const translated = $t(key);
  return translated === key ? toToolLabel(name) : translated;
}

function buildToolOperation(name: string): null | PageOperation {
  const normalizedName = String(name || '').trim();
  if (!normalizedName.startsWith('ui_')) {
    return null;
  }
  return {
    name: normalizedName,
    label: toToolLabel(normalizedName),
    description: toToolDescription(normalizedName),
    readonly: UI_TOOL_META[normalizedName]?.readonly ?? true,
  };
}

function resolveSummary(context: ThinPageContextValue): string {
  if (!context) {
    return $t('common.aiPanel.pageAiNoOperations');
  }
  const activeForm = context.active_form_summary;
  if (activeForm) {
    const remaining = activeForm.remaining_required_fields?.length ?? 0;
    return remaining > 0
      ? $t('common.aiPanel.pageAiSummary', { count: remaining })
      : $t('common.aiPanel.pageAiFallbackSummary');
  }
  const surfaceCount = context.surface_stack?.length ?? 0;
  if (surfaceCount > 1) {
    return $t('common.aiPanel.pageAiFallbackSummaryWithOps', {
      count: surfaceCount - 1,
    });
  }
  return $t('common.aiPanel.pageAiFallbackSummary');
}

export function usePageAICapability(options: UsePageAICapabilityOptions) {
  void options.disabledCapabilities;
  void options.modalState;
  void options.pageContextLimitBytes;

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
    const candidateNames = [
      ...(context.suggested_tools?.primary ?? []),
      ...(context.suggested_tools?.secondary ?? []),
    ];
    const operations: PageOperation[] = [];
    const seen = new Set<string>();
    for (const name of candidateNames) {
      const operation = buildToolOperation(name);
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

  const pageAIDiagnostics = computed<PageAIDiagnostics | null>(() => {
    if (!SHOW_PAGE_AI_DIAGNOSTICS || !currentPageContext.value) {
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
    const reason = currentPageContext.value?.suggested_tools?.reason || '';
    return reason.includes('fallback');
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
    return remaining > 0 ? remaining : 0;
  });
  const pageAISummary = computed(() => resolveSummary(currentPageContext.value));
  const resolvedPageAITitle = computed(() => {
    const rawTitle = currentPageContext.value?.page_title?.trim();
    return rawTitle || $t('common.aiPanel.pageAiCurrentPage');
  });
  const pageAIRailTooltip = computed(
    () => `${resolvedPageAITitle.value} · ${pageAISummary.value}`,
  );

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
