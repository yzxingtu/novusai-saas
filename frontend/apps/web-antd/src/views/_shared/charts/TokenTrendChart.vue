<script lang="ts" setup>
/**
 * Token 消耗趋势面积图（共享组件）
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { Empty } from 'ant-design-vue';

import { $t } from '#/locales';

interface TrendItem {
  date: string;
  input_tokens: number;
  output_tokens: number;
}

const props = withDefaults(
  defineProps<{ data: TrendItem[]; i18nPrefix?: string }>(),
  {
    i18nPrefix: 'admin.analytics',
  },
);

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (props.data.length === 0) return;
  const dates = props.data.map((i) => i.date.slice(5));
  renderEcharts({
    tooltip: { trigger: 'axis' },
    legend: {
      data: [
        $t(`${props.i18nPrefix}.chart.inputTokens`),
        $t(`${props.i18nPrefix}.chart.outputTokens`),
      ],
      bottom: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      {
        name: $t(`${props.i18nPrefix}.chart.inputTokens`),
        type: 'line',
        areaStyle: { opacity: 0.3 },
        data: props.data.map((i) => i.input_tokens),
        smooth: true,
        itemStyle: { color: '#5B8FF9' },
        stack: 'tokens',
      },
      {
        name: $t(`${props.i18nPrefix}.chart.outputTokens`),
        type: 'line',
        areaStyle: { opacity: 0.3 },
        data: props.data.map((i) => i.output_tokens),
        smooth: true,
        itemStyle: { color: '#5AD8A6' },
        stack: 'tokens',
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
