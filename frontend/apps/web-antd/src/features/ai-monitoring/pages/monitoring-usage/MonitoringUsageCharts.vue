<script lang="ts" setup>
import type {
  MonitoringUsageBreakdownItem,
  MonitoringUsageDashboard,
} from '../../api';

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import dayjs from 'dayjs';

import { $t } from '#/locales';

import { formatNumber } from './formatters';

defineOptions({ name: 'MonitoringUsageCharts' });

const props = defineProps<{
  averageTokensPerCall: number;
  breakdownLabel: (item: MonitoringUsageBreakdownItem) => string;
  busiestDay: MonitoringUsageDashboard['daily_stats'][number] | null;
  dashboard: MonitoringUsageDashboard;
  i18nPrefix: string;
  rangeLabel: string;
  scopeLabel: string;
  totalCalls: number;
  topModel: MonitoringUsageBreakdownItem | null;
}>();

const callChartRef = ref();
const modelChartRef = ref();
const { renderEcharts: renderCallChart } = useEcharts(callChartRef);
const { renderEcharts: renderModelChart } = useEcharts(modelChartRef);
let themeObserver: MutationObserver | null = null;

const modelStatsCount = computed(() => props.dashboard.model_stats.length);

function cssVarColor(name: string, alpha?: number) {
  if (typeof window === 'undefined') {
    return '';
  }
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  if (!value) {
    return '';
  }
  return alpha === undefined ? `hsl(${value})` : `hsl(${value} / ${alpha})`;
}

function renderCharts() {
  const current = props.dashboard;
  if (!current) {
    return;
  }

  const primary = cssVarColor('--primary');
  const primarySoft = cssVarColor('--primary', 0.1);
  const success = cssVarColor('--success');
  const successSoft = cssVarColor('--success', 0.08);
  const warning = cssVarColor('--warning');
  const destructive = cssVarColor('--destructive');
  const mutedForeground = cssVarColor('--muted-foreground');
  const border = cssVarColor('--border');

  renderCallChart({
    color: [primary, success, warning],
    tooltip: { trigger: 'axis' },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: '8%',
      containLabel: true,
    },
    legend: {
      bottom: 0,
      icon: 'circle',
      data: [
        $t(`${props.i18nPrefix}.summary.totalCalls`),
        $t(`${props.i18nPrefix}.summary.totalTokens`),
        $t(`${props.i18nPrefix}.summary.totalCost`),
      ],
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: current.daily_stats.map((item) => item.date.slice(5)),
      axisLabel: { color: mutedForeground },
      axisLine: { lineStyle: { color: border } },
    },
    yAxis: [
      {
        type: 'value',
        name: $t(`${props.i18nPrefix}.summary.totalCalls`),
        axisLabel: { color: mutedForeground },
        splitLine: { lineStyle: { color: cssVarColor('--border', 0.28) } },
      },
      {
        type: 'value',
        name: $t(`${props.i18nPrefix}.summary.totalTokens`),
        axisLabel: { color: mutedForeground },
        splitLine: { show: false },
      },
      {
        type: 'value',
        show: false,
      },
    ],
    series: [
      {
        name: $t(`${props.i18nPrefix}.summary.totalCalls`),
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { width: 3 },
        areaStyle: {
          color: primarySoft,
        },
        data: current.daily_stats.map((item) => item.call_count),
      },
      {
        name: $t(`${props.i18nPrefix}.summary.totalTokens`),
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2.5 },
        areaStyle: {
          color: successSoft,
        },
        data: current.daily_stats.map((item) => item.total_tokens),
      },
      {
        name: $t(`${props.i18nPrefix}.summary.totalCost`),
        type: 'bar',
        yAxisIndex: 2,
        barMaxWidth: 18,
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: cssVarColor('--warning', 0.58),
        },
        data: current.daily_stats.map((item) => item.total_cost),
      },
    ],
  });

  renderModelChart({
    color: [
      primary,
      success,
      warning,
      destructive,
      cssVarColor('--secondary-foreground'),
      cssVarColor('--muted-foreground'),
    ],
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      type: 'scroll',
      bottom: 0,
      left: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: mutedForeground },
    },
    series: [
      {
        type: 'pie',
        radius: ['48%', '74%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: { show: false },
        emphasis: {
          scale: true,
          itemStyle: {
            shadowBlur: 12,
            shadowColor: 'rgba(15, 23, 42, 0.18)',
          },
        },
        data: current.model_stats.map((item) => ({
          name: props.breakdownLabel(item),
          value: item.call_count,
        })),
      },
    ],
  });
}

watch(
  () => [props.dashboard, callChartRef.value, modelChartRef.value],
  async () => {
    if (!props.dashboard || !callChartRef.value || !modelChartRef.value) {
      return;
    }
    await nextTick();
    renderCharts();
  },
  { flush: 'post' },
);

onMounted(() => {
  if (typeof window !== 'undefined') {
    themeObserver = new MutationObserver(() => {
      if (props.dashboard) {
        void nextTick().then(renderCharts);
      }
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-theme', 'style'],
    });
  }
});

onBeforeUnmount(() => {
  themeObserver?.disconnect();
  themeObserver = null;
});
</script>

<template>
  <article class="monitoring-surface">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="monitoring-surface__eyebrow">
          {{ $t(`${i18nPrefix}.chart.dailyTrend`) }}
        </p>
        <h3 class="monitoring-surface__title">{{ rangeLabel }}</h3>
        <p class="monitoring-surface__desc">
          {{ scopeLabel }} ·
          {{ $t(`${i18nPrefix}.summary.totalCalls`) }}
          {{ formatNumber(totalCalls) }}
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <span class="monitoring-chip monitoring-chip--sky">
          {{ $t(`${i18nPrefix}.snapshot.busiestDay`) }}
          <strong class="ml-1 font-semibold">
            {{
              busiestDay
                ? dayjs(busiestDay.date).format('MM-DD')
                : $t(`${i18nPrefix}.snapshot.empty`)
            }}
          </strong>
        </span>
        <span class="monitoring-chip monitoring-chip--amber">
          {{ $t(`${i18nPrefix}.metrics.avgTokensPerCall`) }}
          <strong class="ml-1 font-semibold">
            {{ formatNumber(averageTokensPerCall) }}
          </strong>
        </span>
      </div>
    </div>

    <div class="monitoring-chart-shell mt-4">
      <EchartsUI ref="callChartRef" height="286px" />
    </div>
  </article>

  <article class="monitoring-surface">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="monitoring-surface__eyebrow">
          {{ $t(`${i18nPrefix}.chart.modelDistribution`) }}
        </p>
        <h3 class="monitoring-surface__title">
          {{
            topModel
              ? breakdownLabel(topModel)
              : $t(`${i18nPrefix}.snapshot.empty`)
          }}
        </h3>
        <p class="monitoring-surface__desc">
          {{ $t(`${i18nPrefix}.snapshot.topModel`) }}
        </p>
      </div>
      <span class="monitoring-chip monitoring-chip--violet">
        {{ formatNumber(modelStatsCount) }}
      </span>
    </div>

    <div class="monitoring-chart-shell mt-4">
      <EchartsUI ref="modelChartRef" height="224px" />
    </div>
  </article>
</template>
