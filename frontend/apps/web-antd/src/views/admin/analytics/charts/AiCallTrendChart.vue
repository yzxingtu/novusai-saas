<script lang="ts" setup>
/**
 * @deprecated 已迁移至 _shared/charts/AiCallTrendChart.vue
 * 请从 '#/views/_shared/charts/AiCallTrendChart.vue' 导入
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

interface TrendItem {
  date: string;
  calls: number;
  success: number;
  failed: number;
}

const props = defineProps<{ data: TrendItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (!props.data.length) return;
  const dates = props.data.map((i) => i.date.slice(5));
  renderEcharts({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Calls', 'Success', 'Failed'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      { name: 'Calls', type: 'line', data: props.data.map((i) => i.calls), smooth: true, itemStyle: { color: '#5B8FF9' } },
      { name: 'Success', type: 'line', data: props.data.map((i) => i.success), smooth: true, itemStyle: { color: '#5AD8A6' } },
      { name: 'Failed', type: 'line', data: props.data.map((i) => i.failed), smooth: true, itemStyle: { color: '#F6614E' } },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI ref="chartRef" height="320px" />
</template>
