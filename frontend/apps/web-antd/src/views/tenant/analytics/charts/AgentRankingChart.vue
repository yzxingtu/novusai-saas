<script lang="ts" setup>
/**
 * T11: Agent 调用排行水平柱状图
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';
import { Empty } from 'ant-design-vue';
import { $t } from '#/locales';

import type { AgentRankingItem } from '#/api/tenant/analytics';

const props = defineProps<{ data: AgentRankingItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (!props.data.length) return;
  const sorted = [...props.data].reverse();
  renderEcharts({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: sorted.map((i) => i.agent_name) },
    series: [
      { name: $t('tenant.analytics.chart.calls'), type: 'bar', data: sorted.map((i) => i.calls), itemStyle: { color: '#5B8FF9', borderRadius: [0, 4, 4, 0] }, barMaxWidth: 20 },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI v-if="data.length" ref="chartRef" height="320px" />
  <Empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" />
</template>
