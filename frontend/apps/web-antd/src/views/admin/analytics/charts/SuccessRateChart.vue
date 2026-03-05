<script lang="ts" setup>
/**
 * T16: 成功率趋势折线图
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import type { SuccessRateTrendItem } from '#/api/admin/analytics';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { Empty } from 'ant-design-vue';

import { $t } from '#/locales';

const props = defineProps<{ data: SuccessRateTrendItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (props.data.length === 0) return;
  const dates = props.data.map((i) => i.date.slice(5));
  renderEcharts({
    tooltip: { trigger: 'axis' },
    legend: {
      data: [
        $t('admin.analytics.chart.rate'),
        $t('admin.analytics.chart.total'),
        $t('admin.analytics.chart.failed'),
      ],
      bottom: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: [
      {
        type: 'value',
        name: $t('admin.analytics.chart.percent'),
        max: 100,
        position: 'left',
      },
      {
        type: 'value',
        name: $t('admin.analytics.chart.count'),
        position: 'right',
      },
    ],
    series: [
      {
        name: $t('admin.analytics.chart.rate'),
        type: 'line',
        data: props.data.map((i) => i.rate),
        smooth: true,
        itemStyle: { color: '#5AD8A6' },
        yAxisIndex: 0,
      },
      {
        name: $t('admin.analytics.chart.total'),
        type: 'bar',
        data: props.data.map((i) => i.total),
        itemStyle: { color: '#5B8FF9', opacity: 0.3 },
        yAxisIndex: 1,
      },
      {
        name: $t('admin.analytics.chart.failed'),
        type: 'bar',
        data: props.data.map((i) => i.failed),
        itemStyle: { color: '#E86452', opacity: 0.5 },
        yAxisIndex: 1,
      },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI v-if="data.length > 0" ref="chartRef" height="320px" />
  <Empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" />
</template>
