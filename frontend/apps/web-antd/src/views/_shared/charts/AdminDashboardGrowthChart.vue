<script lang="ts" setup>
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { $t } from '#/locales';

interface GrowthItem {
  count: number;
  date: string;
}

const props = withDefaults(
  defineProps<{
    data: GrowthItem[];
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
  const data = props.data.slice(-14);
  if (data.length === 0) {
    return;
  }

  renderEcharts({
    color: ['#3b82f6', '#60a5fa'],
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
      data: data.map((item) => item.date.slice(5)),
      type: 'category',
    },
    yAxis: {
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      type: 'value',
    },
    series: [
      {
        areaStyle: { opacity: 0.16 },
        data: data.map((item) => item.count),
        name: $t('admin.dashboard.controlTower.growthSeries'),
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        type: 'line',
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
