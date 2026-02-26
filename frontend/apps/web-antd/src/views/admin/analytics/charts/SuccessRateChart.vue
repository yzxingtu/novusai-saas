<script lang="ts" setup>
/**
 * T16: 成功率趋势折线图
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import type { SuccessRateTrendItem } from '#/api/admin/analytics';

const props = defineProps<{ data: SuccessRateTrendItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (!props.data.length) return;
  const dates = props.data.map((i) => i.date.slice(5));
  renderEcharts({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Rate', 'Total', 'Failed'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: [
      { type: 'value', name: '%', max: 100, position: 'left' },
      { type: 'value', name: 'Count', position: 'right' },
    ],
    series: [
      { name: 'Rate', type: 'line', data: props.data.map((i) => i.rate), smooth: true, itemStyle: { color: '#5AD8A6' }, yAxisIndex: 0 },
      { name: 'Total', type: 'bar', data: props.data.map((i) => i.total), itemStyle: { color: '#5B8FF9', opacity: 0.3 }, yAxisIndex: 1 },
      { name: 'Failed', type: 'bar', data: props.data.map((i) => i.failed), itemStyle: { color: '#E86452', opacity: 0.5 }, yAxisIndex: 1 },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI ref="chartRef" height="320px" />
</template>
