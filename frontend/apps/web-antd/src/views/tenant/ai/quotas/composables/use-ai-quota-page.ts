import type {
  TenantEffectiveRateLimitInfo,
  TenantQuotaWithUsageInfo,
  TenantRateLimitInfo,
} from '#/api/tenant/ai';

import { computed, onMounted, ref, watch } from 'vue';

import {
  getTenantEffectiveRateLimitsApi,
  getTenantQuotasApi,
  getTenantRateLimitsApi,
} from '#/api/tenant/ai';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';

import {
  getActiveStateOptions,
  getModelSelectOptions,
  resolveQuotaRuntimeStatus,
} from '../data';

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

export interface SelectOption {
  label: string;
  value: number;
}

export interface SharedFilters {
  is_active?: 'false' | 'true';
  model_id?: number;
}

export function useAIQuotaPage() {
  const activeTab = ref<QuotaPageTab>('quotas');
  const modelOptions = ref<SelectOption[]>([]);
  const sharedFilters = ref<SharedFilters>({});
  const quotaPeriod = ref<string>();
  const quotaType = ref<string>();
  const effectiveRateLimitMap = ref<
    Record<number, TenantEffectiveRateLimitInfo>
  >({});
  const effectiveRateLimitLoading = ref(false);

  const {
    list: quotas,
    loading: quotaLoading,
    onSearch: searchQuotas,
  } = useCrudList<TenantQuotaWithUsageInfo>({
    api: {
      list: getTenantQuotasApi,
      resource: '/tenant/ai/quotas',
    },
    i18nPrefix: 'tenant.ai.quota',
    pager: false,
    responseAdapter: (data) => ({
      items: Array.isArray(data)
        ? (data as TenantQuotaWithUsageInfo[]).map((item) => ({
            ...item,
            id: item.quota?.id,
          }))
        : [],
      total: Array.isArray(data) ? (data as unknown[]).length : 0,
    }),
  });

  const {
    list: rateLimits,
    loading: rateLimitLoading,
    onSearch: searchRateLimits,
  } = useCrudList<TenantRateLimitInfo>({
    api: {
      list: getTenantRateLimitsApi,
      resource: '/tenant/ai/quotas/rate-limits',
    },
    i18nPrefix: 'tenant.ai.rateLimit',
    pager: false,
    responseAdapter: (data) => ({
      items: Array.isArray(data) ? (data as TenantRateLimitInfo[]) : [],
      total: Array.isArray(data) ? (data as unknown[]).length : 0,
    }),
  });

  const displayedQuotas = computed(() =>
    quotas.value.filter((item) => {
      if (quotaType.value && item.quota.quota_type !== quotaType.value) {
        return false;
      }
      return true;
    }),
  );

  const selectedModelLabel = computed(() => {
    return modelOptions.value.find(
      (option) => option.value === sharedFilters.value.model_id,
    )?.label;
  });

  const selectedStatusLabel = computed(() => {
    return getActiveStateOptions().find(
      (option) => option.value === sharedFilters.value.is_active,
    )?.label;
  });

  const activeTabTitle = computed(() =>
    activeTab.value === 'quotas'
      ? $t('tenant.ai.quota.title')
      : $t('tenant.ai.rateLimit.title'),
  );

  const heroMetrics = computed<HeroMetric[]>(() => {
    const riskCount = displayedQuotas.value.filter((item) => {
      const status = resolveQuotaRuntimeStatus(item);
      return status === 'warning' || status === 'exceeded';
    }).length;

    return [
      {
        key: 'quotaRules',
        label: $t('tenant.ai.quota.summary.totalRules'),
        value: displayedQuotas.value.length,
      },
      {
        key: 'activeQuotaRules',
        label: $t('tenant.ai.quota.summary.activeRules'),
        value: displayedQuotas.value.filter((item) => item.quota.is_active)
          .length,
      },
      {
        key: 'quotaRiskRules',
        label: $t('tenant.ai.quota.summary.riskRules'),
        value: riskCount,
      },
      {
        key: 'rateLimitRules',
        label: $t('tenant.ai.quota.summary.rateLimitRules'),
        value: rateLimits.value.length,
      },
    ];
  });

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
        text:
          activeTab.value === 'quotas'
            ? `${$t('tenant.ai.quota.usage')} / ${$t('tenant.ai.quota.remaining')} / ${$t('tenant.ai.quota.response')}`
            : `${$t('tenant.ai.rateLimit.effective')} / ${$t('tenant.ai.rateLimit.modelDefault')} / ${$t('tenant.ai.rateLimit.inheritance')}`,
      },
    ];

    const filterLabel = [selectedModelLabel.value, selectedStatusLabel.value]
      .filter(Boolean)
      .join(' / ');
    if (filterLabel) {
      chips.push({
        key: 'filters',
        icon: 'lucide:filter',
        className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
        text: filterLabel,
      });
    }

    return chips;
  });

  const pageLoading = computed(
    () =>
      quotaLoading.value ||
      rateLimitLoading.value ||
      effectiveRateLimitLoading.value,
  );

  watch(
    rateLimits,
    async () => {
      await loadEffectiveRateLimitMap();
    },
    { immediate: true },
  );

  onMounted(async () => {
    await loadModelOptions();
  });

  async function loadModelOptions() {
    try {
      modelOptions.value = await getModelSelectOptions();
    } catch {
      modelOptions.value = [];
    }
  }

  async function loadEffectiveRateLimitMap() {
    const uniqueModelIds = [
      ...new Set(rateLimits.value.map((item) => item.model_id)),
    ];
    if (uniqueModelIds.length === 0) {
      effectiveRateLimitMap.value = {};
      return;
    }

    effectiveRateLimitLoading.value = true;
    try {
      const entries = await Promise.all(
        uniqueModelIds.map(async (modelId) => {
          try {
            return [
              modelId,
              await getTenantEffectiveRateLimitsApi(modelId),
            ] as const;
          } catch {
            return [modelId, undefined] as const;
          }
        }),
      );

      const byModel = new Map<number, TenantEffectiveRateLimitInfo>();
      for (const [modelId, info] of entries) {
        if (info) byModel.set(modelId, info);
      }

      const nextMap: Record<number, TenantEffectiveRateLimitInfo> = {};
      for (const item of rateLimits.value) {
        const info = byModel.get(item.model_id);
        if (info) nextMap[item.id] = info;
      }
      effectiveRateLimitMap.value = nextMap;
    } finally {
      effectiveRateLimitLoading.value = false;
    }
  }

  function buildSharedSearchParams() {
    return {
      ...(sharedFilters.value.model_id
        ? { model_id: sharedFilters.value.model_id }
        : {}),
      ...(sharedFilters.value.is_active === undefined
        ? {}
        : { is_active: sharedFilters.value.is_active }),
    };
  }

  function applyFilters() {
    searchQuotas({
      ...buildSharedSearchParams(),
      ...(quotaPeriod.value ? { period: quotaPeriod.value } : {}),
    });
    searchRateLimits(buildSharedSearchParams());
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
  }

  function handleTabChange(tab: string) {
    activeTab.value = tab === 'rateLimits' ? 'rateLimits' : 'quotas';
  }

  return {
    activeTab,
    displayedQuotas,
    effectiveRateLimitLoading,
    effectiveRateLimitMap,
    heroChips,
    heroMetrics,
    modelOptions,
    pageLoading,
    quotaLoading,
    quotaPeriod,
    quotaType,
    rateLimitLoading,
    rateLimits,
    sharedFilters,
    handleActiveFilterChange,
    handleModelFilterChange,
    handleQuotaPeriodChange,
    handleQuotaTypeChange,
    handleTabChange,
  };
}
