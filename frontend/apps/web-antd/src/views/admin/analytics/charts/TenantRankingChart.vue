<script lang="ts" setup>
/**
 * T14: 租户 Top 10 水平柱状图
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import type { TenantRankingItem } from '#/api/admin/analytics';

const props = defineProps<{ data: TenantRankingItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (!props.data.length) return;
  const sorted = [...props.data].reverse();
  renderEcharts({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: sorted.map((i) => i.tenant_name) },
    series: [
      { name: 'Calls', type: 'bar', data: sorted.map((i) => i.calls), itemStyle: { color: '#5B8FF9', borderRadius: [0, 4, 4, 0] }, barMaxWidth: 20 },
    ],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI ref="chartRef" height="320px" />
</template>
