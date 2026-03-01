<script lang="ts" setup>
/**
 * AI 调用量趋势折线图（共享组件）
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';
import { Empty } from 'ant-design-vue';
import { $t } from '#/locales';

interface TrendItem {
  date: string;
  calls: number;
  success: number;
  failed: number;
}

const props = withDefaults(defineProps<{ data: TrendItem[]; i18nPrefix?: string }>(), {
  i18nPrefix: 'admin.analytics',
});

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (!props.data.length) return;
  const dates = props.data.map((i) => i.date.slice(5));
  renderEcharts({
    tooltip: { trigger: 'axis' },
    legend: { data: [$t(`${props.i18nPrefix}.chart.calls`), $t(`${props.i18nPrefix}.chart.success`), $t(`${props.i18nPrefix}.chart.failed`)], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      { name: $t(`${props.i18nPrefix}.chart.calls`), type: 'line', data: props.data.map((i) => i.calls), smooth: true, itemStyle: { color: '#5B8FF9' } },
      { name: $t(`${props.i18nPrefix}.chart.success`), type: 'line', data: props.data.map((i) => i.success), smooth: true, itemStyle: { color: '#5AD8A6' } },
      { name: $t(`${props.i18nPrefix}.chart.failed`), type: 'line', data: props.data.map((i) => i.failed), smooth: true, itemStyle: { color: '#F6614E' } },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI v-if="data.length" ref="chartRef" height="320px" />
  <Empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" />
</template>
