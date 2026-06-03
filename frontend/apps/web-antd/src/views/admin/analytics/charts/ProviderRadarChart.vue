<script lang="ts" setup>
/**
 * T13: 供应商性能雷达图
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import type { ProviderPerformanceItem } from '#/api/admin/analytics';

import { ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { Empty } from 'ant-design-vue';

import { $t } from '#/locales';

const props = defineProps<{ data: ProviderPerformanceItem[] }>();

const chartRef = ref<EchartsUIType>();
const { renderEcharts } = useEcharts(chartRef);

function render() {
  if (props.data.length === 0) return;
  const indicators = [
    {
      name: $t('admin.analytics.radar.calls'),
      max: Math.max(...props.data.map((i) => i.calls), 1),
    },
    { name: $t('admin.analytics.radar.successRate'), max: 100 },
    {
      name: $t('admin.analytics.radar.avgTokens'),
      max: Math.max(...props.data.map((i) => i.avg_tokens), 1),
    },
    {
      name: $t('admin.analytics.radar.speed'),
      max: Math.max(...props.data.map((i) => i.avg_latency), 1),
    },
  ];
  renderEcharts({
    tooltip: {},
    legend: { bottom: 0, data: props.data.map((i) => i.provider_name) },
    radar: { indicator: indicators, radius: '60%' },
    series: [
      {
        type: 'radar',
        data: props.data.map((p) => ({
          name: p.provider_name,
          value: [
            p.calls,
            p.success_rate,
            p.avg_tokens,
            indicators[3]!.max - p.avg_latency,
          ],
        })),
        areaStyle: { opacity: 0.15 },
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
