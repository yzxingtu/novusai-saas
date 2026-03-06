<script lang="ts" setup>
/**
 * 租户端 AI 用量统计页面
 */
import type { Dayjs } from 'dayjs';

import type { EchartsUIType } from '@vben/plugins/echarts';

import type { TenantAIUsageSummary } from '#/api/tenant/ai';
import type {
  CallTrendItem,
  ModelDistributionItem,
} from '#/api/tenant/analytics';

import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { Button, Card, DatePicker, Spin } from 'ant-design-vue';
import dayjs from 'dayjs';

import { getTenantAIUsageSummaryApi } from '#/api/tenant/ai';
import {
  getTenantCallTrendApi,
  getTenantModelDistributionApi,
} from '#/api/tenant/analytics';
import { $t } from '#/locales';

defineOptions({ name: 'TenantAIUsage' });

// ============ 日期范围 ============

type DateRange = [Dayjs, Dayjs];

const dateRange = ref<DateRange>([
  dayjs().subtract(29, 'day').startOf('day'),
  dayjs().endOf('day'),
]);

const presets = computed(() => [
  {
    label: $t('tenant.ai.usage.last7Days'),
    value: [
      dayjs().subtract(6, 'day').startOf('day'),
      dayjs().endOf('day'),
    ] as DateRange,
  },
  {
    label: $t('tenant.ai.usage.last30Days'),
    value: [
      dayjs().subtract(29, 'day').startOf('day'),
      dayjs().endOf('day'),
    ] as DateRange,
  },
  {
    label: $t('tenant.ai.usage.thisMonth'),
    value: [dayjs().startOf('month'), dayjs().endOf('day')] as DateRange,
  },
]);

function handleDateChange(dates: [string, string] | DateRange | null) {
  if (dates && dates[0] instanceof dayjs && dates[1] instanceof dayjs) {
    dateRange.value = dates as DateRange;
    loadSummary();
    loadCharts();
  }
}

function handlePreset(range: DateRange) {
  dateRange.value = range;
  loadSummary();
  loadCharts();
}

// ============ 数据加载 ============

const loading = ref(false);
const summary = ref<null | TenantAIUsageSummary>(null);

async function loadSummary() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {};
    if (dateRange.value[0]) {
      params.start_date = dateRange.value[0].format('YYYY-MM-DD');
    }
    if (dateRange.value[1]) {
      params.end_date = dateRange.value[1].format('YYYY-MM-DD');
    }
    summary.value = await getTenantAIUsageSummaryApi(params);
  } catch {
    // Error handled by request interceptor
  } finally {
    loading.value = false;
  }
}

const successRate = computed(() => {
  if (!summary.value || summary.value.total_calls === 0) return '0%';
  const rate = (summary.value.success_calls / summary.value.total_calls) * 100;
  return `${rate.toFixed(1)}%`;
});

const formatCost = (cost: number | undefined) => {
  if (!cost) return '$0.00';
  return `$${cost.toFixed(4)}`;
};

const formatTokens = (tokens: number | undefined) => {
  if (!tokens) return '0';
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(2)}M`;
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
  return `${tokens}`;
};

onMounted(loadSummary);

// ============ ECharts ============

const callChartRef = ref<EchartsUIType>();
const modelChartRef = ref<EchartsUIType>();
const { renderEcharts: renderCallChart } = useEcharts(callChartRef);
const { renderEcharts: renderModelChart } = useEcharts(modelChartRef);

const trendData = ref<CallTrendItem[]>([]);
const modelData = ref<ModelDistributionItem[]>([]);

async function loadCharts() {
  const params: Record<string, unknown> = {};
  if (dateRange.value[0])
    params.start_date = dateRange.value[0].format('YYYY-MM-DD');
  if (dateRange.value[1])
    params.end_date = dateRange.value[1].format('YYYY-MM-DD');
  try {
    const [ct, md] = await Promise.allSettled([
      getTenantCallTrendApi(
        params as { end_date?: string; start_date?: string },
      ),
      getTenantModelDistributionApi(
        params as { end_date?: string; start_date?: string },
      ),
    ]);
    if (ct.status === 'fulfilled') trendData.value = ct.value;
    if (md.status === 'fulfilled') modelData.value = md.value;
  } catch {
    /* handled */
  }
}

function renderCharts() {
  const data = trendData.value;
  if (data.length > 0) {
    const dates = data.map((i) => i.date.slice(5));
    renderCallChart({
      tooltip: { trigger: 'axis' },
      legend: {
        data: [
          $t('tenant.analytics.chart.calls'),
          $t('tenant.analytics.chart.tokens'),
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
      yAxis: [
        { type: 'value', name: $t('tenant.analytics.chart.calls') },
        { type: 'value', name: $t('tenant.analytics.chart.tokens') },
      ],
      series: [
        {
          name: $t('tenant.analytics.chart.calls'),
          type: 'line',
          data: data.map((i) => i.calls),
          smooth: true,
          itemStyle: { color: '#5B8FF9' },
        },
        {
          name: $t('tenant.analytics.chart.tokens'),
          type: 'line',
          areaStyle: { opacity: 0.2 },
          data: data.map((i) => i.tokens),
          smooth: true,
          itemStyle: { color: '#5AD8A6' },
          yAxisIndex: 1,
        },
      ],
    });
  }
  const md = modelData.value;
  if (md.length > 0) {
    const COLORS = [
      '#5B8FF9',
      '#5AD8A6',
      '#F6BD16',
      '#E86452',
      '#6DC8EC',
      '#945FB9',
      '#FF9845',
      '#1E9493',
      '#FF99C3',
      '#269A99',
    ];
    renderModelChart({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { type: 'scroll', bottom: 0, left: 'center' },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 8,
            borderColor: 'transparent',
            borderWidth: 2,
          },
          label: { show: false, position: 'center' },
          emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
          labelLine: { show: false },
          color: COLORS,
          data: md.map((i) => ({ name: i.model_name, value: i.calls })),
        },
      ],
    });
  }
}

watch([trendData, modelData], renderCharts);
onMounted(loadCharts);

const cleanupPageContext = registerPageContext('tenant/ai/usage', () => ({
  page_key: 'tenant.ai.usage',
  page_title: $t('tenant.ai.usage.name'),
  page_data: {
    resource: '/tenant/ai/usage',
    total_calls: summary.value?.total_calls ?? 0,
    total_tokens: summary.value?.total_tokens ?? 0,
    total_cost: summary.value?.total_cost ?? 0,
  },
}));

onUnmounted(cleanupPageContext);
</script>

<template>
  <Page
    auto-content-height
    :description="$t('tenant.ai.usage.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 日期范围筛选 -->
    <Card :body-style="{ padding: '12px 16px' }">
      <div class="flex flex-wrap items-center gap-3">
        <span class="text-sm font-medium text-foreground">
          {{ $t('tenant.ai.usage.dateRange') }}
        </span>
        <div class="flex items-center gap-2">
          <Button
            v-for="preset in presets"
            :key="preset.label"
            size="small"
            :type="
              dateRange[0]?.format('YYYY-MM-DD') ===
                preset.value[0].format('YYYY-MM-DD') &&
              dateRange[1]?.format('YYYY-MM-DD') ===
                preset.value[1].format('YYYY-MM-DD')
                ? 'primary'
                : 'default'
            "
            @click="handlePreset(preset.value)"
          >
            {{ preset.label }}
          </Button>
        </div>
        <DatePicker.RangePicker
          :value="dateRange"
          format="YYYY-MM-DD"
          :allow-clear="false"
          size="small"
          class="w-56"
          @change="handleDateChange"
        />
      </div>
    </Card>

    <Spin :spinning="loading">
      <!-- 统计卡片 -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <!-- 总 Tokens -->
        <Card :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-3">
            <div
              class="flex size-12 items-center justify-center rounded-xl bg-primary/10"
            >
              <IconifyIcon icon="lucide:hash" class="size-6 text-primary" />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">
                {{ $t('tenant.ai.usage.summary.totalTokens') }}
              </div>
              <div class="text-2xl font-bold text-foreground">
                {{ formatTokens(summary?.total_tokens) }}
              </div>
            </div>
          </div>
        </Card>

        <!-- 总费用 -->
        <Card :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-3">
            <div
              class="flex size-12 items-center justify-center rounded-xl bg-warning/10"
            >
              <IconifyIcon
                icon="lucide:dollar-sign"
                class="size-6 text-warning"
              />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">
                {{ $t('tenant.ai.usage.summary.totalCost') }}
              </div>
              <div class="text-2xl font-bold text-foreground">
                {{ formatCost(summary?.total_cost) }}
              </div>
            </div>
          </div>
        </Card>

        <!-- 调用次数 -->
        <Card :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-3">
            <div
              class="flex size-12 items-center justify-center rounded-xl bg-success/10"
            >
              <IconifyIcon icon="lucide:activity" class="size-6 text-success" />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">
                {{ $t('tenant.ai.usage.summary.totalCalls') }}
              </div>
              <div class="text-2xl font-bold text-foreground">
                {{ summary?.total_calls || 0 }}
              </div>
            </div>
          </div>
        </Card>

        <!-- 成功率 -->
        <Card :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-3">
            <div
              class="flex size-12 items-center justify-center rounded-xl bg-success/10"
            >
              <IconifyIcon
                icon="lucide:check-circle"
                class="size-6 text-success"
              />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">
                {{ $t('tenant.ai.usage.summary.successRate') }}
              </div>
              <div class="text-2xl font-bold text-foreground">
                {{ successRate }}
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- ECharts 趋势图 -->
      <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card
          :title="$t('tenant.ai.usage.chart.dailyTrend')"
          :body-style="{ padding: '12px' }"
        >
          <EchartsUI ref="callChartRef" height="260px" />
        </Card>
        <Card
          :title="$t('tenant.ai.usage.chart.modelDistribution')"
          :body-style="{ padding: '12px' }"
        >
          <EchartsUI ref="modelChartRef" height="260px" />
        </Card>
      </div>

      <!-- 空状态 -->
      <Card
        v-if="!loading && (!summary || summary.total_calls === 0)"
        class="mt-4"
        :body-style="{ padding: '48px', textAlign: 'center' }"
      >
        <IconifyIcon
          icon="lucide:bar-chart-3"
          class="mx-auto mb-4 size-12 text-muted-foreground"
        />
        <div class="text-muted-foreground">{{ $t('common.noData') }}</div>
      </Card>
    </Spin>
  </Page>
</template>
