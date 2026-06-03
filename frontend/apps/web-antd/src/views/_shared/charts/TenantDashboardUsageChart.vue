<script lang="ts" setup>
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { $t } from '#/locales';

interface TrendItem {
  calls: number;
  date: string;
  tokens: number;
}

const props = withDefaults(
  defineProps<{
    data: TrendItem[];
    emptyText: string;
    height?: string;
  }>(),
  {
    height: '280px',
  },
);

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (props.data.length === 0) {
    return;
  }

  renderEcharts({
    color: ['#2563eb', '#10b981'],
    grid: {
      bottom: 12,
      containLabel: true,
      left: 20,
      right: 20,
      top: 30,
    },
    legend: {
      itemHeight: 8,
      itemWidth: 8,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    tooltip: { trigger: 'axis' },
    xAxis: {
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      data: props.data.map((item) => item.date.slice(5)),
      type: 'category',
    },
    yAxis: [
      {
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        type: 'value',
      },
      {
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        splitLine: { show: false },
        type: 'value',
      },
    ],
    series: [
      {
        barMaxWidth: 22,
        data: props.data.map((item) => item.calls),
        name: $t('tenant.dashboard.cockpit.trend.calls'),
        type: 'bar',
      },
      {
        data: props.data.map((item) => item.tokens),
        name: $t('tenant.dashboard.cockpit.trend.tokens'),
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        type: 'line',
        yAxisIndex: 1,
      },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI v-if="data.length > 0" ref="chartRef" :height="height" />
  <div
    v-else
    class="flex items-center justify-center rounded-[22px] border border-dashed border-border/70 bg-background/60 text-sm text-muted-foreground"
    :style="{ height }"
  >
    {{ emptyText }}
  </div>
</template>
