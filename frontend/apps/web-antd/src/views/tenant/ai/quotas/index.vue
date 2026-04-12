<script lang="ts" setup>
import type {
  TenantEffectiveRateLimitInfo,
  TenantQuotaWithUsageInfo,
  TenantRateLimitInfo,
} from '#/api/tenant/ai';

import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Card,
  Empty,
  Progress,
  Select,
  Spin,
  TabPane,
  Tabs,
  Tag,
} from 'ant-design-vue';

import {
  getTenantEffectiveRateLimitsApi,
  getTenantQuotasApi,
  getTenantRateLimitsApi,
} from '#/api/tenant/ai';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';

import {
  formatPercent,
  formatTokens,
  getActiveStateOptions,
  getModelSelectOptions,
  getPeriodOptions,
  getPeriodText,
  getQuotaTypeOptions,
  getQuotaTypeText,
  getRuntimeStatusColor,
  getRuntimeStatusText,
  getSourceColor,
  getSourceText,
} from './data';

defineOptions({ name: 'TenantAIQuotas' });

interface SelectOption {
  label: string;
  value: number;
}

interface SharedFilters {
  is_active?: 'false' | 'true';
  model_id?: number;
}

const activeTab = ref<'quotas' | 'rateLimits'>('quotas');
const modelOptions = ref<SelectOption[]>([]);
const sharedFilters = ref<SharedFilters>({});
const quotaPeriod = ref<string>();
const quotaType = ref<string>();
const effectiveRateLimitMap = ref<Record<number, TenantEffectiveRateLimitInfo>>(
  {},
);
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

const heroMetrics = computed(() => {
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

const hasVisibleGlobalQuota = computed(() =>
  displayedQuotas.value.some((item) => item.quota.model_id === null),
);

const quotaAlertGridClass = computed(() =>
  hasVisibleGlobalQuota.value ? 'xl:grid-cols-3' : 'xl:grid-cols-2',
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

const heroChips = computed(() => {
  const chips = [
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

function handleModelFilterChange(value: unknown) {
  sharedFilters.value.model_id = typeof value === 'number' ? value : undefined;
  applyFilters();
}

function handleActiveFilterChange(value: unknown) {
  sharedFilters.value.is_active =
    value === 'true' || value === 'false' ? value : undefined;
  applyFilters();
}

function handleQuotaPeriodChange(value: unknown) {
  quotaPeriod.value = typeof value === 'string' ? value : undefined;
  applyFilters();
}

function handleQuotaTypeChange(value: unknown) {
  quotaType.value = typeof value === 'string' ? value : undefined;
}

function resolveQuotaRuntimeStatus(
  item: TenantQuotaWithUsageInfo,
): 'exceeded' | 'healthy' | 'inactive' | 'warning' {
  if (!item.quota.is_active) return 'inactive';
  if (item.is_exceeded) return 'exceeded';
  if (item.is_warning) return 'warning';
  return 'healthy';
}

function getProgressColor(item: TenantQuotaWithUsageInfo): string {
  if (!item.quota.is_active) return '#d9d9d9';
  if (item.is_exceeded) return '#ff4d4f';
  if (item.is_warning) return '#faad14';
  return '#52c41a';
}
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <Spin :spinning="pageLoading">
      <AIPageHeroCard
        :chips="heroChips"
        :description="$t('tenant.ai.quota.pageDesc')"
        icon="lucide:gauge"
        icon-wrap-class="bg-primary/10 text-primary"
        :metrics="heroMetrics"
        :title="$t('tenant.ai.quota.title')"
      />
    </Spin>

    <Card :body-style="{ padding: '20px' }">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <Select
            allow-clear
            class="w-44"
            :options="modelOptions"
            :placeholder="$t('tenant.ai.quota.placeholder.allModels')"
            :value="sharedFilters.model_id"
            @change="handleModelFilterChange"
          />
          <Select
            allow-clear
            class="w-36"
            :options="getActiveStateOptions()"
            :placeholder="$t('tenant.ai.quota.placeholder.allStatus')"
            :value="sharedFilters.is_active"
            @change="handleActiveFilterChange"
          />
          <template v-if="activeTab === 'quotas'">
            <Select
              allow-clear
              class="w-36"
              :options="getPeriodOptions()"
              :placeholder="$t('tenant.ai.quota.placeholder.allPeriods')"
              :value="quotaPeriod"
              @change="handleQuotaPeriodChange"
            />
            <Select
              allow-clear
              class="w-36"
              :options="getQuotaTypeOptions()"
              :placeholder="$t('tenant.ai.quota.placeholder.allTypes')"
              :value="quotaType"
              @change="handleQuotaTypeChange"
            />
          </template>
        </div>
      </div>

      <Tabs v-model:active-key="activeTab">
        <TabPane key="quotas" :tab="$t('tenant.ai.quota.title')">
          <div class="mb-4 grid grid-cols-1 gap-3" :class="quotaAlertGridClass">
            <Alert
              :message="$t('tenant.ai.quota.helper.hardLimit')"
              show-icon
              type="error"
            />
            <Alert
              :message="$t('tenant.ai.quota.helper.softLimit')"
              show-icon
              type="warning"
            />
            <Alert
              v-if="hasVisibleGlobalQuota"
              :message="$t('tenant.ai.quota.helper.globalFallback')"
              show-icon
              type="info"
            />
          </div>

          <Spin :spinning="quotaLoading">
            <div
              v-if="displayedQuotas.length > 0"
              class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
            >
              <Card
                v-for="item in displayedQuotas"
                :key="item.quota.id"
                class="overflow-hidden border-border/60"
                :body-style="{ padding: '18px' }"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <div
                        class="flex size-10 items-center justify-center rounded-2xl bg-primary/10"
                      >
                        <IconifyIcon
                          icon="lucide:shield"
                          class="size-5 text-primary"
                        />
                      </div>
                      <div class="min-w-0">
                        <div
                          class="truncate text-base font-semibold text-foreground"
                        >
                          {{
                            item.quota.model_name ||
                            (item.quota.model_id
                              ? `${$t('tenant.ai.quota.modelId')} #${item.quota.model_id}`
                              : $t('tenant.ai.quota.globalQuota'))
                          }}
                        </div>
                        <div class="mt-1 flex flex-wrap items-center gap-1.5">
                          <Tag color="blue" class="!mr-0">
                            {{
                              item.quota.model_id
                                ? $t('tenant.ai.quota.scope.model')
                                : $t('tenant.ai.quota.scope.global')
                            }}
                          </Tag>
                          <Tag
                            :color="
                              getRuntimeStatusColor(
                                resolveQuotaRuntimeStatus(item),
                              )
                            "
                            class="!mr-0"
                          >
                            {{
                              getRuntimeStatusText(
                                resolveQuotaRuntimeStatus(item),
                              )
                            }}
                          </Tag>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="mt-4 flex flex-wrap items-center gap-2">
                  <Tag
                    :color="
                      item.quota.period === 'daily' ? 'orange' : 'geekblue'
                    "
                    class="!mr-0"
                  >
                    {{ getPeriodText(item.quota.period) }}
                  </Tag>
                  <Tag
                    :color="item.quota.quota_type === 'hard' ? 'red' : 'green'"
                    class="!mr-0"
                  >
                    {{ getQuotaTypeText(item.quota.quota_type) }}
                  </Tag>
                  <Tag
                    :color="item.quota.is_active ? 'success' : 'default'"
                    class="!mr-0"
                  >
                    {{
                      item.quota.is_active
                        ? $t('common.enabled')
                        : $t('common.disabled')
                    }}
                  </Tag>
                </div>

                <div class="mt-4 rounded-2xl bg-accent/10 p-4">
                  <div class="mb-2 flex items-center justify-between text-sm">
                    <span class="text-muted-foreground">
                      {{ $t('tenant.ai.quota.usage') }}
                    </span>
                    <span class="font-medium">
                      {{ formatTokens(item.usage) }} /
                      {{ formatTokens(item.limit) }}
                    </span>
                  </div>
                  <Progress
                    :percent="Math.min(item.usage_percent, 100)"
                    :show-info="false"
                    :stroke-color="getProgressColor(item)"
                  />
                  <div
                    class="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm"
                  >
                    <span class="text-muted-foreground">
                      {{ $t('tenant.ai.quota.remaining') }}:
                      <span class="font-medium text-foreground">
                        {{ formatTokens(item.remaining) }}
                      </span>
                    </span>
                    <span class="text-muted-foreground">
                      {{ formatPercent(item.usage_percent) }}
                    </span>
                  </div>
                  <div
                    class="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
                  >
                    <span>
                      {{ $t('tenant.ai.quota.warningThreshold') }}:
                      {{ item.quota.warning_threshold ?? 80 }}%
                    </span>
                    <span v-if="item.is_warning">
                      {{ $t('tenant.ai.quota.warning') }}
                    </span>
                    <span v-if="item.is_exceeded">
                      {{ $t('tenant.ai.quota.exceeded') }}
                    </span>
                  </div>
                </div>

                <div class="mt-4 space-y-2 text-sm">
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-muted-foreground">{{
                      $t('tenant.ai.quota.response')
                    }}</span>
                    <span class="font-medium text-foreground">
                      {{
                        item.quota.quota_type === 'hard'
                          ? 'HTTP 429'
                          : $t('tenant.ai.quota.type_options.soft')
                      }}
                    </span>
                  </div>
                  <div class="text-xs text-muted-foreground">
                    {{
                      item.quota.quota_type === 'hard'
                        ? $t('tenant.ai.quota.helper.hardLimit')
                        : $t('tenant.ai.quota.helper.softLimit')
                    }}
                  </div>
                  <div
                    v-if="item.quota.description"
                    class="text-xs text-muted-foreground"
                  >
                    {{ item.quota.description }}
                  </div>
                </div>
              </Card>
            </div>
            <Empty v-else :description="$t('common.noData')" class="py-16" />
          </Spin>
        </TabPane>

        <TabPane key="rateLimits" :tab="$t('tenant.ai.rateLimit.title')">
          <div class="mb-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
            <Alert
              :message="$t('tenant.ai.rateLimit.helper.inherit')"
              show-icon
              type="info"
            />
            <Alert
              :message="$t('tenant.ai.rateLimit.helper.disable')"
              show-icon
              type="warning"
            />
          </div>

          <Spin :spinning="rateLimitLoading || effectiveRateLimitLoading">
            <div
              v-if="rateLimits.length > 0"
              class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
            >
              <Card
                v-for="item in rateLimits"
                :key="item.id"
                class="overflow-hidden border-border/60"
                :body-style="{ padding: '18px' }"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <div
                        class="flex size-10 items-center justify-center rounded-2xl bg-success/10"
                      >
                        <IconifyIcon
                          icon="lucide:timer"
                          class="size-5 text-success"
                        />
                      </div>
                      <div class="min-w-0">
                        <div
                          class="truncate text-base font-semibold text-foreground"
                        >
                          {{
                            item.model_name ||
                            `${$t('tenant.ai.rateLimit.modelId')} #${item.model_id}`
                          }}
                        </div>
                        <div class="mt-1 flex flex-wrap items-center gap-1.5">
                          <Tag
                            :color="item.is_active ? 'success' : 'default'"
                            class="!mr-0"
                          >
                            {{
                              item.is_active
                                ? $t('common.enabled')
                                : $t('common.disabled')
                            }}
                          </Tag>
                          <template v-if="effectiveRateLimitMap[item.id]">
                            <Tag
                              :color="
                                getSourceColor(
                                  effectiveRateLimitMap[item.id]?.rpm_source,
                                )
                              "
                              class="!mr-0"
                            >
                              RPM
                              {{
                                getSourceText(
                                  effectiveRateLimitMap[item.id]?.rpm_source,
                                )
                              }}
                            </Tag>
                            <Tag
                              :color="
                                getSourceColor(
                                  effectiveRateLimitMap[item.id]?.tpm_source,
                                )
                              "
                              class="!mr-0"
                            >
                              TPM
                              {{
                                getSourceText(
                                  effectiveRateLimitMap[item.id]?.tpm_source,
                                )
                              }}
                            </Tag>
                          </template>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="mt-4 grid grid-cols-1 gap-3">
                  <div class="rounded-2xl bg-accent/10 p-4">
                    <div class="mb-2 flex items-center justify-between text-sm">
                      <span class="text-muted-foreground">
                        {{ $t('tenant.ai.rateLimit.configured') }}
                      </span>
                      <span class="font-medium">
                        RPM
                        {{
                          item.rpm_limit ?? $t('tenant.ai.rateLimit.noLimit')
                        }}
                        / TPM
                        {{
                          item.tpm_limit == null
                            ? $t('tenant.ai.rateLimit.noLimit')
                            : formatTokens(item.tpm_limit)
                        }}
                      </span>
                    </div>
                    <div class="text-xs text-muted-foreground">
                      {{
                        item.description ||
                        $t('tenant.ai.rateLimit.inheritance')
                      }}
                    </div>
                  </div>

                  <div
                    v-if="effectiveRateLimitMap[item.id]"
                    class="rounded-2xl bg-accent/10 p-4"
                  >
                    <div class="mb-2 flex items-center justify-between text-sm">
                      <span class="text-muted-foreground">
                        {{ $t('tenant.ai.rateLimit.effective') }}
                      </span>
                      <span class="font-medium">
                        RPM
                        {{
                          effectiveRateLimitMap[item.id]?.rpm_limit ??
                          $t('tenant.ai.rateLimit.noLimit')
                        }}
                        / TPM
                        {{
                          effectiveRateLimitMap[item.id]?.tpm_limit == null
                            ? $t('tenant.ai.rateLimit.noLimit')
                            : formatTokens(
                                effectiveRateLimitMap[item.id]?.tpm_limit ?? 0,
                              )
                        }}
                      </span>
                    </div>
                    <div class="text-xs text-muted-foreground">
                      {{ $t('tenant.ai.rateLimit.inheritance') }}
                    </div>
                  </div>
                </div>

                <div class="mt-4 grid grid-cols-1 gap-2 text-sm">
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-muted-foreground">{{
                      $t('tenant.ai.rateLimit.modelDefault')
                    }}</span>
                    <span class="font-medium text-foreground">
                      RPM
                      {{
                        effectiveRateLimitMap[item.id]
                          ?.model_default_rpm_limit ??
                        $t('tenant.ai.rateLimit.noLimit')
                      }}
                      / TPM
                      {{
                        effectiveRateLimitMap[item.id]
                          ?.model_default_tpm_limit == null
                          ? $t('tenant.ai.rateLimit.noLimit')
                          : formatTokens(
                              effectiveRateLimitMap[item.id]
                                ?.model_default_tpm_limit ?? 0,
                            )
                      }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-muted-foreground">{{
                      $t('tenant.ai.rateLimit.sourceLabel')
                    }}</span>
                    <span
                      class="flex flex-wrap items-center justify-end gap-1.5"
                    >
                      <Tag
                        :color="
                          getSourceColor(
                            effectiveRateLimitMap[item.id]?.rpm_source,
                          )
                        "
                        class="!mr-0"
                      >
                        RPM
                        {{
                          getSourceText(
                            effectiveRateLimitMap[item.id]?.rpm_source,
                          )
                        }}
                      </Tag>
                      <Tag
                        :color="
                          getSourceColor(
                            effectiveRateLimitMap[item.id]?.tpm_source,
                          )
                        "
                        class="!mr-0"
                      >
                        TPM
                        {{
                          getSourceText(
                            effectiveRateLimitMap[item.id]?.tpm_source,
                          )
                        }}
                      </Tag>
                    </span>
                  </div>
                </div>
              </Card>
            </div>
            <Empty v-else :description="$t('common.noData')" class="py-16" />
          </Spin>
        </TabPane>
      </Tabs>
    </Card>
  </Page>
</template>
