<script lang="ts" setup>
import type { MonitoringCallLogInfo, MonitoringScope } from '../api';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Drawer, Empty, Spin, Tag } from 'ant-design-vue';

import { getAIRuntimeRootCauseApi } from '#/api/admin/ai-runtime';
import { IdentitySummaryCard } from '#/components/business/identity-display';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import { getMonitoringCallLogDetail } from '../api';
import {
  createMonitoringCallerDetailMeta,
  createMonitoringCallerIdentityModel,
} from '../identity';

const props = defineProps<{
  i18nPrefix: string;
  logId: null | number;
  open: boolean;
  scope: MonitoringScope;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const loading = ref(false);
const detail = ref<MonitoringCallLogInfo | null>(null);
const rootCauseLoading = ref(false);
const rootCausePayload = ref<null | Record<string, unknown>>(null);

watch(
  () => [props.open, props.logId] as const,
  async ([open, id]) => {
    if (!open || !id) {
      detail.value = null;
      rootCausePayload.value = null;
      return;
    }
    loading.value = true;
    try {
      detail.value = await getMonitoringCallLogDetail(props.scope, id);
      await loadRootCause();
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

async function loadRootCause() {
  if (props.scope !== 'admin' || !props.logId) {
    rootCausePayload.value = null;
    return;
  }
  rootCauseLoading.value = true;
  try {
    rootCausePayload.value = (await getAIRuntimeRootCauseApi({
      call_log_id: props.logId,
      trace_id: detail.value?.trace_id || undefined,
    })) as Record<string, unknown>;
  } catch {
    rootCausePayload.value = null;
  } finally {
    rootCauseLoading.value = false;
  }
}

function closeDrawer() {
  emits('update:open', false);
}

function pretty(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function formatCost(cost?: null | number) {
  return `$${Number(cost || 0).toFixed(4)}`;
}

function formatTokens(tokens?: null | number) {
  return Number(tokens || 0).toLocaleString();
}

function formatLatency(latency?: null | number) {
  return latency === null || latency === undefined ? '-' : `${latency} ms`;
}

function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

function getInitialLetter(value: null | string | undefined): string {
  const text = String(value || '').trim();
  return text ? text.charAt(0).toUpperCase() : '?';
}

const detailAgentName = computed(() => detail.value?.agent_name || '-');
const callerIdentityModel = computed(() =>
  detail.value ? createMonitoringCallerIdentityModel(detail.value) : null,
);

const callerContextLabel = computed(() => $t(`${props.i18nPrefix}.callerName`));

function getStatusColor(status?: null | string) {
  switch (status) {
    case 'failed': {
      return 'error';
    }
    case 'success': {
      return 'success';
    }
    case 'timeout': {
      return 'warning';
    }
    default: {
      return 'default';
    }
  }
}

const drawerTitle = computed(() =>
  props.scope === 'admin'
    ? $t('admin.ai.callLog.detail.title')
    : $t('tenant.ai.callLog.detailTitle'),
);

const summaryDescription = computed(() => $t(`${props.i18nPrefix}.pageDesc`));

const requestDataLabel = computed(() =>
  props.scope === 'admin'
    ? $t('admin.ai.callLog.detail.requestData')
    : $t(`${props.i18nPrefix}.requestData`),
);

const responseDataLabel = computed(() =>
  props.scope === 'admin'
    ? $t('admin.ai.callLog.detail.responseData')
    : $t(`${props.i18nPrefix}.responseData`),
);

const statusText = computed(() => {
  const status = detail.value?.status;
  if (!status) {
    return '-';
  }
  const statusOptionKey = `${props.i18nPrefix}.status_options.${status}`;
  const translated = $t(statusOptionKey);
  return translated === statusOptionKey ? status : translated;
});

const summaryChips = computed(() => {
  if (!detail.value) {
    return [];
  }
  return [
    {
      key: 'model',
      label: $t(`${props.i18nPrefix}.modelName`),
      value: detail.value.model_name || '-',
    },
    {
      key: 'provider',
      label: $t(`${props.i18nPrefix}.providerName`),
      value: detail.value.provider_name || '-',
    },
    {
      key: 'requestType',
      label: $t(`${props.i18nPrefix}.requestType`),
      value: detail.value.request_type || '-',
    },
  ];
});

const metricCards = computed(() => {
  if (!detail.value) {
    return [];
  }
  return [
    {
      key: 'inputTokens',
      icon: 'lucide:arrow-down-to-line',
      label: $t(`${props.i18nPrefix}.inputTokens`),
      value: formatTokens(detail.value.input_tokens),
    },
    {
      key: 'outputTokens',
      icon: 'lucide:arrow-up-from-line',
      label: $t(`${props.i18nPrefix}.outputTokens`),
      value: formatTokens(detail.value.output_tokens),
    },
    {
      key: 'totalTokens',
      icon: 'lucide:binary',
      label: $t(`${props.i18nPrefix}.totalTokens`),
      value: formatTokens(detail.value.total_tokens),
    },
    {
      key: 'cost',
      icon: 'lucide:badge-dollar-sign',
      label: $t(`${props.i18nPrefix}.cost`),
      value: formatCost(detail.value.cost),
    },
    {
      key: 'latency',
      icon: 'lucide:gauge',
      label: $t(`${props.i18nPrefix}.latency`),
      value: formatLatency(detail.value.latency_ms),
    },
  ];
});

const detailFields = computed(() => {
  if (!detail.value) {
    return [];
  }
  const fields = [
    {
      key: 'createdAt',
      label: $t(`${props.i18nPrefix}.createdAt`),
      value: formatDate(detail.value.created_at),
    },
    {
      key: 'requestType',
      label: $t(`${props.i18nPrefix}.requestType`),
      value: detail.value.request_type || '-',
    },
    {
      key: 'modelName',
      label: $t(`${props.i18nPrefix}.modelName`),
      value: detail.value.model_name || '-',
    },
    {
      key: 'providerName',
      label: $t(`${props.i18nPrefix}.providerName`),
      value: detail.value.provider_name || '-',
    },
    {
      key: 'status',
      label: $t(`${props.i18nPrefix}.status`),
      value: statusText.value,
    },
  ];
  if (props.scope === 'admin') {
    fields.push({
      key: 'tenantName',
      label: $t(`${props.i18nPrefix}.tenantName`),
      value: detail.value.tenant_name || '-',
    });
  }
  return fields;
});

function buildDrawerCallerMeta(data: MonitoringCallLogInfo | null) {
  if (!data) {
    return {};
  }

  return createMonitoringCallerDetailMeta(data, {
    createdAt: data.created_at,
    scope: props.scope,
    tenantId: data.tenant_id,
    tenantName: data.tenant_name,
  });
}
</script>

<template>
  <Drawer :open="open" :title="drawerTitle" width="860" @close="closeDrawer">
    <Spin :spinning="loading">
      <template v-if="detail">
        <section
          class="rounded-[20px] border border-border/70 bg-gradient-to-br from-primary/10 via-background to-background px-5 py-4 shadow-sm"
        >
          <div
            class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between"
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class="flex size-9 items-center justify-center rounded-xl bg-primary/15 text-primary"
                >
                  <IconifyIcon icon="lucide:radar" class="size-5" />
                </span>
                <h3 class="text-base font-semibold text-foreground">
                  {{ drawerTitle }}
                </h3>
              </div>
              <p class="mt-2 text-xs leading-5 text-muted-foreground">
                {{ summaryDescription }}
              </p>

              <div class="mt-3 flex flex-wrap gap-2">
                <span
                  class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-2 py-1 text-xs"
                >
                  <span
                    class="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10 text-primary"
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
                  <span class="max-w-[180px] truncate text-foreground">
                    {{ detailAgentName }}
                  </span>
                </span>
                <span
                  class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-3 py-1 text-xs"
                >
                  <span class="font-mono text-foreground"
                    >#{{ detail.id }}</span
                  >
                </span>
                <div
                  class="inline-flex items-center rounded-2xl border border-border/70 bg-background/90 px-2 py-1"
                >
                  <span class="mr-2 text-xs text-muted-foreground">{{
                    $t(`${i18nPrefix}.callerName`)
                  }}</span>
                  <IdentityTrigger
                    v-if="callerIdentityModel"
                    :avatar-size="28"
                    :model="callerIdentityModel"
                    :meta="buildDrawerCallerMeta(detail)"
                    :context="callerContextLabel"
                    :show-status-badge="false"
                  />
                </div>
                <span
                  v-for="chip in summaryChips"
                  :key="chip.key"
                  class="inline-flex max-w-full items-center gap-2 rounded-full border border-border/70 bg-background/90 px-3 py-1 text-xs"
                >
                  <span class="text-muted-foreground">{{ chip.label }}</span>
                  <span class="max-w-[220px] truncate text-foreground">
                    {{ chip.value }}
                  </span>
                </span>
              </div>
            </div>

            <div class="flex flex-col items-start gap-2 xl:items-end">
              <Tag :color="getStatusColor(detail.status)">
                {{ statusText }}
              </Tag>
              <div
                class="rounded-xl border border-border/70 bg-card/90 px-3 py-2"
              >
                <div class="text-[11px] text-muted-foreground">
                  {{ $t(`${i18nPrefix}.createdAt`) }}
                </div>
                <div class="mt-1 text-xs font-medium text-foreground">
                  {{ formatDate(detail.created_at) }}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5"
        >
          <article
            v-for="metric in metricCards"
            :key="metric.key"
            class="rounded-2xl border border-border/70 bg-card px-4 py-3 shadow-sm"
          >
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <IconifyIcon :icon="metric.icon" class="size-4" />
              <span>{{ metric.label }}</span>
            </div>
            <div class="mt-2 text-lg font-semibold text-foreground">
              {{ metric.value }}
            </div>
          </article>
        </section>

        <section
          class="mt-4 rounded-2xl border border-border/70 bg-card px-4 py-4 shadow-sm"
        >
          <div
            class="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground"
          >
            <IconifyIcon icon="lucide:list-tree" class="size-4 text-primary" />
            <span>{{ drawerTitle }}</span>
          </div>

          <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div
              class="rounded-xl border border-border/60 bg-background/70 px-3 py-3"
            >
              <div class="text-xs text-muted-foreground">
                {{ $t(`${i18nPrefix}.agentName`) }}
              </div>
              <div class="mt-2 flex items-center gap-3">
                <div
                  class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-primary/10 text-primary"
                >
                  <img
                    v-if="
                      detail.agent_avatar && !isIconAvatar(detail.agent_avatar)
                    "
                    :alt="detailAgentName"
                    :src="toAvatarDisplayUrl(detail.agent_avatar)"
                    class="size-full object-cover"
                  />
                  <IconifyIcon
                    v-else-if="isIconAvatar(detail.agent_avatar)"
                    :icon="String(detail.agent_avatar)"
                    class="size-5"
                  />
                  <span v-else class="text-sm font-semibold">
                    {{ getInitialLetter(detailAgentName) }}
                  </span>
                </div>
                <div class="min-w-0">
                  <div class="truncate text-sm font-semibold text-foreground">
                    {{ detailAgentName }}
                  </div>
                  <div
                    v-if="detail.conversation_id"
                    class="text-xs text-muted-foreground"
                  >
                    #{{ detail.conversation_id }}
                  </div>
                </div>
              </div>
            </div>
            <IdentityTrigger
              v-if="callerIdentityModel"
              :model="callerIdentityModel"
              :meta="buildDrawerCallerMeta(detail)"
              :context="callerContextLabel"
            >
              <template #default="{ detailRequest }">
                <IdentitySummaryCard
                  :detail-request="detailRequest"
                  :model="callerIdentityModel"
                  mode="embedded"
                />
              </template>
            </IdentityTrigger>
            <div
              v-else
              class="rounded-xl border border-border/60 bg-background/70 px-3 py-3"
            >
              <div class="text-xs text-muted-foreground">
                {{ $t(`${i18nPrefix}.callerName`) }}
              </div>
              <div class="mt-2 text-sm text-muted-foreground">-</div>
            </div>
          </div>

          <div class="grid grid-cols-1 gap-x-4 gap-y-3 md:grid-cols-2">
            <div
              v-for="field in detailFields"
              :key="field.key"
              class="rounded-xl border border-border/60 bg-background/70 px-3 py-2"
            >
              <div class="text-xs text-muted-foreground">{{ field.label }}</div>
              <div class="mt-1 break-all text-sm font-medium text-foreground">
                {{ field.value }}
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="scope === 'admin'"
          class="mt-4 rounded-2xl border border-border/70 bg-card px-4 py-4 shadow-sm"
        >
          <div class="mb-2 flex items-center justify-between gap-2">
            <div
              class="flex items-center gap-2 text-sm font-semibold text-foreground"
            >
              <IconifyIcon
                icon="lucide:search-check"
                class="size-4 text-primary"
              />
              <span>Root Cause</span>
            </div>
            <button
              class="rounded-md border border-border/60 px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground"
              @click="loadRootCause"
            >
              Refresh
            </button>
          </div>
          <div
            v-if="rootCauseLoading"
            class="py-3 text-xs text-muted-foreground"
          >
            Loading root cause...
          </div>
          <template v-else-if="rootCausePayload">
            <div class="mb-2 grid grid-cols-1 gap-2 md:grid-cols-3">
              <div
                class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
              >
                <div class="text-[11px] text-muted-foreground">Status</div>
                <div class="mt-1 text-sm font-medium text-foreground">
                  {{ String(rootCausePayload.status || '-') }}
                </div>
              </div>
              <div
                class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
              >
                <div class="text-[11px] text-muted-foreground">
                  Failure Layer
                </div>
                <div class="mt-1 text-sm font-medium text-foreground">
                  {{ String(rootCausePayload.failure_layer || '-') }}
                </div>
              </div>
              <div
                class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
              >
                <div class="text-[11px] text-muted-foreground">Cause Code</div>
                <div class="mt-1 text-sm font-medium text-foreground">
                  {{ String(rootCausePayload.cause_code || '-') }}
                </div>
              </div>
            </div>
            <pre
              class="max-h-72 overflow-auto rounded-xl border border-border/60 bg-accent/30 p-3 font-mono text-xs leading-5"
              >{{ pretty(rootCausePayload) }}</pre
            >
          </template>
          <div v-else class="py-3 text-xs text-muted-foreground">
            Root cause report is unavailable for this call log.
          </div>
        </section>

        <section
          v-if="detail.error_message"
          class="mt-4 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-4 shadow-sm"
        >
          <div
            class="mb-2 flex items-center gap-2 text-sm font-semibold text-destructive"
          >
            <IconifyIcon icon="lucide:triangle-alert" class="size-4" />
            <span>{{ $t(`${i18nPrefix}.errorMessage`) }}</span>
          </div>
          <pre
            class="max-h-56 overflow-auto whitespace-pre-wrap rounded-xl border border-destructive/30 bg-background/80 p-3 font-mono text-xs leading-5 text-destructive"
            >{{ detail.error_message }}</pre
          >
        </section>

        <section class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <article
            class="rounded-2xl border border-border/70 bg-card p-4 shadow-sm"
          >
            <div
              class="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground"
            >
              <IconifyIcon
                icon="lucide:arrow-up-right"
                class="size-4 text-primary"
              />
              <span>{{ requestDataLabel }}</span>
            </div>
            <pre
              class="max-h-96 overflow-auto rounded-xl border border-border/60 bg-accent/30 p-3 font-mono text-xs leading-5"
              >{{ pretty(detail.request_data) }}</pre
            >
          </article>

          <article
            class="rounded-2xl border border-border/70 bg-card p-4 shadow-sm"
          >
            <div
              class="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground"
            >
              <IconifyIcon
                icon="lucide:arrow-down-left"
                class="size-4 text-primary"
              />
              <span>{{ responseDataLabel }}</span>
            </div>
            <pre
              class="max-h-96 overflow-auto rounded-xl border border-border/60 bg-accent/30 p-3 font-mono text-xs leading-5"
              >{{ pretty(detail.response_data) }}</pre
            >
          </article>
        </section>
      </template>
      <Empty v-else class="py-16" />
    </Spin>
  </Drawer>
</template>
