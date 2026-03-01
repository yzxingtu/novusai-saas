<script lang="ts" setup>
/**
 * T15: 延迟分布直方图
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';
import { Empty } from 'ant-design-vue';

import type { LatencyDistributionItem } from '#/api/admin/analytics';

const props = defineProps<{ data: LatencyDistributionItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (!props.data.length) return;
  renderEcharts({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: props.data.map((i) => i.range) },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: props.data.map((i) => i.count),
      itemStyle: {
        color: (params: { dataIndex: number }) => {
          const colors = ['#5AD8A6', '#5AD8A6', '#F6BD16', '#F6BD16', '#E86452', '#E86452'];
          return colors[params.dataIndex] || '#5B8FF9';
        },
        borderRadius: [4, 4, 0, 0],
      },
      barMaxWidth: 40,
    }],
  });
}

watch(() => props.data, render, { immediate: true });
</script>

<template>
  <EchartsUI v-if="data.length" ref="chartRef" height="320px" />
  <Empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" />
</template>
