<script lang="ts" setup>
import type { QuotaPageTab } from '../composables/use-ai-quota-page';

import type {
  TenantEffectiveRateLimitInfo,
  TenantQuotaWithUsageInfo,
  TenantRateLimitInfo,
} from '#/api/tenant/ai';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Card,
  Empty,
  Progress,
  Spin,
  TabPane,
  Tabs,
  Tag,
} from 'ant-design-vue';

import {
  formatPercent,
  formatTokens,
  getPeriodText,
  getQuotaProgressColor,
  getQuotaTypeText,
  getRuntimeStatusColor,
  getRuntimeStatusText,
  getSourceColor,
  getSourceText,
  resolveQuotaRuntimeStatus,
} from '../data';

defineOptions({ name: 'TenantAIQuotaPageContent' });

const props = defineProps<{
  activeTab: QuotaPageTab;
  displayedQuotas: TenantQuotaWithUsageInfo[];
  effectiveRateLimitLoading: boolean;
  effectiveRateLimitMap: Record<number, TenantEffectiveRateLimitInfo>;
  onTabChange: (tab: string) => void;
  quotaLoading: boolean;
  rateLimitLoading: boolean;
  rateLimits: TenantRateLimitInfo[];
}>();

function handleTabChange(tab: number | string) {
  props.onTabChange(String(tab));
}

const hasVisibleGlobalQuota = computed(() =>
  props.displayedQuotas.some((item) => item.quota.model_id === null),
);

const quotaAlertGridClass = computed(() =>
  hasVisibleGlobalQuota.value ? 'xl:grid-cols-3' : 'xl:grid-cols-2',
);

const rateLimitSpinning = computed(
  () => props.rateLimitLoading || props.effectiveRateLimitLoading,
);
</script>

<template>
  <Tabs :active-key="activeTab" @change="handleTabChange">
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
                          getRuntimeStatusColor(resolveQuotaRuntimeStatus(item))
                        "
                        class="!mr-0"
                      >
                        {{
                          getRuntimeStatusText(resolveQuotaRuntimeStatus(item))
                        }}
                      </Tag>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-4 flex flex-wrap items-center gap-2">
              <Tag
                :color="item.quota.period === 'daily' ? 'orange' : 'geekblue'"
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
                :stroke-color="getQuotaProgressColor(item)"
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
                <span class="text-muted-foreground">
                  {{ $t('tenant.ai.quota.response') }}
                </span>
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

      <Spin :spinning="rateLimitSpinning">
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
                    {{ item.rpm_limit ?? $t('tenant.ai.rateLimit.noLimit') }}
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
                    item.description || $t('tenant.ai.rateLimit.inheritance')
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
                <span class="text-muted-foreground">
                  {{ $t('tenant.ai.rateLimit.modelDefault') }}
                </span>
                <span class="font-medium text-foreground">
                  RPM
                  {{
                    effectiveRateLimitMap[item.id]?.model_default_rpm_limit ??
                    $t('tenant.ai.rateLimit.noLimit')
                  }}
                  / TPM
                  {{
                    effectiveRateLimitMap[item.id]?.model_default_tpm_limit ==
                    null
                      ? $t('tenant.ai.rateLimit.noLimit')
                      : formatTokens(
                          effectiveRateLimitMap[item.id]
                            ?.model_default_tpm_limit ?? 0,
                        )
                  }}
                </span>
              </div>
              <div class="flex items-center justify-between gap-3">
                <span class="text-muted-foreground">
                  {{ $t('tenant.ai.rateLimit.sourceLabel') }}
                </span>
                <span class="flex flex-wrap items-center justify-end gap-1.5">
                  <Tag
                    :color="
                      getSourceColor(effectiveRateLimitMap[item.id]?.rpm_source)
                    "
                    class="!mr-0"
                  >
                    RPM
                    {{
                      getSourceText(effectiveRateLimitMap[item.id]?.rpm_source)
                    }}
                  </Tag>
                  <Tag
                    :color="
                      getSourceColor(effectiveRateLimitMap[item.id]?.tpm_source)
                    "
                    class="!mr-0"
                  >
                    TPM
                    {{
                      getSourceText(effectiveRateLimitMap[item.id]?.tpm_source)
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
</template>
