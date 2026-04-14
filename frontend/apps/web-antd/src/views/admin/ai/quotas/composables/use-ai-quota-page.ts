import type {
  AIQuotaDiagnosticInfo,
  AIQuotaDiagnosticsSummaryInfo,
  AIRateLimitDiagnosticInfo,
  AIRateLimitInfo,
} from '#/api/admin/ai';

import { computed, onMounted, ref } from 'vue';

import {
  deleteAIQuotaApi,
  deleteAIRateLimitApi,
  getAIModelSelectApi,
  getAIQuotaListApi,
  getAIQuotaSummaryApi,
  getAIRateLimitListApi,
} from '#/api/admin/ai';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { buildPageAIFormExtraData, useCrudList } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, getRateLimitFormDefaults } from '../data';
import Form from '../modules/form.vue';

export type QuotaPageTab = 'quotas' | 'rateLimits';

export interface HeroChip {
  className: string;
  icon: string;
  key: string;
  text: string;
}

export interface HeroMetric {
  key: string;
  label: string;
  value: number;
}

export interface RateLimitFormExposed {
  openEdit: (row: AIRateLimitInfo, extraData?: Record<string, unknown>) => void;
  openNew: (extraData?: Record<string, unknown>) => void;
}

export interface SelectOption {
  label: string;
  value: number;
}

export interface SharedFilters {
  is_active?: 'false' | 'true';
  model_id?: number;
  tenant_id?: number;
}

const AI_PAGE_KEY = 'admin.ai.quotas';

const EMPTY_SUMMARY: AIQuotaDiagnosticsSummaryInfo = {
  active_quota_rules: 0,
  active_rate_limit_rules: 0,
  hard_quota_rules: 0,
  quota_exceeded_rules: 0,
  quota_warning_rules: 0,
  rate_limit_exceeded_rules: 0,
  rate_limit_warning_rules: 0,
  soft_quota_rules: 0,
  total_quota_rules: 0,
  total_rate_limit_rules: 0,
};

function buildRateLimitExtraData() {
  return buildPageAIFormExtraData({ pageKey: AI_PAGE_KEY });
}

export function useAIQuotaPage() {
  const activeTab = ref<QuotaPageTab>('quotas');
  const modelOptions = ref<SelectOption[]>([]);
  const quotaPeriod = ref<string>();
  const quotaType = ref<string>();
  const rateLimitFormRef = ref<RateLimitFormExposed>();
  const sharedFilters = ref<SharedFilters>({});
  const summary = ref<AIQuotaDiagnosticsSummaryInfo>({ ...EMPTY_SUMMARY });
  const summaryLoading = ref(false);
  const tenantOptions = ref<SelectOption[]>([]);

  const activeTabTitle = computed(() =>
    activeTab.value === 'quotas'
      ? $t('admin.ai.quota.title')
      : $t('admin.ai.rateLimit.title'),
  );

  const selectedTenantLabel = computed(() => {
    return tenantOptions.value.find(
      (option) => option.value === sharedFilters.value.tenant_id,
    )?.label;
  });

  const selectedModelLabel = computed(() => {
    return modelOptions.value.find(
      (option) => option.value === sharedFilters.value.model_id,
    )?.label;
  });

  const heroMetrics = computed<HeroMetric[]>(() => [
    {
      key: 'activeQuotaRules',
      label: $t('admin.ai.quota.summary.activeRules'),
      value: summary.value.active_quota_rules,
    },
    {
      key: 'hardQuotaRules',
      label: $t('admin.ai.quota.summary.blockRules'),
      value: summary.value.hard_quota_rules,
    },
    {
      key: 'quotaRisks',
      label: $t('admin.ai.quota.summary.riskRules'),
      value:
        summary.value.quota_warning_rules + summary.value.quota_exceeded_rules,
    },
    {
      key: 'activeRateLimits',
      label: $t('admin.ai.quota.summary.rateLimitRules'),
      value: summary.value.active_rate_limit_rules,
    },
  ]);

  const heroChips = computed<HeroChip[]>(() => {
    const chips: HeroChip[] = [
      {
        key: 'tab',
        icon: 'lucide:layers-3',
        className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
        text: activeTabTitle.value,
      },
      {
        key: 'focus',
        icon: 'lucide:scan-search',
        className: 'bg-background/90 text-foreground',
        text: `${$t('admin.ai.quota.runtime')} / ${$t('admin.ai.quota.response')} / ${$t('admin.ai.quota.remaining')}`,
      },
    ];

    if (selectedTenantLabel.value || selectedModelLabel.value) {
      chips.push({
        key: 'filters',
        icon: 'lucide:filter',
        className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
        text: [selectedTenantLabel.value, selectedModelLabel.value]
          .filter(Boolean)
          .join(' / '),
      });
    }

    return chips;
  });

  async function loadSummary() {
    summaryLoading.value = true;
    try {
      summary.value = await getAIQuotaSummaryApi();
    } catch {
      // request interceptor handles errors / 请求拦截器统一处理错误
    } finally {
      summaryLoading.value = false;
    }
  }

  async function loadSelectOptions() {
    try {
      const [tenantResult, modelResult] = await Promise.all([
        getTenantSelectApi({ is_active: 'true' }),
        getAIModelSelectApi({ is_active: 'true' }),
      ]);
      tenantOptions.value = (tenantResult.items as SelectOption[]) || [];
      modelOptions.value = (modelResult.items as SelectOption[]) || [];
    } catch {
      tenantOptions.value = [];
      modelOptions.value = [];
    }
  }

  function buildSharedSearchParams() {
    return {
      ...(sharedFilters.value.tenant_id
        ? { 'filter[tenant_id][eq]': sharedFilters.value.tenant_id }
        : {}),
      ...(sharedFilters.value.model_id
        ? { 'filter[model_id][eq]': sharedFilters.value.model_id }
        : {}),
      ...(sharedFilters.value.is_active === undefined
        ? {}
        : { 'filter[is_active][eq]': sharedFilters.value.is_active }),
    };
  }

  function buildQuotaSearchParams() {
    return {
      ...buildSharedSearchParams(),
      ...(quotaPeriod.value ? { 'filter[period][eq]': quotaPeriod.value } : {}),
      ...(quotaType.value ? { 'filter[quota_type][eq]': quotaType.value } : {}),
    };
  }

  function buildRateLimitSearchParams() {
    return buildSharedSearchParams();
  }

  const {
    list: quotas,
    total: quotaTotal,
    loading: quotaLoading,
    currentPage: quotaPage,
    pageSize: quotaPageSize,
    FormDrawer: QuotaFormDrawer,
    loadList: loadQuotas,
    onCreate: openQuotaCreate,
    onDelete: deleteQuota,
    onEdit: editQuota,
    onPageChange: onQuotaPageChange,
    onSearch: onQuotaSearch,
  } = useCrudList<AIQuotaDiagnosticInfo>({
    api: {
      list: getAIQuotaListApi,
      delete: deleteAIQuotaApi,
      resource: '/admin/ai/quotas',
    },
    formComponent: Form,
    formDefaults: getFormDefaults,
    i18nPrefix: 'admin.ai.quota',
    nameField: 'id',
    pageSize: 9,
    createPermission: 'ai_quota:create',
  });

  const {
    list: rateLimits,
    total: rateLimitTotal,
    loading: rateLimitLoading,
    currentPage: rateLimitPage,
    pageSize: rateLimitPageSize,
    loadList: loadRateLimits,
    onDelete: deleteRateLimit,
    onPageChange: onRateLimitPageChange,
    onSearch: onRateLimitSearch,
  } = useCrudList<AIRateLimitDiagnosticInfo>({
    api: {
      list: getAIRateLimitListApi,
      delete: deleteAIRateLimitApi,
      resource: '/admin/ai/quotas/rate-limits',
    },
    formDefaults: getRateLimitFormDefaults,
    i18nPrefix: 'admin.ai.rateLimit',
    nameField: 'id',
    pageSize: 9,
    createPermission: 'ai_quota:create_rate_limit',
  });

  function applyFilters() {
    onQuotaSearch(buildQuotaSearchParams());
    onRateLimitSearch(buildRateLimitSearchParams());
  }

  function handleActiveFilterChange(value: unknown) {
    sharedFilters.value.is_active =
      value === 'true' || value === 'false' ? value : undefined;
    applyFilters();
  }

  function handleModelFilterChange(value: unknown) {
    sharedFilters.value.model_id =
      typeof value === 'number' ? value : undefined;
    applyFilters();
  }

  function handleQuotaPeriodChange(value: unknown) {
    quotaPeriod.value = typeof value === 'string' ? value : undefined;
    applyFilters();
  }

  function handleQuotaTypeChange(value: unknown) {
    quotaType.value = typeof value === 'string' ? value : undefined;
    applyFilters();
  }

  function handleTabChange(tab: string) {
    activeTab.value = tab === 'rateLimits' ? 'rateLimits' : 'quotas';
  }

  function handleTenantFilterChange(value: unknown) {
    sharedFilters.value.tenant_id =
      typeof value === 'number' ? value : undefined;
    applyFilters();
  }

  function openRateLimitTab() {
    activeTab.value = 'rateLimits';
  }

  function openCreate() {
    if (activeTab.value === 'quotas') {
      openQuotaCreate();
      return;
    }
    openRateLimitTab();
    rateLimitFormRef.value?.openNew(buildRateLimitExtraData());
  }

  function openRateLimitEdit(row: AIRateLimitInfo) {
    openRateLimitTab();
    rateLimitFormRef.value?.openEdit(row, buildRateLimitExtraData());
  }

  async function refreshAll() {
    await Promise.all([loadSummary(), loadQuotas(), loadRateLimits()]);
  }

  async function handleQuotaDelete(item: AIQuotaDiagnosticInfo) {
    await deleteQuota(item);
    await loadSummary();
  }

  async function handleRateLimitDelete(item: AIRateLimitDiagnosticInfo) {
    await deleteRateLimit(item);
    await loadSummary();
  }

  async function handleQuotaMutationSuccess() {
    await Promise.all([loadSummary(), loadQuotas()]);
  }

  async function handleRateLimitMutationSuccess() {
    await Promise.all([loadSummary(), loadRateLimits()]);
  }

  onMounted(async () => {
    await Promise.all([loadSummary(), loadSelectOptions()]);
  });

  return {
    activeTab,
    heroChips,
    heroMetrics,
    modelOptions,
    quotaLoading,
    quotaPage,
    quotaPageSize,
    quotaPeriod,
    quotaTotal,
    quotas,
    QuotaFormDrawer,
    rateLimitFormRef,
    rateLimitLoading,
    rateLimitPage,
    rateLimitPageSize,
    rateLimitTotal,
    rateLimits,
    sharedFilters,
    summaryLoading,
    tenantOptions,
    quotaType,
    editQuota,
    handleActiveFilterChange,
    handleModelFilterChange,
    handleQuotaDelete,
    handleQuotaMutationSuccess,
    handleQuotaPeriodChange,
    handleQuotaTypeChange,
    handleRateLimitDelete,
    handleRateLimitMutationSuccess,
    handleTabChange,
    handleTenantFilterChange,
    openCreate,
    openRateLimitEdit,
    onQuotaPageChange,
    onRateLimitPageChange,
    refreshAll,
  };
}
