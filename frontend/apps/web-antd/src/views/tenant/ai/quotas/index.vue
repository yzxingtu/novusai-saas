<script lang="ts" setup>
/**
 * 租户端配额与速率限制管理页面（只读）— useCrudList 声明式卡片布局
 */
import type {
  TenantQuotaWithUsageInfo,
  TenantRateLimitInfo,
} from '#/api/tenant/ai';

import { onUnmounted } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Card,
  Empty,
  Progress,
  Spin,
  TabPane,
  Tabs,
  Tag,
} from 'ant-design-vue';

import { getTenantQuotasApi, getTenantRateLimitsApi } from '#/api/tenant/ai';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';

import { formatTokens, getPeriodText, getQuotaTypeText } from './data';

defineOptions({ name: 'TenantAIQuotas' });

// ========== 配额 Tab — useCrudList（只读，含使用量） ==========
const { list: quotas, loading: quotaLoading } =
  useCrudList<TenantQuotaWithUsageInfo>({
    api: {
      list: getTenantQuotasApi,
      resource: '',
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
    ai: false,
  });

// ========== 速率限制 Tab — useCrudList（只读） ==========
const { list: rateLimits, loading: rateLimitLoading } =
  useCrudList<TenantRateLimitInfo>({
    api: {
      list: getTenantRateLimitsApi,
      resource: '',
    },
    i18nPrefix: 'tenant.ai.rateLimit',
    pager: false,
    responseAdapter: (data) => ({
      items: Array.isArray(data) ? (data as TenantRateLimitInfo[]) : [],
      total: Array.isArray(data) ? (data as unknown[]).length : 0,
    }),
    ai: false,
  });

/** 获取进度条颜色 */
function getProgressColor(item: TenantQuotaWithUsageInfo): string {
  if (item.is_exceeded) return '#ff4d4f';
  if (item.is_warning) return '#faad14';
  return '#52c41a';
}

const cleanupPageContext = registerPageContext('tenant/ai/quotas', () => ({
  page_key: 'tenant.ai.quotas',
  page_title: $t('tenant.ai.quota.name'),
  page_data: {
    resource: '/tenant/ai/quotas',
  },
}));

const cleanupPageOps = registerPageOperations('tenant.ai.quotas', [
  {
    name: 'refresh_quotas',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload quotas and rate limits',
    readonly: true,
    handler: async () => {
      quotas.value = [];
      rateLimits.value = [];
      // Trigger reload by re-fetching
      const [q, r] = await Promise.all([
        getTenantQuotasApi(),
        getTenantRateLimitsApi(),
      ]);
      quotas.value = Array.isArray(q)
        ? (q as TenantQuotaWithUsageInfo[]).map((item) => ({
            ...item,
            id: item.quota?.id,
          }))
        : [];
      rateLimits.value = Array.isArray(r) ? r : [];
      return { success: true, message: 'Quotas refreshed' };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('tenant.ai.quota.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <Card :body-style="{ padding: '0' }">
      <Tabs default-active-key="quotas" class="px-4">
        <!-- ========== 配额 Tab ========== -->
        <TabPane key="quotas" :tab="$t('tenant.ai.quota.title')">
          <!-- 信息栏 -->
          <div class="mb-4">
            <span class="text-sm text-muted-foreground">
              {{ quotas.length }} {{ $t('tenant.ai.quota.title') }}
            </span>
          </div>

          <!-- 配额列表 -->
          <Spin :spinning="quotaLoading">
            <div
              v-if="quotas.length > 0"
              class="grid grid-cols-1 gap-3 pb-4 md:grid-cols-2 xl:grid-cols-3"
            >
              <Card
                v-for="item in quotas"
                :key="item.quota.id"
                class="transition-shadow duration-200 hover:shadow-md"
                :body-style="{ padding: '16px' }"
              >
                <div class="flex items-start justify-between">
                  <!-- 左侧信息 -->
                  <div class="flex-1">
                    <div class="mb-2 flex items-center gap-2">
                      <div
                        class="flex size-9 items-center justify-center rounded-lg bg-primary/10"
                      >
                        <IconifyIcon
                          icon="lucide:gauge"
                          class="size-4.5 text-primary"
                        />
                      </div>
                      <div>
                        <div class="flex items-center gap-2">
                          <span
                            v-if="item.quota.model_name"
                            class="font-medium text-foreground"
                          >
                            {{ item.quota.model_name }}
                          </span>
                          <span
                            v-else-if="item.quota.model_id"
                            class="font-medium text-foreground"
                          >
                            {{ $t('tenant.ai.quota.modelId') }} #{{
                              item.quota.model_id
                            }}
                          </span>
                          <Tag v-else color="blue">
                            {{ $t('tenant.ai.quota.globalQuota') }}
                          </Tag>
                          <Tag
                            :color="
                              item.quota.period === 'daily' ? 'orange' : 'blue'
                            "
                          >
                            {{ getPeriodText(item.quota.period) }}
                          </Tag>
                          <Tag
                            :color="
                              item.quota.quota_type === 'hard' ? 'red' : 'green'
                            "
                          >
                            {{ getQuotaTypeText(item.quota.quota_type) }}
                          </Tag>
                        </div>
                        <div
                          v-if="item.quota.description"
                          class="mt-0.5 text-xs text-muted-foreground"
                        >
                          {{ item.quota.description }}
                        </div>
                      </div>
                    </div>

                    <!-- 进度条 -->
                    <div class="mt-3">
                      <div
                        class="mb-1 flex items-center justify-between text-sm"
                      >
                        <span class="text-muted-foreground">
                          {{ $t('tenant.ai.quota.usage') }}:
                          <span class="font-mono font-medium text-foreground">
                            {{ formatTokens(item.usage) }}
                          </span>
                          / {{ formatTokens(item.limit) }}
                        </span>
                        <span
                          class="font-medium"
                          :class="{
                            'text-destructive': item.is_exceeded,
                            'text-warning':
                              item.is_warning && !item.is_exceeded,
                            'text-success': !item.is_warning,
                          }"
                        >
                          {{ item.usage_percent.toFixed(1) }}%
                        </span>
                      </div>
                      <Progress
                        :percent="Math.min(item.usage_percent, 100)"
                        :show-info="false"
                        :stroke-color="getProgressColor(item)"
                        size="small"
                      />
                      <div
                        class="mt-1 flex items-center gap-3 text-xs text-muted-foreground"
                      >
                        <span>
                          {{ $t('tenant.ai.quota.remaining') }}:
                          {{ formatTokens(item.remaining) }}
                        </span>
                        <Tag
                          v-if="item.is_exceeded"
                          color="error"
                          class="text-xs"
                        >
                          {{ $t('tenant.ai.quota.exceeded') }}
                        </Tag>
                        <Tag
                          v-else-if="item.is_warning"
                          color="warning"
                          class="text-xs"
                        >
                          {{ $t('tenant.ai.quota.warning') }}
                        </Tag>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
            <Empty v-else :description="$t('common.noData')" class="py-16" />
          </Spin>
        </TabPane>

        <!-- ========== 速率限制 Tab ========== -->
        <TabPane key="rateLimits" :tab="$t('tenant.ai.rateLimit.title')">
          <!-- 信息栏 -->
          <div class="mb-4">
            <span class="text-sm text-muted-foreground">
              {{ rateLimits.length }} {{ $t('tenant.ai.rateLimit.title') }}
            </span>
          </div>

          <!-- 速率限制列表 -->
          <Spin :spinning="rateLimitLoading">
            <div
              v-if="rateLimits.length > 0"
              class="grid grid-cols-1 gap-3 pb-4 md:grid-cols-2 xl:grid-cols-3"
            >
              <Card
                v-for="item in rateLimits"
                :key="item.id"
                class="transition-shadow duration-200 hover:shadow-md"
                :body-style="{ padding: '16px' }"
              >
                <div class="flex items-center justify-between">
                  <!-- 左侧信息 -->
                  <div class="flex items-center gap-3">
                    <div
                      class="flex size-9 shrink-0 items-center justify-center rounded-lg"
                      :class="item.is_active ? 'bg-primary/10' : 'bg-muted'"
                    >
                      <IconifyIcon
                        icon="lucide:timer"
                        class="size-4.5"
                        :class="
                          item.is_active
                            ? 'text-primary'
                            : 'text-muted-foreground'
                        "
                      />
                    </div>
                    <div>
                      <div class="flex items-center gap-2">
                        <span class="font-medium text-foreground">
                          {{
                            item.model_name ||
                            `${$t('tenant.ai.rateLimit.modelId')} #${item.model_id}`
                          }}
                        </span>
                        <Tag :color="item.is_active ? 'success' : 'default'">
                          {{
                            item.is_active
                              ? $t('tenant.ai.rateLimit.isActive')
                              : $t('common.disabled')
                          }}
                        </Tag>
                      </div>
                      <div
                        class="mt-1 flex items-center gap-4 text-sm text-muted-foreground"
                      >
                        <span>
                          {{ $t('tenant.ai.rateLimit.rpmLimit') }}:
                          <span class="font-mono font-medium text-foreground">
                            {{
                              item.rpm_limit ??
                              $t('tenant.ai.rateLimit.noLimit')
                            }}
                          </span>
                          <span v-if="item.rpm_limit" class="ml-0.5">{{
                            $t('tenant.ai.rateLimit.rpmUnit')
                          }}</span>
                        </span>
                        <span>
                          {{ $t('tenant.ai.rateLimit.tpmLimit') }}:
                          <span class="font-mono font-medium text-foreground">
                            {{
                              item.tpm_limit
                                ? formatTokens(item.tpm_limit)
                                : $t('tenant.ai.rateLimit.noLimit')
                            }}
                          </span>
                          <span v-if="item.tpm_limit" class="ml-0.5">{{
                            $t('tenant.ai.rateLimit.tpmUnit')
                          }}</span>
                        </span>
                      </div>
                    </div>
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
