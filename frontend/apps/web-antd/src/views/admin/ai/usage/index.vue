<script lang="ts" setup>
import type { EchartsUIType } from '@vben/plugins/echarts';

import type { AIUsageStatInfo } from '#/api/admin/ai';
import type { CallTrendItem } from '#/api/admin/analytics';

/**
 * 平台管理端 AI 使用量统计页面
 * Platform admin AI usage statistics page
 */
import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { Card, Progress, Spin, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAICallLogStatisticsApi, getAIUsageStatsApi } from '#/api/admin/ai';
import { getCallTrendApi } from '#/api/admin/analytics';
import { createRefreshPageOperation } from '#/composables';
import { $t } from '#/locales';

import AIPageHeroCard from '../_shared/AIPageHeroCard.vue';
import {
  formatCost,
  formatLatency,
  formatTokens,
  getRequestTypeColor,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'AdminAIUsage' });

const AI_PAGE_KEY = 'admin.ai.usage';
const USAGE_TABLE_PREVIEW_LIMIT = 8;

// ============================================================
// Summary statistics / 汇总统计
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

const heroMetrics = computed(() =>
  summaryCards.value.map((item) => ({
    key: item.key,
    label: item.label,
    value: item.value,
  })),
);

const heroChips = computed(() => [
  {
    key: 'dimensions',
    icon: 'lucide:table-properties',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t('admin.ai.usage.tenantName')} / ${$t('admin.ai.usage.modelName')} / ${$t('admin.ai.usage.requestType')}`,
  },
  {
    key: 'trend',
    icon: 'lucide:chart-column-big',
    className: 'bg-background/90 text-foreground',
    text: `${$t('admin.analytics.callTrend')} / ${$t('admin.analytics.tokenTrend')}`,
  },
  {
    key: 'focus',
    icon: 'lucide:scan-search',
    className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
    text: `${$t('admin.ai.usage.totalCost')} / ${$t('admin.ai.usage.successRate')} / ${$t('admin.ai.usage.avgLatency')}`,
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
    // Error handled by request interceptor / 错误由请求拦截器处理
  } finally {
    summaryLoading.value = false;
  }
}

onMounted(loadSummary);

// ============================================================
// ECharts trend charts / ECharts 趋势图表
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
    // Error handled by request interceptor / 错误由请求拦截器处理
  } finally {
    trendLoading.value = false;
  }
}

function renderCharts() {
  const data = trendData.value;
  if (data.length === 0) return;
  const dates = data.map((i) => i.date.slice(5));

  renderCallChart({
    tooltip: { trigger: 'axis' },
    legend: {
      data: [
        $t('admin.analytics.chart.calls'),
        $t('admin.analytics.chart.success'),
        $t('admin.analytics.chart.failed'),
      ],
      bottom: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '14%',
      top: '8%',
      containLabel: true,
    },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      {
        name: $t('admin.analytics.chart.calls'),
        type: 'line',
        data: data.map((i) => i.calls),
        smooth: true,
        itemStyle: { color: '#5B8FF9' },
      },
      {
        name: $t('admin.analytics.chart.success'),
        type: 'line',
        data: data.map((i) => i.success),
        smooth: true,
        itemStyle: { color: '#5AD8A6' },
      },
      {
        name: $t('admin.analytics.chart.failed'),
        type: 'line',
        data: data.map((i) => i.failed),
        smooth: true,
        itemStyle: { color: '#F6614E' },
      },
    ],
  });

  renderTokenChart({
    tooltip: { trigger: 'axis' },
    legend: {
      data: [
        $t('admin.analytics.chart.inputTokens'),
        $t('admin.analytics.chart.outputTokens'),
      ],
      bottom: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '14%',
      top: '8%',
      containLabel: true,
    },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      {
        name: $t('admin.analytics.chart.inputTokens'),
        type: 'line',
        areaStyle: { opacity: 0.3 },
        data: data.map((i) => i.input_tokens),
        smooth: true,
        itemStyle: { color: '#5B8FF9' },
        stack: 'tokens',
      },
      {
        name: $t('admin.analytics.chart.outputTokens'),
        type: 'line',
        areaStyle: { opacity: 0.3 },
        data: data.map((i) => i.output_tokens),
        smooth: true,
        itemStyle: { color: '#5AD8A6' },
        stack: 'tokens',
      },
    ],
  });
}

watch(trendData, renderCharts);
onMounted(loadTrend);

// ============================================================
// Grid / 表格
// ============================================================

function buildTrendPreview() {
  return trendData.value.slice(-7).map((item) => ({
    date: item.date,
    calls: item.calls,
    success: item.success,
    failed: item.failed,
    input_tokens: item.input_tokens,
    output_tokens: item.output_tokens,
  }));
}

function buildVisibleTablePreview() {
  const grid = gridApi.grid as unknown as {
    getTableData?: () => { tableData?: Record<string, unknown>[] };
  };
  const rows = (grid?.getTableData?.().tableData ??
    []) as unknown as AIUsageStatInfo[];

  return rows.slice(0, USAGE_TABLE_PREVIEW_LIMIT).map((row) => ({
    stat_date: row.stat_date,
    tenant_name: row.tenant_name ?? null,
    model_name: row.model_name ?? null,
    request_type: row.request_type,
    total_tokens: row.total_tokens,
    input_tokens: row.input_tokens,
    output_tokens: row.output_tokens,
    call_count: row.call_count,
    success_count: row.success_count,
    failed_count: row.failed_count,
    success_rate:
      row.call_count > 0
        ? Number(((row.success_count / row.call_count) * 100).toFixed(1))
        : 0,
    total_cost: row.total_cost,
    avg_latency_ms: row.avg_latency_ms,
  }));
}

async function refreshUsagePage() {
  await Promise.all([
    Promise.resolve(gridApi.query()),
    loadSummary(),
    loadTrend(),
  ]);
}

const { Grid, gridApi } = useCrudPage({
  api: {
    list: getAIUsageStatsApi,
    resource: '/admin/ai/usage/stats',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.ai.usage',
  defaultSort: '-stat_date',
  ai: {
    pageKey: AI_PAGE_KEY,
    entityName: $t('admin.ai.usage.name'),
    entityDescription: $t('admin.ai.usage.pageDesc'),
    contextExtras: () => {
      const visibleTablePreview = buildVisibleTablePreview();
      const recentTrend = buildTrendPreview();

      return {
        total_calls: summaryData.value.total_calls,
        total_tokens: summaryData.value.total_tokens,
        total_cost: summaryData.value.total_cost,
        success_calls: summaryData.value.success_calls,
        success_rate: successRate.value,
        visible_table_preview: visibleTablePreview,
        visible_table_row_count: visibleTablePreview.length,
        recent_call_trend: recentTrend,
      };
    },
    extra: [
      createRefreshPageOperation({
        description:
          'Reload the usage table, summary, and trend charts / 重新加载用量表格、摘要与趋势图',
        action: async () => {
          await refreshUsagePage();
        },
      }),
    ],
  },
  toolbar: {
    search: true,
    refresh: true,
    export: true,
    zoom: true,
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <Spin :spinning="summaryLoading">
      <AIPageHeroCard
        :chips="heroChips"
        :description="$t('admin.ai.usage.pageDesc')"
        icon="lucide:chart-column-big"
        icon-wrap-class="bg-primary/10 text-primary"
        :metrics="heroMetrics"
        :title="$t('admin.ai.usage.title')"
      />
    </Spin>

    <!-- Trend charts -->
    <Spin :spinning="trendLoading">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card
          :title="$t('admin.analytics.callTrend')"
          :body-style="{ padding: '12px' }"
        >
          <EchartsUI ref="callChartRef" height="240px" />
        </Card>
        <Card
          :title="$t('admin.analytics.tokenTrend')"
          :body-style="{ padding: '12px' }"
        >
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

        <!-- 企业 -->
        <template #tenantName_cell="{ row }">
          <span v-if="row.tenant_name" class="text-foreground">
            {{ row.tenant_name }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 模型 -->
        <template #modelName_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon
              icon="lucide:brain"
              class="size-3.5 text-muted-foreground"
            />
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
          <Tooltip
            :title="`${$t('admin.ai.usage.successCount')}: ${row.success_count} | ${$t('admin.ai.usage.failedCount')}: ${row.failed_count}`"
          >
            <Progress
              :percent="
                row.call_count > 0
                  ? Math.round((row.success_count / row.call_count) * 100)
                  : 0
              "
              :stroke-color="
                row.success_count / row.call_count >= 0.95
                  ? 'hsl(var(--success))'
                  : row.success_count / row.call_count >= 0.8
                    ? 'hsl(var(--warning))'
                    : 'hsl(var(--destructive))'
              "
              size="small"
              class="w-24"
            />
          </Tooltip>
        </template>

        <!-- Total Cost -->
        <template #totalCost_cell="{ row }">
          <span
            class="font-mono"
            :class="
              row.total_cost > 0 ? 'text-warning' : 'text-muted-foreground'
            "
          >
            {{ formatCost(row.total_cost) }}
          </span>
        </template>

        <!-- 平均延迟 -->
        <template #avgLatency_cell="{ row }">
          <span
            class="font-mono text-sm"
            :class="
              row.avg_latency_ms > 5000
                ? 'text-destructive'
                : row.avg_latency_ms > 2000
                  ? 'text-warning'
                  : 'text-success'
            "
          >
            {{ formatLatency(row.avg_latency_ms) }}
          </span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
