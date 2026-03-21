<script lang="ts" setup>
import type { Dayjs } from 'dayjs';

import type {
  CallTrendItem,
  LatencyDistributionItem,
  ModelDistributionItem,
  ProviderPerformanceItem,
  SuccessRateTrendItem,
  TenantRankingItem,
} from '#/api/admin/analytics';

/**
 * Admin Analytics 数据分析页面（T17）
 *
 * 集成所有 ECharts 图表 + 日期范围筛选
 */
import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { Card, DatePicker, Spin } from 'ant-design-vue';

import {
  getCallTrendApi,
  getLatencyDistributionApi,
  getModelDistributionApi,
  getProviderPerformanceApi,
  getSuccessRateTrendApi,
  getTenantRankingApi,
} from '#/api/admin/analytics';
import { $t } from '#/locales';
import AiCallTrendChart from '#/views/_shared/charts/AiCallTrendChart.vue';
import ModelDistributionChart from '#/views/_shared/charts/ModelDistributionChart.vue';
import TokenTrendChart from '#/views/_shared/charts/TokenTrendChart.vue';

import LatencyHistogramChart from './charts/LatencyHistogramChart.vue';
import ProviderRadarChart from './charts/ProviderRadarChart.vue';
import SuccessRateChart from './charts/SuccessRateChart.vue';
import TenantRankingChart from './charts/TenantRankingChart.vue';

defineOptions({ name: 'AdminAnalytics' });

const loading = ref(false);
const dateRange = ref<[Dayjs, Dayjs] | undefined>();

const callTrend = ref<CallTrendItem[]>([]);
const modelDist = ref<ModelDistributionItem[]>([]);
const providerPerf = ref<ProviderPerformanceItem[]>([]);
const tenantRanking = ref<TenantRankingItem[]>([]);
const latencyDist = ref<LatencyDistributionItem[]>([]);
const successRate = ref<SuccessRateTrendItem[]>([]);

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
    const [ct, md, pp, tr, ld, sr] = await Promise.allSettled([
      getCallTrendApi(params),
      getModelDistributionApi(params),
      getProviderPerformanceApi(params),
      getTenantRankingApi(10, params),
      getLatencyDistributionApi(params),
      getSuccessRateTrendApi(params),
    ]);
    if (ct.status === 'fulfilled') callTrend.value = ct.value;
    if (md.status === 'fulfilled') modelDist.value = md.value;
    if (pp.status === 'fulfilled') providerPerf.value = pp.value;
    if (tr.status === 'fulfilled') tenantRanking.value = tr.value;
    if (ld.status === 'fulfilled') latencyDist.value = ld.value;
    if (sr.status === 'fulfilled') successRate.value = sr.value;
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
</script>

<template>
  <Page :title="$t('admin.analytics.title')">
    <template #extra>
      <DatePicker.RangePicker
        v-model:value="dateRange"
        :placeholder="[
          $t('admin.analytics.startDate'),
          $t('admin.analytics.endDate'),
        ]"
        @change="handleDateChange"
        allow-clear
      />
    </template>

    <Spin :spinning="loading">
      <!-- Row 1: Call Trend + Token Trend -->
      <div class="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card :title="$t('admin.analytics.callTrend')">
          <AiCallTrendChart :data="callTrend" />
        </Card>
        <Card :title="$t('admin.analytics.tokenTrend')">
          <TokenTrendChart :data="callTrend" />
        </Card>
      </div>

      <!-- Row 2: Model Distribution + Provider Radar -->
      <div class="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card :title="$t('admin.analytics.modelDistribution')">
          <ModelDistributionChart :data="modelDist" />
        </Card>
        <Card :title="$t('admin.analytics.providerPerformance')">
          <ProviderRadarChart :data="providerPerf" />
        </Card>
      </div>

      <!-- Row 3: Tenant Ranking + Success Rate -->
      <div class="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card :title="$t('admin.analytics.tenantRanking')">
          <TenantRankingChart :data="tenantRanking" />
        </Card>
        <Card :title="$t('admin.analytics.successRate')">
          <SuccessRateChart :data="successRate" />
        </Card>
      </div>

      <!-- Row 4: Latency Distribution (full width) -->
      <Card :title="$t('admin.analytics.latencyDistribution')">
        <LatencyHistogramChart :data="latencyDist" />
      </Card>
    </Spin>
  </Page>
</template>
