<script lang="ts" setup>
import type {
  AIHealthHistoryEntry,
  AIHealthStatus,
} from '#/api/admin/ai-providers';

/**
 * AI 供应商健康状态监控页面 — useCrudList + autoRefresh
 */
import { computed, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Empty,
  InputNumber,
  Modal,
  Spin,
  Tooltip,
} from 'ant-design-vue';

import {
  getAIHealthHistoryApi,
  getAIHealthStatusApi,
} from '#/api/admin/ai-providers';
import {
  getAIRuntimeCapabilitiesApi,
  getAIRuntimeDoctorApi,
  runAIRuntimeSmokeApi,
} from '#/api/admin/ai-runtime';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { getErrorMessage } from '#/utils/error-helpers';
import { toAttachmentImageUrl } from '#/utils/image';

defineOptions({ name: 'AIHealthMonitor' });

interface HealthHistoryDisplayPoint extends AIHealthHistoryEntry {
  isMissing?: boolean;
}

interface HealthHistoryState {
  errorMessage?: string;
  items: AIHealthHistoryEntry[];
  status: 'error' | 'loaded';
}

const HISTORY_SLOT_COUNT = 60;
const HISTORY_LOAD_TIMEOUT_MS = 12_000;

// ========== 声明式列表管理 + 30秒自动刷新 / Declarative list + 30s refresh ==========
const {
  list: statuses,
  loading,
  loadList: loadHealth,
} = useCrudList<AIHealthStatus>({
  api: {
    list: () =>
      getAIHealthStatusApi() as unknown as Promise<{
        items: AIHealthStatus[];
        total: number;
      }>,
    resource: '/admin/ai/health',
  },
  keyField: 'provider_id',
  i18nPrefix: 'admin.ai.health',
  pager: false,
  autoRefreshInterval: 30_000,
});

// ========== 概览计数 / Overview counts ==========
const healthyCount = computed(
  () => statuses.value.filter((s) => s.is_healthy && s.is_available).length,
);
const degradedCount = computed(
  () => statuses.value.filter((s) => !s.is_healthy && s.is_available).length,
);
const unavailableCount = computed(
  () => statuses.value.filter((s) => !s.is_available).length,
);

const healthHistoryMap = ref<Record<number, HealthHistoryState>>({});
const historyLoading = ref(false);
let historyLoadToken = 0;

const runtimeAgentId = ref<number>();
const runtimeLoading = ref(false);
const runtimeResultTitle = ref('');
const runtimeResultOpen = ref(false);
const runtimeResultPayload = ref<unknown>(null);

function openRuntimeResult(title: string, payload: unknown) {
  runtimeResultTitle.value = title;
  runtimeResultPayload.value = payload;
  runtimeResultOpen.value = true;
}

function getRuntimeAgentParams(): undefined | { agent_id: number } {
  return typeof runtimeAgentId.value === 'number'
    ? { agent_id: runtimeAgentId.value }
    : undefined;
}

async function runRuntimeDoctor() {
  runtimeLoading.value = true;
  try {
    const result = await getAIRuntimeDoctorApi(getRuntimeAgentParams());
    openRuntimeResult($t('admin.ai.health.runtimeDoctor'), result);
  } finally {
    runtimeLoading.value = false;
  }
}

async function runRuntimeSmoke() {
  runtimeLoading.value = true;
  try {
    const result = await runAIRuntimeSmokeApi(getRuntimeAgentParams());
    openRuntimeResult($t('admin.ai.health.runtimeSmoke'), result);
  } finally {
    runtimeLoading.value = false;
  }
}

async function runRuntimeCapabilities() {
  runtimeLoading.value = true;
  try {
    const result = await getAIRuntimeCapabilitiesApi(getRuntimeAgentParams());
    openRuntimeResult($t('admin.ai.health.runtimeCapabilities'), result);
  } finally {
    runtimeLoading.value = false;
  }
}

function prettyRuntimeResult(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

// ========== 辅助 / Helpers ==========
function getStatusText(status: AIHealthStatus): string {
  if (status.is_healthy && status.is_available)
    return $t('admin.ai.health.status.healthy');
  if (!status.is_healthy && status.is_available)
    return $t('admin.ai.health.status.degraded');
  return $t('admin.ai.health.status.unavailable');
}

function getStatusPillClass(status: AIHealthStatus): string {
  if (status.is_healthy && status.is_available) {
    return 'border-emerald-300 bg-emerald-500/10 text-emerald-700 dark:border-emerald-400/25 dark:text-emerald-200';
  }
  if (!status.is_healthy && status.is_available) {
    return 'border-amber-300 bg-amber-500/10 text-amber-700 dark:border-amber-400/25 dark:text-amber-200';
  }
  return 'border-rose-300 bg-rose-500/10 text-rose-700 dark:border-rose-400/25 dark:text-rose-200';
}

function getStatusAccentClass(status: AIHealthStatus): string {
  if (status.is_healthy && status.is_available) {
    return 'text-emerald-600 dark:text-emerald-300';
  }
  if (!status.is_healthy && status.is_available) {
    return 'text-amber-600 dark:text-amber-300';
  }
  return 'text-rose-600 dark:text-rose-300';
}

function getProviderHistoryState(
  status: AIHealthStatus,
): HealthHistoryState | undefined {
  return healthHistoryMap.value[status.provider_id];
}

function getProviderHistoryLoadState(
  status: AIHealthStatus,
): 'error' | 'loaded' | 'unknown' {
  return getProviderHistoryState(status)?.status ?? 'unknown';
}

function getProviderHistory(status: AIHealthStatus): AIHealthHistoryEntry[] {
  const history = getProviderHistoryState(status)?.items ?? [];
  return history
    .toSorted((left, right) => {
      const parsedLeftTime = left.checked_at ? Date.parse(left.checked_at) : 0;
      const parsedRightTime = right.checked_at
        ? Date.parse(right.checked_at)
        : 0;
      const leftTime = Number.isFinite(parsedLeftTime) ? parsedLeftTime : 0;
      const rightTime = Number.isFinite(parsedRightTime) ? parsedRightTime : 0;
      return leftTime - rightTime;
    })
    .slice(-HISTORY_SLOT_COUNT);
}

function getHistoryDisplayPoints(
  status: AIHealthStatus,
): HealthHistoryDisplayPoint[] {
  const history = getProviderHistory(status).slice(-HISTORY_SLOT_COUNT);
  const missingCount = Math.max(HISTORY_SLOT_COUNT - history.length, 0);
  const missingPoints = Array.from<unknown, HealthHistoryDisplayPoint>(
    { length: missingCount },
    () => ({ isMissing: true }),
  );
  return [...missingPoints, ...history];
}

function getHistorySuccessCount(status: AIHealthStatus): number {
  return getProviderHistory(status).filter((item) => item.is_healthy === true)
    .length;
}

function getHistoryAvailabilityLabel(status: AIHealthStatus): string {
  const history = getProviderHistory(status);
  if (
    getProviderHistoryLoadState(status) !== 'loaded' ||
    history.length === 0
  ) {
    return '--';
  }
  return `${((getHistorySuccessCount(status) / history.length) * 100).toFixed(
    2,
  )}%`;
}

function getHistorySuccessSummary(status: AIHealthStatus): string {
  const history = getProviderHistory(status);
  if (getProviderHistoryLoadState(status) === 'error') {
    return $t('admin.ai.health.historyLoadFailed');
  }
  if (history.length === 0) {
    return $t('admin.ai.health.noSample');
  }
  return `${getHistorySuccessCount(status)}/${history.length} ${$t(
    'admin.ai.health.success',
  )}`;
}

function getHistoryPointClass(point: HealthHistoryDisplayPoint): string {
  if (point.isMissing) return 'bg-muted-foreground/20 dark:bg-white/15';
  if (point.is_healthy === true) return 'bg-emerald-500';
  if (
    point.is_available === false ||
    point.base_connectivity_healthy === false
  ) {
    return 'bg-rose-600';
  }
  return 'bg-amber-400';
}

function getHistoryPointStatusText(point: HealthHistoryDisplayPoint): string {
  if (point.isMissing) return $t('admin.ai.health.noSample');
  if (point.is_healthy === true) return $t('admin.ai.health.status.healthy');
  if (
    point.is_available === false ||
    point.base_connectivity_healthy === false
  ) {
    return $t('admin.ai.health.status.unavailable');
  }
  return $t('admin.ai.health.status.degraded');
}

function getHistoryPointTooltip(point: HealthHistoryDisplayPoint): string {
  if (point.isMissing) return $t('admin.ai.health.noSample');
  const checkedAt = point.checked_at ? formatDate(point.checked_at) : '-';
  const responseTime =
    typeof point.response_time_ms === 'number'
      ? `${point.response_time_ms} ms`
      : '-';
  return `${checkedAt} · ${getHistoryPointStatusText(point)} · ${responseTime}`;
}

function getHistoryErrorMessage(status: AIHealthStatus): string {
  return (
    getProviderHistoryState(status)?.errorMessage ??
    $t('admin.ai.health.historyLoadFailed')
  );
}

async function loadProviderHistory(
  providerId: number,
): Promise<AIHealthHistoryEntry[]> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const timeoutPromise = new Promise<AIHealthHistoryEntry[]>((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error($t('admin.ai.health.historyTimeout')));
    }, HISTORY_LOAD_TIMEOUT_MS);
  });
  try {
    return await Promise.race([
      getAIHealthHistoryApi(
        providerId,
        { limit: HISTORY_SLOT_COUNT },
        {
          showCodeMessage: false,
          showErrorMessage: false,
        },
      ),
      timeoutPromise,
    ]);
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

async function loadHealthHistory(items: AIHealthStatus[]) {
  const currentToken = ++historyLoadToken;
  if (items.length === 0) {
    healthHistoryMap.value = {};
    historyLoading.value = false;
    return;
  }
  historyLoading.value = true;
  try {
    const entries = await Promise.all(
      items.map(async (item) => {
        try {
          const history = await loadProviderHistory(item.provider_id);
          return [
            item.provider_id,
            { items: history, status: 'loaded' },
          ] as const;
        } catch (error) {
          return [
            item.provider_id,
            {
              errorMessage: getErrorMessage(
                error,
                'admin.ai.health.historyLoadFailed',
              ),
              items: [],
              status: 'error',
            },
          ] as const;
        }
      }),
    );
    if (currentToken !== historyLoadToken) return;
    healthHistoryMap.value = Object.fromEntries(entries);
  } finally {
    if (currentToken === historyLoadToken) {
      historyLoading.value = false;
    }
  }
}

watch(
  statuses,
  (items) => {
    void loadHealthHistory(items);
  },
  { immediate: true },
);
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <div data-testid="admin-ai-health-page" class="flex flex-col gap-4">
      <section
        data-testid="health-runtime-actions"
        class="rounded-lg border border-border/70 bg-card/90 px-4 py-3 shadow-sm dark:border-white/[0.08]"
      >
        <div
          class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"
        >
          <div>
            <h2 class="text-lg font-semibold text-foreground">
              {{ $t('admin.ai.health.title') }}
            </h2>
            <div class="mt-1 flex flex-wrap items-center gap-3 text-sm">
              <span class="text-muted-foreground">
                {{ statuses.length }}
                {{ $t('admin.ai.health.monitoringItems') }}
              </span>
              <span class="inline-flex items-center gap-1 text-emerald-600">
                <Badge status="success" />
                {{ healthyCount }}
              </span>
              <span class="inline-flex items-center gap-1 text-amber-600">
                <Badge status="warning" />
                {{ degradedCount }}
              </span>
              <span class="inline-flex items-center gap-1 text-rose-600">
                <Badge status="error" />
                {{ unavailableCount }}
              </span>
            </div>
          </div>
          <div class="flex flex-wrap items-center justify-end gap-2">
            <InputNumber
              v-model:value="runtimeAgentId"
              data-testid="runtime-agent-id"
              size="small"
              class="w-[140px]"
              :min="1"
              :placeholder="$t('admin.ai.health.agentIdPlaceholder')"
            />
            <Button
              v-access:code="['ai_runtime:list']"
              data-testid="runtime-doctor"
              size="small"
              :loading="runtimeLoading"
              @click="runRuntimeDoctor"
            >
              <template #icon>
                <IconifyIcon icon="lucide:stethoscope" class="size-3.5" />
              </template>
              {{ $t('admin.ai.health.runtimeDoctor') }}
            </Button>
            <Button
              v-access:code="['ai_runtime:list']"
              data-testid="runtime-smoke"
              size="small"
              :loading="runtimeLoading"
              @click="runRuntimeSmoke"
            >
              <template #icon>
                <IconifyIcon icon="lucide:flame" class="size-3.5" />
              </template>
              {{ $t('admin.ai.health.runtimeSmoke') }}
            </Button>
            <Button
              v-access:code="['ai_runtime:list']"
              data-testid="runtime-capabilities"
              size="small"
              :loading="runtimeLoading"
              @click="runRuntimeCapabilities"
            >
              <template #icon>
                <IconifyIcon icon="lucide:scan-search" class="size-3.5" />
              </template>
              {{ $t('admin.ai.health.runtimeCapabilities') }}
            </Button>
            <Button
              data-testid="health-refresh"
              size="small"
              @click="loadHealth"
            >
              <template #icon>
                <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
              </template>
              {{ $t('admin.ai.health.refresh') }}
            </Button>
          </div>
        </div>
      </section>

      <Spin :spinning="loading || historyLoading">
        <div
          v-if="statuses.length > 0"
          data-testid="health-provider-cards"
          class="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3"
        >
          <article
            v-for="status in statuses"
            :key="status.provider_id"
            data-testid="health-provider-card"
            class="overflow-hidden rounded-lg border border-border/70 bg-gradient-to-br from-background via-background to-muted/30 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/20 hover:shadow-md dark:border-white/[0.08] dark:from-card dark:via-card dark:to-primary/[0.04]"
          >
            <div class="space-y-2.5 px-3 py-3">
              <div class="flex items-start justify-between gap-3">
                <div class="flex min-w-0 items-center gap-2.5">
                  <div
                    class="flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border/70 bg-background/90 text-foreground dark:border-white/[0.08]"
                  >
                    <img
                      v-if="
                        toAttachmentImageUrl(status.provider_icon, {
                          preset: 'small',
                        })
                      "
                      :src="
                        toAttachmentImageUrl(status.provider_icon, {
                          preset: 'small',
                        })
                      "
                      class="size-full object-contain p-1.5"
                      alt=""
                    />
                    <IconifyIcon v-else icon="lucide:activity" class="size-5" />
                  </div>
                  <div class="min-w-0">
                    <h3
                      class="truncate text-base font-semibold leading-5 text-foreground"
                      :title="status.provider_name"
                    >
                      {{ status.provider_name }}
                    </h3>
                    <div
                      class="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground"
                    >
                      <span
                        class="inline-flex items-center rounded-full border border-border/70 bg-background/80 px-2 py-0.5 font-semibold text-foreground dark:border-white/[0.08]"
                      >
                        {{ $t('admin.ai.health.serviceLayer') }}
                      </span>
                      <span class="truncate">{{ status.provider_code }}</span>
                    </div>
                  </div>
                </div>
                <span
                  class="shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold"
                  :class="getStatusPillClass(status)"
                >
                  {{ getStatusText(status) }}
                </span>
              </div>

              <div class="grid gap-2 sm:grid-cols-2">
                <div
                  class="rounded-md border border-border/70 bg-background/80 px-2.5 py-2 dark:border-white/[0.08] dark:bg-background/40"
                >
                  <div
                    class="flex items-center gap-1.5 text-[11px] uppercase text-muted-foreground"
                  >
                    <IconifyIcon icon="lucide:waves" class="size-3.5" />
                    {{ $t('admin.ai.health.ttfb') }}
                  </div>
                  <div class="mt-1 text-lg font-semibold text-foreground">
                    {{ status.response_time_ms }} ms
                  </div>
                </div>
                <div
                  class="rounded-md border border-border/70 bg-background/80 px-2.5 py-2 dark:border-white/[0.08] dark:bg-background/40"
                >
                  <div
                    class="flex items-center gap-1.5 text-[11px] uppercase text-muted-foreground"
                  >
                    <IconifyIcon icon="lucide:clock-3" class="size-3.5" />
                    {{ $t('admin.ai.health.latest') }}
                  </div>
                  <div
                    class="mt-1.5 text-xs font-semibold text-foreground sm:text-sm"
                  >
                    {{ formatDate(status.checked_at) }}
                  </div>
                </div>
              </div>

              <div class="flex items-end justify-between gap-4">
                <div>
                  <div class="text-[11px] uppercase text-muted-foreground">
                    {{ $t('admin.ai.health.availabilityOneHour') }}
                  </div>
                  <div
                    data-testid="health-availability"
                    class="mt-0.5 text-lg font-semibold"
                    :class="getStatusAccentClass(status)"
                  >
                    {{ getHistoryAvailabilityLabel(status) }}
                  </div>
                  <div
                    data-testid="health-success-summary"
                    class="text-[11px] text-muted-foreground"
                  >
                    {{ getHistorySuccessSummary(status) }}
                  </div>
                </div>
                <div
                  class="text-right text-[11px] uppercase text-muted-foreground"
                >
                  {{
                    $t('admin.ai.health.history', {
                      count: HISTORY_SLOT_COUNT,
                    })
                  }}
                </div>
              </div>

              <div class="space-y-1">
                <div
                  class="flex items-center justify-between text-[11px] uppercase text-muted-foreground"
                >
                  <span>{{ $t('admin.ai.health.historyPast') }}</span>
                  <span>{{ $t('admin.ai.health.historyNow') }}</span>
                </div>
                <div
                  v-if="getProviderHistoryLoadState(status) === 'loaded'"
                  data-testid="health-history-chart"
                  class="grid grid-cols-[repeat(60,minmax(1px,1fr))] items-end gap-[2px] rounded-md border border-border/50 bg-background/70 px-2 py-2 dark:border-white/[0.08] dark:bg-background/35"
                >
                  <Tooltip
                    v-for="(point, index) in getHistoryDisplayPoints(status)"
                    :key="`${status.provider_id}-${point.checked_at || index}`"
                    :title="getHistoryPointTooltip(point)"
                  >
                    <span
                      data-testid="health-history-point"
                      class="h-8 min-w-0 rounded-[2px]"
                      :class="getHistoryPointClass(point)"
                    ></span>
                  </Tooltip>
                </div>
                <div
                  v-else-if="getProviderHistoryLoadState(status) === 'error'"
                  data-testid="health-history-error"
                  class="flex items-start gap-2 rounded-md border border-rose-500/25 bg-rose-500/5 px-2.5 py-2 text-xs text-rose-600 dark:text-rose-300"
                >
                  <IconifyIcon
                    icon="lucide:triangle-alert"
                    class="mt-0.5 size-3.5 shrink-0"
                  />
                  <span class="line-clamp-2">{{
                    getHistoryErrorMessage(status)
                  }}</span>
                </div>
              </div>

              <Tooltip
                v-if="status.error_message"
                :title="status.error_message"
              >
                <div
                  class="line-clamp-1 rounded-lg border border-rose-500/20 bg-rose-500/5 px-2.5 py-1 text-xs text-rose-600 dark:text-rose-300"
                >
                  {{ status.error_message }}
                </div>
              </Tooltip>
            </div>
          </article>
        </div>
        <Empty
          v-else
          data-testid="health-empty-state"
          class="py-16"
          :description="$t('admin.ai.health.noData')"
        />
      </Spin>

      <Modal
        v-model:open="runtimeResultOpen"
        :title="runtimeResultTitle"
        :footer="null"
        width="920px"
        destroy-on-close
      >
        <pre
          class="max-h-[560px] overflow-auto rounded-lg border border-border/60 bg-accent/20 p-3 font-mono text-xs leading-5"
          >{{ prettyRuntimeResult(runtimeResultPayload) }}</pre
        >
      </Modal>
    </div>
  </Page>
</template>
