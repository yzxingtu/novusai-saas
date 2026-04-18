<script lang="ts" setup>
import type { MonitoringConversationDetail } from '../../api';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Card, Empty, Tag, Timeline } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { formatCost, formatTokens, traceStatusColor } from './helpers';

defineOptions({ name: 'MonitoringConversationCallTraceCard' });

const props = defineProps<{
  callTrace: MonitoringConversationDetail['call_trace'];
  i18nPrefix: string;
}>();

const successfulCallCount = computed(
  () => props.callTrace.filter((trace) => trace.status === 'success').length,
);

const failedCallCount = computed(
  () => props.callTrace.filter((trace) => trace.status !== 'success').length,
);

const averageLatency = computed(() => {
  const latencyList = props.callTrace
    .map((trace) => trace.latency_ms)
    .filter(
      (latency): latency is number => latency !== null && latency !== undefined,
    );
  if (latencyList.length === 0) {
    return null;
  }
  const total = latencyList.reduce((sum, latency) => sum + latency, 0);
  return Math.round(total / latencyList.length);
});
</script>

<template>
  <Card class="monitoring-card" :bordered="false">
    <template #title>
      <div class="monitoring-card__title">
        <IconifyIcon class="size-4" icon="lucide:route" />
        <span>{{ $t(`${i18nPrefix}.tabModelCalls`) }}</span>
        <Tag color="cyan">
          {{ formatTokens(callTrace.length) }}
        </Tag>
      </div>
    </template>

    <div class="mb-3 flex flex-wrap items-center gap-2">
      <Tag color="success">
        {{ $t(`${i18nPrefix}.toolOk`) }}:
        {{ formatTokens(successfulCallCount) }}
      </Tag>
      <Tag color="error">
        {{ $t(`${i18nPrefix}.toolFailed`) }}:
        {{ formatTokens(failedCallCount) }}
      </Tag>
      <Tag color="processing">
        {{ $t(`${i18nPrefix}.callLogLatency`) }}:
        {{ averageLatency == null ? '-' : `${averageLatency}ms` }}
      </Tag>
    </div>

    <Empty
      v-if="callTrace.length === 0"
      :description="$t(`${i18nPrefix}.modelCallsEmpty`)"
    />

    <Timeline v-else class="monitoring-scroll-area">
      <Timeline.Item
        v-for="trace in callTrace"
        :key="trace.id"
        :color="traceStatusColor(trace.status)"
      >
        <div class="monitoring-trace-item">
          <div class="monitoring-trace-head">
            <Tag :color="traceStatusColor(trace.status)">
              {{ trace.status }}
            </Tag>
            <span class="font-medium text-foreground">{{
              trace.model_name || '-'
            }}</span>
            <span class="text-xs text-muted-foreground">
              {{ trace.provider_name || '-' }}
            </span>
          </div>
          <div class="monitoring-trace-meta">
            <span>{{ formatDate(trace.created_at) }}</span>
            <span>·</span>
            <span>{{ trace.request_type }}</span>
            <span>·</span>
            <span>{{ formatTokens(trace.total_tokens) }}</span>
            <span>·</span>
            <span>{{ formatCost(trace.cost) }}</span>
            <template v-if="trace.latency_ms != null">
              <span>·</span>
              <span>{{ trace.latency_ms }}ms</span>
            </template>
            <template v-if="trace.usage_mode">
              <span>·</span>
              <Tag color="purple">{{ trace.usage_mode }}</Tag>
            </template>
          </div>
          <div v-if="trace.error_message" class="mt-1 text-xs text-destructive">
            <IconifyIcon
              icon="lucide:triangle-alert"
              class="mr-1 inline size-3.5"
            />
            {{ trace.error_message }}
          </div>
        </div>
      </Timeline.Item>
    </Timeline>
  </Card>
</template>
