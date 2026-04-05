<script lang="ts" setup>
import type {
  MonitoringConversationDetail,
  MonitoringIntentPlanItem,
  MonitoringProviderEvent,
  MonitoringRetryEvent,
  MonitoringRuntimeDiagnostics,
  MonitoringScope,
} from '../api';

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
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate, formatTimeOnly } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

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

function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

function getInitialLetter(value: null | string | undefined): string {
  const text = String(value || '').trim();
  return text ? text.charAt(0).toUpperCase() : '?';
}

const detailAgentName = computed(() => detail.value?.agent_name || '-');

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

function getActorDisplayName(actor?: MonitoringConversationDetail['actor']) {
  if (!actor) {
    return '-';
  }
  return actor.display_name || actor.nickname || actor.username || '-';
}

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

function asRecord(
  value: null | Record<string, unknown> | unknown,
): null | Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asRecordArray<T extends Record<string, unknown>>(value: unknown): T[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is T =>
      Boolean(item) && typeof item === 'object' && !Array.isArray(item),
  );
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => asString(item))
    .filter(
      (item, index, list) => Boolean(item) && list.indexOf(item) === index,
    );
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function hasEntries(
  value: null | Record<string, unknown> | undefined,
): boolean {
  return Boolean(value && Object.keys(value).length > 0);
}

function translateOption(
  group: string,
  value: null | string | undefined,
): string {
  const raw = asString(value);
  if (!raw) {
    return '-';
  }
  const key = `${props.i18nPrefix}.${group}.${raw}`;
  const translated = $t(key);
  return translated === key ? raw : translated;
}

const runtimeDiagnostics = computed<MonitoringRuntimeDiagnostics | null>(() => {
  if (!detail.value) {
    return null;
  }
  const metadata = asRecord(detail.value.metadata);
  const contextDiagnostics =
    asRecord(detail.value.context_diagnostics) ||
    asRecord(metadata?.context_diagnostics);
  const lastRunSummary =
    asRecord(detail.value.last_run_summary) ||
    asRecord(metadata?.last_run_summary);
  const merged = {
    ...contextDiagnostics,
    ...lastRunSummary,
  } as MonitoringRuntimeDiagnostics;
  return hasEntries(merged) ? merged : null;
});

const intentPlanItems = computed<MonitoringIntentPlanItem[]>(() =>
  asRecordArray<MonitoringIntentPlanItem>(
    runtimeDiagnostics.value?.intent_plan,
  ),
);

const providerEvents = computed<MonitoringProviderEvent[]>(() =>
  asRecordArray<MonitoringProviderEvent>(
    runtimeDiagnostics.value?.provider_events,
  ),
);

const retryEvents = computed<MonitoringRetryEvent[]>(() =>
  asRecordArray<MonitoringRetryEvent>(runtimeDiagnostics.value?.retry_events),
);

const candidateToolNames = computed(() =>
  asStringArray(runtimeDiagnostics.value?.candidate_tool_names),
);

const diagnosticsSummary = computed(() => {
  const diagnostics = runtimeDiagnostics.value;
  if (!diagnostics) {
    return [];
  }
  const summaryItems = [
    {
      key: 'path',
      label: $t(`${props.i18nPrefix}.executionPath`),
      value: translateOption(
        'executionPathOptions',
        diagnostics.execution_path,
      ),
    },
    {
      key: 'failure',
      label: $t(`${props.i18nPrefix}.failureKind`),
      value: translateOption('failureKindOptions', diagnostics.failure_kind),
    },
    {
      key: 'budget',
      label: $t(`${props.i18nPrefix}.budgetStatus`),
      value: translateOption('budgetStatusOptions', diagnostics.budget_status),
    },
    {
      key: 'budgetExitReason',
      label: $t(`${props.i18nPrefix}.budgetExitReason`),
      value: asString(diagnostics.budget_exit_reason),
    },
    {
      key: 'providerEvents',
      label: $t(`${props.i18nPrefix}.providerEvents`),
      value: formatTokens(providerEvents.value.length),
    },
    {
      key: 'retryEvents',
      label: $t(`${props.i18nPrefix}.retryEvents`),
      value: formatTokens(retryEvents.value.length),
    },
  ];
  return summaryItems.filter((item) => item.value && item.value !== '-');
});

const diagnosticsDetailRows = computed(() => {
  const diagnostics = runtimeDiagnostics.value;
  if (!diagnostics) {
    return [];
  }
  return [
    {
      key: 'budgetExitReason',
      label: $t(`${props.i18nPrefix}.budgetExitReason`),
      value: asString(diagnostics.budget_exit_reason),
    },
    {
      key: 'partialExitReason',
      label: $t(`${props.i18nPrefix}.partialExitReason`),
      value: asString(diagnostics.partial_exit_reason),
    },
  ].filter((item) => item.value);
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

const actorIdentityModel = computed(() => {
  const actor = detail.value?.actor;
  if (!actor) {
    return null;
  }

  return {
    avatar: actor.avatar,
    badges: actor.type
      ? [
          {
            color: 'blue',
            key: `actor-type-${actor.id ?? actor.username ?? 'unknown'}`,
            label: actorTypeLabel(actor.type),
          },
        ]
      : [],
    displayName: actor.display_name,
    id: actor.id ?? '-',
    isActive: actor.is_active,
    isLeader: actor.is_leader,
    isOwner: actor.is_owner,
    nickname: getActorDisplayName(actor),
    orgNodeName: actor.org_node_name,
    roleName: actor.role_name,
    username: actor.display_name || actor.nickname ? undefined : actor.username,
  };
});

const actorIdentityMeta = computed<IdentityDetailMeta>(() => ({
  orgNodeName: detail.value?.actor?.org_node_name,
  roleName: detail.value?.actor?.role_name,
  scope: props.scope,
  subjectType: detail.value?.actor?.type,
  tenantName: detail.value?.tenant_name,
  userType: detail.value?.actor?.type,
  username:
    detail.value?.actor?.username ||
    detail.value?.actor?.display_name ||
    detail.value?.actor?.nickname ||
    undefined,
}));

function closeDrawer() {
  emits('update:open', false);
}

function formatCost(cost?: null | number) {
  return `$${Number(cost || 0).toFixed(4)}`;
}

function formatTokens(tokens?: null | number) {
  return Number(tokens || 0).toLocaleString();
}

function formatTagValue(value: null | string | undefined): string {
  return asString(value) || '-';
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
                  <span
                    class="flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10 text-primary"
                  >
                    <img
                      v-if="
                        detail.agent_avatar &&
                        !isIconAvatar(detail.agent_avatar)
                      "
                      :alt="detailAgentName"
                      :src="toAvatarDisplayUrl(detail.agent_avatar)"
                      class="size-full object-cover"
                    />
                    <IconifyIcon
                      v-else-if="isIconAvatar(detail.agent_avatar)"
                      :icon="String(detail.agent_avatar)"
                      class="size-4"
                    />
                    <span v-else class="text-[11px] font-semibold">
                      {{ getInitialLetter(detailAgentName) }}
                    </span>
                  </span>
                  <span>{{ detailAgentName }}</span>
                </span>
                <span class="monitoring-hero__meta-item">
                  <IconifyIcon class="size-3.5" icon="lucide:building-2" />
                  <span>{{ detail.tenant_name || '-' }}</span>
                </span>
                <div
                  v-if="actorIdentityModel"
                  class="min-w-[180px] rounded-xl bg-background/75 px-2 py-2"
                >
                  <IdentityTrigger
                    :avatar-size="32"
                    :model="actorIdentityModel"
                    :meta="actorIdentityMeta"
                  />
                </div>
              </div>
              <div class="mt-3 flex flex-wrap items-center gap-2">
                <Tag :color="conversationStatusColor(detail.status)">
                  {{ detail.status }}
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
                    v-if="
                      detail.agent_avatar && !isIconAvatar(detail.agent_avatar)
                    "
                    :size="24"
                    :src="toAvatarDisplayUrl(detail.agent_avatar)"
                  />
                  <IconifyIcon
                    v-else-if="isIconAvatar(detail.agent_avatar)"
                    :icon="String(detail.agent_avatar)"
                    class="size-4 text-primary"
                  />
                  <Avatar
                    v-else
                    :size="24"
                    class="bg-primary/10 text-xs text-primary"
                  >
                    {{ getInitialLetter(detailAgentName) }}
                  </Avatar>
                  <span>{{ detailAgentName }}</span>
                </div>
              </div>
            </div>

            <div class="monitoring-overview-item">
              <div class="monitoring-overview-label">
                {{ $t(`${i18nPrefix}.user`) }}
              </div>
              <div class="monitoring-overview-value">
                <IdentityTrigger
                  v-if="actorIdentityModel"
                  :avatar-size="24"
                  :model="actorIdentityModel"
                  :meta="actorIdentityMeta"
                />
                <span v-else>-</span>
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

        <Card class="monitoring-card mt-4" :bordered="false">
          <template #title>
            <div class="monitoring-card__title">
              <IconifyIcon class="size-4" icon="lucide:workflow" />
              <span>{{ $t(`${i18nPrefix}.runtimeDiagnostics`) }}</span>
            </div>
          </template>

          <Empty
            v-if="!runtimeDiagnostics"
            :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
          />

          <template v-else>
            <div class="monitoring-diagnostics-summary">
              <article
                v-for="item in diagnosticsSummary"
                :key="item.key"
                class="monitoring-diagnostics-summary__item"
              >
                <div class="monitoring-overview-label">{{ item.label }}</div>
                <div class="monitoring-overview-value">{{ item.value }}</div>
              </article>
            </div>

            <div v-if="diagnosticsDetailRows.length > 0" class="mt-4">
              <div class="monitoring-card__subtitle">
                {{ $t(`${i18nPrefix}.diagnosticNotes`) }}
              </div>
              <div class="monitoring-overview-grid mt-3">
                <div
                  v-for="item in diagnosticsDetailRows"
                  :key="item.key"
                  class="monitoring-overview-item"
                >
                  <div class="monitoring-overview-label">{{ item.label }}</div>
                  <div class="monitoring-overview-value">{{ item.value }}</div>
                </div>
              </div>
            </div>

            <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
              <section class="monitoring-diagnostics-panel">
                <div class="monitoring-card__subtitle">
                  {{ $t(`${i18nPrefix}.intentPlan`) }}
                </div>
                <Empty
                  v-if="intentPlanItems.length === 0"
                  :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
                />
                <div v-else class="mt-3 space-y-3">
                  <article
                    v-for="(intent, index) in intentPlanItems"
                    :key="intent.id || intent.intent_id || `${index}`"
                    class="monitoring-diagnostics-intent"
                  >
                    <div class="monitoring-diagnostics-intent__head">
                      <Tag color="blue">
                        {{ formatTagValue(intent.kind || intent.label) }}
                      </Tag>
                      <Tag
                        v-if="intent.status"
                        :color="
                          intent.status === 'completed'
                            ? 'success'
                            : intent.status === 'failed'
                              ? 'error'
                              : 'processing'
                        "
                      >
                        {{ formatTagValue(intent.status) }}
                      </Tag>
                      <span
                        v-if="intent.intent_id"
                        class="text-xs text-muted-foreground"
                      >
                        {{ intent.intent_id }}
                      </span>
                    </div>
                    <div
                      v-if="
                        asStringArray(intent.required_capabilities).length >
                          0 ||
                        asStringArray(intent.allowed_tools).length > 0 ||
                        asStringArray(intent.selected_tools).length > 0 ||
                        asStringArray(intent.completed_tools).length > 0
                      "
                      class="mt-3 space-y-2"
                    >
                      <div
                        v-if="
                          asStringArray(intent.required_capabilities).length > 0
                        "
                        class="monitoring-diagnostics-line"
                      >
                        <span class="monitoring-overview-label">
                          {{ $t(`${i18nPrefix}.requiredCapabilities`) }}
                        </span>
                        <div class="monitoring-tag-list">
                          <Tag
                            v-for="capability in asStringArray(
                              intent.required_capabilities,
                            )"
                            :key="capability"
                            color="cyan"
                          >
                            {{ capability }}
                          </Tag>
                        </div>
                      </div>
                      <div
                        v-if="asStringArray(intent.allowed_tools).length > 0"
                        class="monitoring-diagnostics-line"
                      >
                        <span class="monitoring-overview-label">
                          {{ $t(`${i18nPrefix}.allowedTools`) }}
                        </span>
                        <div class="monitoring-tag-list">
                          <Tag
                            v-for="tool in asStringArray(intent.allowed_tools)"
                            :key="tool"
                            color="geekblue"
                          >
                            {{ tool }}
                          </Tag>
                        </div>
                      </div>
                      <div
                        v-if="asStringArray(intent.selected_tools).length > 0"
                        class="monitoring-diagnostics-line"
                      >
                        <span class="monitoring-overview-label">
                          {{ $t(`${i18nPrefix}.selectedTools`) }}
                        </span>
                        <div class="monitoring-tag-list">
                          <Tag
                            v-for="tool in asStringArray(intent.selected_tools)"
                            :key="tool"
                            color="processing"
                          >
                            {{ tool }}
                          </Tag>
                        </div>
                      </div>
                      <div
                        v-if="asStringArray(intent.completed_tools).length > 0"
                        class="monitoring-diagnostics-line"
                      >
                        <span class="monitoring-overview-label">
                          {{ $t(`${i18nPrefix}.completedTools`) }}
                        </span>
                        <div class="monitoring-tag-list">
                          <Tag
                            v-for="tool in asStringArray(
                              intent.completed_tools,
                            )"
                            :key="tool"
                            color="success"
                          >
                            {{ tool }}
                          </Tag>
                        </div>
                      </div>
                    </div>
                    <div
                      v-if="intent.unfinished_reason"
                      class="mt-3 text-xs text-muted-foreground"
                    >
                      {{ $t(`${i18nPrefix}.unfinishedReason`) }}:
                      {{ intent.unfinished_reason }}
                    </div>
                  </article>
                </div>
              </section>

              <section class="monitoring-diagnostics-panel">
                <div class="monitoring-card__subtitle">
                  {{ $t(`${i18nPrefix}.candidateTools`) }}
                </div>
                <div
                  v-if="candidateToolNames.length > 0"
                  class="monitoring-tag-list mt-3"
                >
                  <Tag
                    v-for="tool in candidateToolNames"
                    :key="tool"
                    color="purple"
                  >
                    {{ tool }}
                  </Tag>
                </div>
                <Empty
                  v-else
                  class="mt-3"
                  :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
                />

                <div class="monitoring-card__subtitle mt-5">
                  {{ $t(`${i18nPrefix}.providerEvents`) }}
                </div>
                <Empty
                  v-if="providerEvents.length === 0"
                  class="mt-3"
                  :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
                />
                <div v-else class="mt-3 space-y-3">
                  <article
                    v-for="(event, index) in providerEvents"
                    :key="`${event.kind || 'provider'}-${index}`"
                    class="monitoring-diagnostics-event"
                  >
                    <div class="monitoring-diagnostics-intent__head">
                      <Tag color="orange">
                        {{
                          formatTagValue(
                            event.kind || event.provider_failure_kind,
                          )
                        }}
                      </Tag>
                      <span
                        v-if="event.stage"
                        class="text-xs text-muted-foreground"
                      >
                        {{ event.stage }}
                      </span>
                    </div>
                    <pre class="monitoring-diagnostics-json">{{
                      prettyJson(event)
                    }}</pre>
                  </article>
                </div>

                <div class="monitoring-card__subtitle mt-5">
                  {{ $t(`${i18nPrefix}.retryEvents`) }}
                </div>
                <Empty
                  v-if="retryEvents.length === 0"
                  class="mt-3"
                  :description="$t(`${i18nPrefix}.diagnosticsEmpty`)"
                />
                <div v-else class="mt-3 space-y-3">
                  <article
                    v-for="(event, index) in retryEvents"
                    :key="`${event.kind || 'retry'}-${index}`"
                    class="monitoring-diagnostics-event"
                  >
                    <div class="monitoring-diagnostics-intent__head">
                      <Tag color="gold">
                        {{ formatTagValue(event.kind || event.reason) }}
                      </Tag>
                      <span
                        v-if="event.attempt != null"
                        class="text-xs text-muted-foreground"
                      >
                        #{{ event.attempt }}
                      </span>
                    </div>
                    <pre class="monitoring-diagnostics-json">{{
                      prettyJson(event)
                    }}</pre>
                  </article>
                </div>
              </section>
            </div>
          </template>
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
                    <Tooltip :title="formatDate(message.created_at)">
                      <span class="text-xs text-muted-foreground">
                        {{ formatTimeOnly(message.created_at) }}
                      </span>
                    </Tooltip>
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
  padding: 18px 20px 20px;
  background:
    radial-gradient(
      circle at right top,
      hsl(var(--primary) / 14%) 0%,
      transparent 52%
    ),
    linear-gradient(140deg, hsl(var(--background)) 0%, hsl(var(--card)) 60%);
  border: 1px solid hsl(var(--border) / 25%);
  border-radius: 16px;
  box-shadow:
    inset 0 1px 0 hsl(var(--background) / 70%),
    0 16px 24px hsl(var(--foreground) / 7%);
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
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
  color: hsl(var(--foreground) / 96%);
}

.monitoring-hero__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin-top: 8px;
}

.monitoring-hero__meta-item {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  color: hsl(var(--muted-foreground) / 96%);
}

.monitoring-hero__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(130px, 1fr));
  gap: 10px;
  min-width: 300px;
}

.monitoring-hero__stat {
  padding: 10px 12px;
  background: hsl(var(--background) / 72%);
  border: 1px solid hsl(var(--border) / 24%);
  border-radius: 12px;
}

.monitoring-hero__stat-label {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  color: hsl(var(--muted-foreground) / 95%);
}

.monitoring-hero__stat-value {
  margin-top: 4px;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 18px;
  font-weight: 700;
  color: hsl(var(--foreground) / 98%);
}

.monitoring-card {
  background: hsl(var(--card) / 80%);
  border: 1px solid hsl(var(--border) / 24%);
  border-radius: 14px;
  box-shadow: 0 10px 20px hsl(var(--foreground) / 5%);
}

.monitoring-card :deep(.ant-card-head) {
  min-height: 54px;
  padding: 0 16px;
  border-bottom: 1px solid hsl(var(--border) / 16%);
}

.monitoring-card :deep(.ant-card-head-title) {
  padding: 10px 0;
}

.monitoring-card :deep(.ant-card-body) {
  padding: 14px 16px 16px;
}

.monitoring-card__title {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-weight: 600;
}

.monitoring-card__subtitle {
  font-size: 13px;
  font-weight: 600;
  color: hsl(var(--foreground) / 98%);
}

.monitoring-overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.monitoring-overview-item {
  padding: 10px 12px;
  background: hsl(var(--background) / 88%);
  border: 1px solid hsl(var(--border) / 20%);
  border-radius: 10px;
}

.monitoring-overview-label {
  margin-bottom: 4px;
  font-size: 12px;
  color: hsl(var(--muted-foreground) / 98%);
}

.monitoring-overview-value {
  font-size: 13px;
  font-weight: 500;
  color: hsl(var(--foreground) / 98%);
}

.monitoring-diagnostics-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.monitoring-diagnostics-summary__item,
.monitoring-diagnostics-panel,
.monitoring-diagnostics-intent,
.monitoring-diagnostics-event {
  padding: 12px;
  background: hsl(var(--background) / 88%);
  border: 1px solid hsl(var(--border) / 20%);
  border-radius: 12px;
}

.monitoring-diagnostics-intent__head {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  align-items: center;
}

.monitoring-diagnostics-line {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.monitoring-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.monitoring-diagnostics-json {
  padding: 10px;
  margin-top: 10px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  color: hsl(var(--foreground) / 96%);
  white-space: pre-wrap;
  background: hsl(var(--accent) / 50%);
  border-radius: 10px;
}

.monitoring-scroll-area {
  max-height: 520px;
  padding-right: 4px;
  overflow-y: auto;
}

.monitoring-message-item,
.monitoring-trace-item {
  padding: 10px 12px;
  background: hsl(var(--accent) / 65%);
  border: 1px solid hsl(var(--border) / 20%);
  border-radius: 12px;
}

.monitoring-message-head,
.monitoring-trace-head {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  align-items: center;
}

.monitoring-message-content {
  padding: 8px 10px;
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.55;
  color: hsl(var(--foreground) / 98%);
  white-space: pre-wrap;
  background: hsl(var(--background) / 88%);
  border: 1px solid hsl(var(--border) / 18%);
  border-radius: 10px;
}

.monitoring-trace-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0 6px;
  align-items: center;
  margin-top: 6px;
  font-size: 12px;
  color: hsl(var(--muted-foreground) / 95%);
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
