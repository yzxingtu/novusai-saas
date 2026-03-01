<script lang="ts" setup>
/**
 * T12: 费用趋势折线图
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';
import { Empty } from 'ant-design-vue';
import { $t } from '#/locales';

import type { CostTrendItem } from '#/api/tenant/analytics';

const props = defineProps<{ data: CostTrendItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (!props.data.length) return;
  const dates = props.data.map((i) => i.date.slice(5));
  renderEcharts({
    tooltip: { trigger: 'axis' },
    legend: { data: [$t('tenant.analytics.chart.cost'), $t('tenant.analytics.chart.calls')], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: [
      { type: 'value', name: $t('tenant.analytics.chart.costUnit'), position: 'left' },
      { type: 'value', name: $t('tenant.analytics.chart.calls'), position: 'right' },
    ],
    series: [
      { name: $t('tenant.analytics.chart.cost'), type: 'line', areaStyle: { opacity: 0.2 }, data: props.data.map((i) => i.cost), smooth: true, itemStyle: { color: '#F6BD16' }, yAxisIndex: 0 },
      { name: $t('tenant.analytics.chart.calls'), type: 'bar', data: props.data.map((i) => i.calls), itemStyle: { color: '#5B8FF9', opacity: 0.3 }, yAxisIndex: 1 },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI v-if="data.length" ref="chartRef" height="320px" />
  <Empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" />
</template>
