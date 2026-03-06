<script lang="ts" setup>
import type { Dayjs } from 'dayjs';

import type {
  AgentRankingItem,
  CallTrendItem,
  CostTrendItem,
  ModelDistributionItem,
} from '#/api/tenant/analytics';

/**
 * Tenant Analytics 数据分析页面（T13）
 *
 * 集成 ECharts 图表 + 日期范围筛选
 * T9/T10 复用 Admin 端的 AiCallTrendChart / ModelDistributionChart
 */
import { onMounted, onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';

import { Card, DatePicker, Spin } from 'ant-design-vue';

import {
  getTenantAgentRankingApi,
  getTenantCallTrendApi,
  getTenantCostTrendApi,
  getTenantModelDistributionApi,
} from '#/api/tenant/analytics';
import { $t } from '#/locales';
import AiCallTrendChart from '#/views/_shared/charts/AiCallTrendChart.vue';
import ModelDistributionChart from '#/views/_shared/charts/ModelDistributionChart.vue';
import TokenTrendChart from '#/views/_shared/charts/TokenTrendChart.vue';

import AgentRankingChart from './charts/AgentRankingChart.vue';
import CostTrendChart from './charts/CostTrendChart.vue';

defineOptions({ name: 'TenantAnalytics' });

const loading = ref(false);
const dateRange = ref<[Dayjs, Dayjs] | undefined>();

const callTrend = ref<CallTrendItem[]>([]);
const modelDist = ref<ModelDistributionItem[]>([]);
const agentRanking = ref<AgentRankingItem[]>([]);
const costTrend = ref<CostTrendItem[]>([]);

function getParams() {
  if (!dateRange.value) return {};
  return {
    start_date: dateRange.value[0].format('YYYY-MM-DD'),
    end_date: dateRange.value[1].format('YYYY-MM-DD'),
  };
}

async function loadAll() {
  loading.value = true;
  const params = getParams();
  try {
    const [ct, md, ar, cst] = await Promise.allSettled([
      getTenantCallTrendApi(params),
      getTenantModelDistributionApi(params),
      getTenantAgentRankingApi(10, params),
      getTenantCostTrendApi(params),
    ]);
    if (ct.status === 'fulfilled') callTrend.value = ct.value;
    if (md.status === 'fulfilled') modelDist.value = md.value;
    if (ar.status === 'fulfilled') agentRanking.value = ar.value;
    if (cst.status === 'fulfilled') costTrend.value = cst.value;
  } finally {
    loading.value = false;
  }
}

function handleDateChange() {
  loadAll();
}

onMounted(() => {
  loadAll();
});

const cleanupPageContext = registerPageContext('tenant/analytics', () => ({
  page_key: 'tenant.analytics',
  page_title: $t('tenant.analytics.title'),
  page_data: {
    resource: '/tenant/analytics',
  },
}));

const cleanupPageOps = registerPageOperations('tenant.analytics', [
  {
    name: 'refresh_analytics',
    label: $t('shared.pageOperation.refreshAnalytics'),
    description: 'Reload all analytics charts and data',
    readonly: true,
    handler: async () => {
      await loadAll();
      return { success: true, message: 'Analytics data refreshed' };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page :title="$t('tenant.analytics.title')">
    <template #extra>
      <DatePicker.RangePicker
        v-model:value="dateRange"
        :placeholder="[
          $t('tenant.analytics.startDate'),
          $t('tenant.analytics.endDate'),
        ]"
        @change="handleDateChange"
        allow-clear
      />
    </template>

    <Spin :spinning="loading">
      <!-- Row 1: Call Trend + Token Trend -->
      <div class="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card :title="$t('tenant.analytics.callTrend')">
          <AiCallTrendChart :data="callTrend" i18n-prefix="tenant.analytics" />
        </Card>
        <Card :title="$t('tenant.analytics.tokenTrend')">
          <TokenTrendChart :data="callTrend" i18n-prefix="tenant.analytics" />
        </Card>
      </div>

      <!-- Row 2: Model Distribution + Agent Ranking -->
      <div class="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card :title="$t('tenant.analytics.modelDistribution')">
          <ModelDistributionChart :data="modelDist" />
        </Card>
        <Card :title="$t('tenant.analytics.agentRanking')">
          <AgentRankingChart :data="agentRanking" />
        </Card>
      </div>

      <!-- Row 3: Cost Trend (full width) -->
      <Card :title="$t('tenant.analytics.costTrend')">
        <CostTrendChart :data="costTrend" />
      </Card>
    </Spin>
  </Page>
</template>
