<script lang="ts" setup>
/**
 * 平台管理端 AI 使用量统计页面
 */
import { computed, onMounted, ref, watch } from 'vue';

import type { EchartsUIType } from '@vben/plugins/echarts';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Progress, Spin, Tag, Tooltip } from 'ant-design-vue';
import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAICallLogStatisticsApi, getAIUsageStatsApi } from '#/api/admin/ai';
import { type CallTrendItem, getCallTrendApi } from '#/api/admin/analytics';
import { $t } from '#/locales';

import { formatCost, formatLatency, formatTokens, getRequestTypeColor, useColumns, useGridFormSchema } from './data';

defineOptions({ name: 'AdminAIUsage' });

// ============================================================
// Summary statistics
// ============================================================

interface SummaryData {
  total_calls: number;
  total_tokens: number;
  total_cost: number;
  success_calls: number;
}

const summaryLoading = ref(false);
const summaryData = ref<SummaryData>({
  total_calls: 0,
  total_tokens: 0,
  total_cost: 0,
  success_calls: 0,
});

const successRate = computed(() => {
  const { total_calls, success_calls } = summaryData.value;
  if (total_calls === 0) return '0%';
  return `${((success_calls / total_calls) * 100).toFixed(1)}%`;
});

const summaryCards = computed(() => [
  {
    key: 'totalCalls',
    label: $t('admin.ai.usage.summary.totalCalls'),
    value: summaryData.value.total_calls,
    icon: 'lucide:phone-call',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'totalTokens',
    label: $t('admin.ai.usage.summary.totalTokens'),
    value: formatTokens(summaryData.value.total_tokens),
    icon: 'lucide:hash',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'totalCost',
    label: $t('admin.ai.usage.summary.totalCost'),
    value: formatCost(summaryData.value.total_cost),
    icon: 'lucide:dollar-sign',
    bgClass: 'bg-warning/10',
    iconClass: 'text-warning',
  },
  {
    key: 'successRate',
    label: $t('admin.ai.usage.summary.successRate'),
    value: successRate.value,
    icon: 'lucide:check-circle',
    bgClass: 'bg-success/10',
    iconClass: 'text-success',
  },
]);

async function loadSummary() {
  summaryLoading.value = true;
  try {
    const res = await getAICallLogStatisticsApi();
    summaryData.value = {
      total_calls: (res.total_calls as number) || 0,
      total_tokens: (res.total_tokens as number) || 0,
      total_cost: (res.total_cost as number) || 0,
      success_calls: (res.success_calls as number) || 0,
    };
  } catch {
    // Error handled by request interceptor
  } finally {
    summaryLoading.value = false;
  }
}

onMounted(loadSummary);

// ============================================================
// ECharts trend charts
// ============================================================

const callChartRef = ref<EchartsUIType>();
const tokenChartRef = ref<EchartsUIType>();
const { renderEcharts: renderCallChart } = useEcharts(callChartRef);
const { renderEcharts: renderTokenChart } = useEcharts(tokenChartRef);

const trendData = ref<CallTrendItem[]>([]);
const trendLoading = ref(false);

async function loadTrend() {
  trendLoading.value = true;
  try {
    trendData.value = await getCallTrendApi();
  } catch {
    // Error handled by request interceptor
  } finally {
    trendLoading.value = false;
  }
}

function renderCharts() {
  const data = trendData.value;
  if (!data.length) return;
  const dates = data.map((i) => i.date.slice(5));

  renderCallChart({
    tooltip: { trigger: 'axis' },
    legend: { data: [$t('admin.analytics.chart.calls'), $t('admin.analytics.chart.success'), $t('admin.analytics.chart.failed')], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      { name: $t('admin.analytics.chart.calls'), type: 'line', data: data.map((i) => i.calls), smooth: true, itemStyle: { color: '#5B8FF9' } },
      { name: $t('admin.analytics.chart.success'), type: 'line', data: data.map((i) => i.success), smooth: true, itemStyle: { color: '#5AD8A6' } },
      { name: $t('admin.analytics.chart.failed'), type: 'line', data: data.map((i) => i.failed), smooth: true, itemStyle: { color: '#F6614E' } },
    ],
  });

  renderTokenChart({
    tooltip: { trigger: 'axis' },
    legend: { data: [$t('admin.analytics.chart.inputTokens'), $t('admin.analytics.chart.outputTokens')], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      { name: $t('admin.analytics.chart.inputTokens'), type: 'line', areaStyle: { opacity: 0.3 }, data: data.map((i) => i.input_tokens), smooth: true, itemStyle: { color: '#5B8FF9' }, stack: 'tokens' },
      { name: $t('admin.analytics.chart.outputTokens'), type: 'line', areaStyle: { opacity: 0.3 }, data: data.map((i) => i.output_tokens), smooth: true, itemStyle: { color: '#5AD8A6' }, stack: 'tokens' },
    ],
  });
}

watch(trendData, renderCharts);
onMounted(loadTrend);

// ============================================================
// Grid
// ============================================================

const { Grid } = useCrudPage({
  api: {
    list: getAIUsageStatsApi,
    resource: '/admin/ai/usage/stats',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.ai.usage',
  defaultSort: '-stat_date',
  toolbar: {
    search: true,
    refresh: true,
    export: true,
    zoom: true,
  },
});
</script>

<template>
  <Page auto-content-height :description="$t('admin.ai.usage.pageDesc')" content-class="flex flex-col gap-4">
    <!-- Summary statistics cards -->
    <Spin :spinning="summaryLoading">
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card
          v-for="stat in summaryCards"
          :key="stat.key"
          :body-style="{ padding: '16px' }"
        >
          <div class="flex items-center gap-3">
            <div
              class="flex size-10 items-center justify-center rounded-lg"
              :class="stat.bgClass"
            >
              <IconifyIcon
                :icon="stat.icon"
                class="size-5"
                :class="stat.iconClass"
              />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">{{ stat.label }}</div>
              <div class="text-lg font-semibold text-foreground">
                {{ stat.value }}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </Spin>

    <!-- Trend charts -->
    <Spin :spinning="trendLoading">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card :title="$t('admin.analytics.callTrend')" :body-style="{ padding: '12px' }">
          <EchartsUI ref="callChartRef" height="240px" />
        </Card>
        <Card :title="$t('admin.analytics.tokenTrend')" :body-style="{ padding: '12px' }">
          <EchartsUI ref="tokenChartRef" height="240px" />
        </Card>
      </div>
    </Spin>

    <!-- Data table -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 统计日期 -->
        <template #statDate_cell="{ row }">
          <span class="font-mono text-sm text-foreground">
            {{ row.stat_date }}
          </span>
        </template>

        <!-- 租户 -->
        <template #tenantName_cell="{ row }">
          <span v-if="row.tenant_name" class="text-foreground">
            {{ row.tenant_name }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 模型 -->
        <template #modelName_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon icon="lucide:brain" class="size-3.5 text-muted-foreground" />
            <span class="text-foreground">{{ row.model_name || '-' }}</span>
          </div>
        </template>

        <!-- 请求类型 -->
        <template #requestType_cell="{ row }">
          <Tag :color="getRequestTypeColor(row.request_type)" class="!m-0">
            {{ row.request_type || '-' }}
          </Tag>
        </template>

        <!-- Total Tokens -->
        <template #totalTokens_cell="{ row }">
          <span class="font-mono text-foreground">
            {{ formatTokens(row.total_tokens) }}
          </span>
        </template>

        <!-- Input Tokens -->
        <template #inputTokens_cell="{ row }">
          <span class="font-mono text-muted-foreground">
            {{ formatTokens(row.input_tokens) }}
          </span>
        </template>

        <!-- Output Tokens -->
        <template #outputTokens_cell="{ row }">
          <span class="font-mono text-muted-foreground">
            {{ formatTokens(row.output_tokens) }}
          </span>
        </template>

        <!-- 成功率 -->
        <template #successRate_cell="{ row }">
          <Tooltip :title="`${$t('admin.ai.usage.successCount')}: ${row.success_count} | ${$t('admin.ai.usage.failedCount')}: ${row.failed_count}`">
            <Progress
              :percent="row.call_count > 0 ? Math.round((row.success_count / row.call_count) * 100) : 0"
              :stroke-color="(row.success_count / row.call_count) >= 0.95 ? 'hsl(var(--success))' : (row.success_count / row.call_count) >= 0.8 ? 'hsl(var(--warning))' : 'hsl(var(--destructive))'"
              size="small"
              class="w-24"
            />
          </Tooltip>
        </template>

        <!-- Total Cost -->
        <template #totalCost_cell="{ row }">
          <span class="font-mono" :class="row.total_cost > 0 ? 'text-warning' : 'text-muted-foreground'">
            {{ formatCost(row.total_cost) }}
          </span>
        </template>

        <!-- 平均延迟 -->
        <template #avgLatency_cell="{ row }">
          <span
            class="font-mono text-sm"
            :class="row.avg_latency_ms > 5000 ? 'text-destructive' : row.avg_latency_ms > 2000 ? 'text-warning' : 'text-success'"
          >
            {{ formatLatency(row.avg_latency_ms) }}
          </span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
