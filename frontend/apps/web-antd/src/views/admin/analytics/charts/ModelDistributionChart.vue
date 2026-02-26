<script lang="ts" setup>
/**
 * T12: 模型调用分布环形图
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

interface DistItem {
  model_name: string;
  calls: number;
}

const props = defineProps<{ data: DistItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

const COLORS = ['#5B8FF9', '#5AD8A6', '#F6BD16', '#E86452', '#6DC8EC', '#945FB9', '#FF9845', '#1E9493', '#FF99C3', '#269A99'];

function render() {
  if (!props.data.length) return;
  renderEcharts({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', bottom: 0, left: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 8, borderColor: 'transparent', borderWidth: 2 },
      label: { show: false, position: 'center' },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      labelLine: { show: false },
      color: COLORS,
      data: props.data.map((i) => ({ name: i.model_name, value: i.calls })),
    }],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI ref="chartRef" height="320px" />
</template>
