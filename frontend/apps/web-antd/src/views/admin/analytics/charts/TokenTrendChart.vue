<script lang="ts" setup>
/**
 * @deprecated 已迁移至 _shared/charts/TokenTrendChart.vue
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

interface TrendItem {
  date: string;
  input_tokens: number;
  output_tokens: number;
}

const props = defineProps<{ data: TrendItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (!props.data.length) return;
  const dates = props.data.map((i) => i.date.slice(5));
  renderEcharts({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Input Tokens', 'Output Tokens'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      { name: 'Input Tokens', type: 'line', areaStyle: { opacity: 0.3 }, data: props.data.map((i) => i.input_tokens), smooth: true, itemStyle: { color: '#5B8FF9' }, stack: 'tokens' },
      { name: 'Output Tokens', type: 'line', areaStyle: { opacity: 0.3 }, data: props.data.map((i) => i.output_tokens), smooth: true, itemStyle: { color: '#5AD8A6' }, stack: 'tokens' },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI ref="chartRef" height="320px" />
</template>
