<script lang="ts" setup>
import type { MonitoringConversationDetail, MonitoringScope } from '../api';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Avatar,
  Card,
  Drawer,
  Empty,
  Spin,
  Tag,
  Timeline,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

import { getMonitoringConversationDetail } from '../api';

const props = defineProps<{
  conversationId: null | number;
  i18nPrefix: string;
  open: boolean;
  scope: MonitoringScope;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const loading = ref(false);
const detail = ref<MonitoringConversationDetail | null>(null);

watch(
  () => [props.open, props.conversationId] as const,
  async ([open, id]) => {
    if (!open || !id) {
      detail.value = null;
      return;
    }
    loading.value = true;
    try {
      detail.value = await getMonitoringConversationDetail(props.scope, id, {
        message_limit: 200,
        message_skip: 0,
      });
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

const actorName = computed(() => {
  return (
    detail.value?.actor?.display_name ||
    detail.value?.actor?.nickname ||
    detail.value?.actor?.username ||
    '-'
  );
});

const successfulCallCount = computed(() => {
  return (
    detail.value?.call_trace.filter((trace) => trace.status === 'success')
      .length || 0
  );
});

const failedCallCount = computed(() => {
  return (
    detail.value?.call_trace.filter((trace) => trace.status !== 'success')
      .length || 0
  );
});

const averageLatency = computed(() => {
  const latencyList =
    detail.value?.call_trace
      .map((trace) => trace.latency_ms)
      .filter(
        (latency): latency is number =>
          latency !== null && latency !== undefined,
      ) || [];
  if (latencyList.length === 0) {
    return null;
  }
  const total = latencyList.reduce((sum, latency) => sum + latency, 0);
  return Math.round(total / latencyList.length);
});

const heroStats = computed(() => {
  if (!detail.value) {
    return [];
  }
  return [
    {
      icon: 'lucide:messages-square',
      key: 'messages',
      label: $t(`${props.i18nPrefix}.messageCount`),
      value: formatTokens(detail.value.message_count),
    },
    {
      icon: 'lucide:cpu',
      key: 'calls',
      label: $t(`${props.i18nPrefix}.totalCalls`),
      value: formatTokens(detail.value.call_count),
    },
    {
      icon: 'lucide:sigma',
      key: 'tokens',
      label: $t(`${props.i18nPrefix}.tokenCount`),
      value: formatTokens(detail.value.total_tokens),
    },
    {
      icon: 'lucide:badge-dollar-sign',
      key: 'cost',
      label: $t(`${props.i18nPrefix}.cost`),
      value: formatCost(detail.value.total_cost),
    },
  ];
});

const drawerTitle = computed(() => $t(`${props.i18nPrefix}.detailTitle`));

function actorTypeLabel(type?: null | string) {
  if (!type) {
    return '';
  }
  const key = `${props.i18nPrefix}.actorType.${type}`;
  const translated = $t(key);
  return translated === key ? type : translated;
}

function closeDrawer() {
  emits('update:open', false);
}

function formatCost(cost?: null | number) {
  return `$${Number(cost || 0).toFixed(4)}`;
}

function formatTokens(tokens?: null | number) {
  return Number(tokens || 0).toLocaleString();
}

function roleColor(role: string) {
  switch (role) {
    case 'assistant': {
      return 'success';
    }
    case 'system': {
      return 'orange';
    }
    case 'tool': {
      return 'purple';
    }
    default: {
      return 'blue';
    }
  }
}

function conversationStatusColor(status?: null | string) {
  switch (status) {
    case 'active': {
      return 'success';
    }
    case 'closed': {
      return 'error';
    }
    default: {
      return 'default';
    }
  }
}

function traceStatusColor(status?: null | string) {
  return status === 'success' ? 'success' : 'error';
}
</script>

<template>
  <Drawer
    class="monitoring-conversation-drawer"
    :open="open"
    :title="drawerTitle"
    :body-style="{
      background:
        'linear-gradient(180deg, hsl(var(--background)) 0%, hsl(var(--card)) 100%)',
      padding: '20px',
    }"
    width="980"
    @close="closeDrawer"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <section class="monitoring-hero">
          <div class="monitoring-hero__topline">
            <div
              class="inline-flex items-center gap-2 rounded-full bg-sky-500/10 px-3 py-1"
            >
              <IconifyIcon
                class="size-3.5 text-sky-600"
                icon="lucide:activity-square"
              />
              <span class="text-xs font-medium text-sky-700">
                {{ $t(`${i18nPrefix}.conversationTitle`) }}
              </span>
            </div>
          </div>

          <div class="monitoring-hero__content">
            <div class="monitoring-hero__main">
              <div class="monitoring-hero__title">
                {{ detail.title || '-' }}
              </div>
              <div class="monitoring-hero__meta">
                <span class="monitoring-hero__meta-item">
                  <IconifyIcon class="size-3.5" icon="lucide:bot" />
                  <span>{{ detail.agent_name || '-' }}</span>
                </span>
                <span class="monitoring-hero__meta-item">
                  <IconifyIcon class="size-3.5" icon="lucide:building-2" />
                  <span>{{ detail.tenant_name || '-' }}</span>
                </span>
                <span class="monitoring-hero__meta-item">
                  <IconifyIcon class="size-3.5" icon="lucide:user-round" />
                  <span>{{ actorName }}</span>
                </span>
              </div>
              <div class="mt-3 flex flex-wrap items-center gap-2">
                <Tag :color="conversationStatusColor(detail.status)">
                  {{ detail.status }}
                </Tag>
                <Tag v-if="detail.actor?.type" color="blue">
                  {{ actorTypeLabel(detail.actor.type) }}
                </Tag>
                <Tag v-if="detail.last_call_at" color="cyan">
                  {{ formatDate(detail.last_call_at) }}
                </Tag>
              </div>
            </div>

            <div class="monitoring-hero__stats">
              <div
                v-for="stat in heroStats"
                :key="stat.key"
                class="monitoring-hero__stat"
              >
                <div class="monitoring-hero__stat-label">
                  <IconifyIcon :icon="stat.icon" class="size-3.5" />
                  <span>{{ stat.label }}</span>
                </div>
                <div class="monitoring-hero__stat-value">{{ stat.value }}</div>
              </div>
            </div>
          </div>
        </section>

        <Card class="monitoring-card mt-4" :bordered="false">
          <template #title>
            <div class="monitoring-card__title">
              <IconifyIcon class="size-4" icon="lucide:scan-face" />
              <span>{{ $t('common.basicInfo') }}</span>
            </div>
          </template>

          <div class="monitoring-overview-grid">
            <div class="monitoring-overview-item">
              <div class="monitoring-overview-label">
                {{ $t(`${i18nPrefix}.agentName`) }}
              </div>
              <div class="monitoring-overview-value">
                <div class="flex items-center gap-2">
                  <Avatar
                    v-if="detail.agent_avatar"
                    :size="24"
                    :src="toAvatarDisplayUrl(detail.agent_avatar)"
                  />
                  <span>{{ detail.agent_name || '-' }}</span>
                </div>
              </div>
            </div>

            <div class="monitoring-overview-item">
              <div class="monitoring-overview-label">
                {{ $t(`${i18nPrefix}.user`) }}
              </div>
              <div class="monitoring-overview-value">
                <div class="flex items-center gap-2">
                  <Avatar
                    v-if="detail.actor?.avatar"
                    :size="24"
                    :src="toAvatarDisplayUrl(detail.actor.avatar)"
                  />
                  <span>{{ actorName }}</span>
                </div>
              </div>
            </div>

            <div class="monitoring-overview-item">
              <div class="monitoring-overview-label">
                {{ $t(`${i18nPrefix}.tenantName`) }}
              </div>
              <div class="monitoring-overview-value">
                {{ detail.tenant_name || '-' }}
              </div>
            </div>

            <div class="monitoring-overview-item">
              <div class="monitoring-overview-label">
                {{ $t(`${i18nPrefix}.status`) }}
              </div>
              <div class="monitoring-overview-value">
                <Tag :color="conversationStatusColor(detail.status)">
                  {{ detail.status }}
                </Tag>
              </div>
            </div>

            <div class="monitoring-overview-item">
              <div class="monitoring-overview-label">
                {{ $t(`${i18nPrefix}.createdAt`) }}
              </div>
              <div class="monitoring-overview-value">
                {{ formatDate(detail.created_at) }}
              </div>
            </div>

            <div class="monitoring-overview-item">
              <div class="monitoring-overview-label">
                {{ $t(`${i18nPrefix}.lastCallAt`) }}
              </div>
              <div class="monitoring-overview-value">
                {{
                  detail.last_call_at ? formatDate(detail.last_call_at) : '-'
                }}
              </div>
            </div>
          </div>
        </Card>

        <div class="mt-4 grid grid-cols-1 gap-4 2xl:grid-cols-2">
          <Card class="monitoring-card" :bordered="false">
            <template #title>
              <div class="monitoring-card__title">
                <IconifyIcon class="size-4" icon="lucide:messages-square" />
                <span>{{ $t(`${i18nPrefix}.tabMessages`) }}</span>
                <Tag color="blue">
                  {{ formatTokens(detail.message_list.length) }}
                </Tag>
              </div>
            </template>

            <Empty v-if="detail.message_list.length === 0" />

            <Timeline v-else class="monitoring-scroll-area">
              <Timeline.Item
                v-for="message in detail.message_list"
                :key="message.id"
                :color="roleColor(message.role)"
              >
                <div class="monitoring-message-item">
                  <div class="monitoring-message-head">
                    <Tag :color="roleColor(message.role)">
                      {{ message.role }}
                    </Tag>
                    <span class="text-xs text-muted-foreground">
                      #{{ message.sequence }}
                    </span>
                    <span class="text-xs text-muted-foreground">
                      {{ formatDate(message.created_at) }}
                    </span>
                    <span
                      v-if="message.token_count"
                      class="text-xs text-muted-foreground"
                    >
                      {{ formatTokens(message.token_count) }}
                    </span>
                    <Tag v-if="message.tool_name" color="purple">
                      {{ message.tool_name }}
                    </Tag>
                  </div>
                  <div
                    v-if="message.content"
                    class="monitoring-message-content"
                  >
                    {{ message.content }}
                  </div>
                  <div v-else class="text-xs text-muted-foreground">-</div>
                </div>
              </Timeline.Item>
            </Timeline>
          </Card>

          <Card class="monitoring-card" :bordered="false">
            <template #title>
              <div class="monitoring-card__title">
                <IconifyIcon class="size-4" icon="lucide:route" />
                <span>{{ $t(`${i18nPrefix}.tabModelCalls`) }}</span>
                <Tag color="cyan">
                  {{ formatTokens(detail.call_trace.length) }}
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
              v-if="detail.call_trace.length === 0"
              :description="$t(`${i18nPrefix}.modelCallsEmpty`)"
            />

            <Timeline v-else class="monitoring-scroll-area">
              <Timeline.Item
                v-for="trace in detail.call_trace"
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
                  </div>
                  <div
                    v-if="trace.usage_mode"
                    class="mt-1 text-xs text-muted-foreground"
                  >
                    usage_mode: {{ trace.usage_mode }}
                  </div>
                  <div
                    v-if="trace.error_message"
                    class="mt-1 text-xs text-destructive"
                  >
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
        </div>
      </template>
    </Spin>
  </Drawer>
</template>

<style scoped>
.monitoring-hero {
  border: 1px solid hsl(var(--border) / 0.25);
  border-radius: 16px;
  background:
    radial-gradient(
      circle at right top,
      hsl(var(--primary) / 0.14) 0%,
      transparent 52%
    ),
    linear-gradient(140deg, hsl(var(--background)) 0%, hsl(var(--card)) 60%);
  box-shadow:
    inset 0 1px 0 hsl(var(--background) / 0.7),
    0 16px 24px hsl(var(--foreground) / 0.07);
  padding: 18px 20px 20px;
}

.monitoring-hero__topline {
  margin-bottom: 12px;
}

.monitoring-hero__content {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  justify-content: space-between;
}

.monitoring-hero__main {
  flex: 1;
  min-width: 260px;
}

.monitoring-hero__title {
  color: hsl(var(--foreground) / 0.96);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
}

.monitoring-hero__meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}

.monitoring-hero__meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: hsl(var(--muted-foreground) / 0.96);
  font-size: 12px;
}

.monitoring-hero__stats {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(130px, 1fr));
  min-width: 300px;
}

.monitoring-hero__stat {
  border: 1px solid hsl(var(--border) / 0.24);
  border-radius: 12px;
  background: hsl(var(--background) / 0.72);
  padding: 10px 12px;
}

.monitoring-hero__stat-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: hsl(var(--muted-foreground) / 0.95);
  font-size: 12px;
}

.monitoring-hero__stat-value {
  margin-top: 4px;
  color: hsl(var(--foreground) / 0.98);
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 18px;
  font-weight: 700;
}

.monitoring-card {
  border: 1px solid hsl(var(--border) / 0.24);
  border-radius: 14px;
  background: hsl(var(--card) / 0.8);
  box-shadow: 0 10px 20px hsl(var(--foreground) / 0.05);
}

.monitoring-card :deep(.ant-card-head) {
  border-bottom: 1px solid hsl(var(--border) / 0.16);
  min-height: 54px;
  padding: 0 16px;
}

.monitoring-card :deep(.ant-card-head-title) {
  padding: 10px 0;
}

.monitoring-card :deep(.ant-card-body) {
  padding: 14px 16px 16px;
}

.monitoring-card__title {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-weight: 600;
}

.monitoring-overview-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.monitoring-overview-item {
  border: 1px solid hsl(var(--border) / 0.2);
  border-radius: 10px;
  background: hsl(var(--background) / 0.88);
  padding: 10px 12px;
}

.monitoring-overview-label {
  color: hsl(var(--muted-foreground) / 0.98);
  font-size: 12px;
  margin-bottom: 4px;
}

.monitoring-overview-value {
  color: hsl(var(--foreground) / 0.98);
  font-size: 13px;
  font-weight: 500;
}

.monitoring-scroll-area {
  max-height: 520px;
  overflow-y: auto;
  padding-right: 4px;
}

.monitoring-message-item,
.monitoring-trace-item {
  border: 1px solid hsl(var(--border) / 0.2);
  border-radius: 12px;
  background: hsl(var(--accent) / 0.65);
  padding: 10px 12px;
}

.monitoring-message-head,
.monitoring-trace-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
}

.monitoring-message-content {
  margin-top: 8px;
  border-radius: 10px;
  background: hsl(var(--background) / 0.88);
  border: 1px solid hsl(var(--border) / 0.18);
  color: hsl(var(--foreground) / 0.98);
  font-size: 13px;
  line-height: 1.55;
  padding: 8px 10px;
  white-space: pre-wrap;
}

.monitoring-trace-meta {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0 6px;
  color: hsl(var(--muted-foreground) / 0.95);
  font-size: 12px;
}

@media (max-width: 1280px) {
  .monitoring-overview-grid {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }

  .monitoring-hero__stats {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
    min-width: 100%;
  }
}
</style>
