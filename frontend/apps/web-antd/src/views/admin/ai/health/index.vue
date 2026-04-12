<script lang="ts" setup>
import type { AIHealthStatus } from '#/api/admin/ai';

/**
 * AI 供应商健康状态监控页面 — useCrudList + autoRefresh
 */
import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Card,
  Empty,
  InputNumber,
  Modal,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { getAIHealthStatusApi } from '#/api/admin/ai';
import {
  getAIRuntimeCapabilitiesApi,
  getAIRuntimeDoctorApi,
  runAIRuntimeSmokeApi,
} from '#/api/admin/ai-runtime';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAttachmentImageUrl } from '#/utils/image';

import AIGatewayQuickStartHero from '../_shared/AIGatewayQuickStartHero.vue';

defineOptions({ name: 'AIHealthMonitor' });

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
function getStatusColor(status: AIHealthStatus): string {
  if (status.is_healthy && status.is_available) return 'success';
  if (!status.is_healthy && status.is_available) return 'warning';
  return 'error';
}

function getStatusText(status: AIHealthStatus): string {
  if (status.is_healthy && status.is_available)
    return $t('admin.ai.health.status.healthy');
  if (!status.is_healthy && status.is_available)
    return $t('admin.ai.health.status.degraded');
  return $t('admin.ai.health.status.unavailable');
}

function getBadgeStatus(
  status: AIHealthStatus,
): 'error' | 'success' | 'warning' {
  return getStatusColor(status) as 'error' | 'success' | 'warning';
}

function getProbeBadgeStatus(
  passed: boolean | null | undefined,
): 'default' | 'error' | 'success' | 'warning' {
  if (passed === true) return 'success';
  if (passed === false) return 'error';
  return 'default';
}

function getProbeText(passed: boolean | null | undefined): string {
  if (passed === true) return $t('admin.ai.health.checks.pass');
  if (passed === false) return $t('admin.ai.health.checks.fail');
  return $t('admin.ai.health.checks.skipped');
}
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIGatewayQuickStartHero :current-title="$t('admin.ai.health.title')" />

    <section
      class="rounded-[20px] border border-border/70 bg-card px-4 py-3 shadow-sm"
    >
      <div
        class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
      >
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-700 dark:text-emerald-200"
          >
            <Badge status="success" />
            {{ healthyCount }} {{ $t('admin.ai.health.status.healthy') }}
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs text-amber-700 dark:text-amber-200"
          >
            <Badge status="warning" />
            {{ degradedCount }} {{ $t('admin.ai.health.status.degraded') }}
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-2.5 py-1 text-xs text-rose-700 dark:text-rose-200"
          >
            <Badge status="error" />
            {{ unavailableCount }}
            {{ $t('admin.ai.health.status.unavailable') }}
          </span>
          <span
            class="rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs text-muted-foreground"
          >
            <span class="mr-1 font-semibold text-foreground">
              {{ statuses.length }}
            </span>
            {{ $t('admin.ai.health.providers') }}
          </span>
        </div>
        <div class="flex flex-wrap items-center justify-end gap-2">
          <InputNumber
            v-model:value="runtimeAgentId"
            size="small"
            class="w-[140px]"
            :min="1"
            :placeholder="$t('admin.ai.health.agentIdPlaceholder')"
          />
          <Button
            v-access:code="['ai_runtime:list']"
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
            v-access:code="['ai_runtime:create']"
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
            size="small"
            :loading="runtimeLoading"
            @click="runRuntimeCapabilities"
          >
            <template #icon>
              <IconifyIcon icon="lucide:scan-search" class="size-3.5" />
            </template>
            {{ $t('admin.ai.health.runtimeCapabilities') }}
          </Button>
          <Button size="small" @click="loadHealth">
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
            </template>
            {{ $t('admin.ai.health.refresh') }}
          </Button>
        </div>
      </div>
    </section>

    <!-- 健康状态卡片网格 -->
    <Spin :spinning="loading">
      <div
        v-if="statuses.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <Card
          v-for="status in statuses"
          :key="status.provider_id"
          class="transition-shadow duration-200 hover:shadow-md"
          :body-style="{ padding: '20px' }"
        >
          <!-- 头部：供应商 + 状态 -->
          <div class="mb-4 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div
                class="flex size-10 items-center justify-center overflow-hidden rounded-lg"
                :class="
                  status.is_available ? 'bg-success/10' : 'bg-destructive/10'
                "
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
                  class="size-full object-contain"
                  alt=""
                />
                <IconifyIcon
                  v-else
                  icon="lucide:cpu"
                  class="size-5"
                  :class="
                    status.is_available ? 'text-success' : 'text-destructive'
                  "
                />
              </div>
              <div>
                <div class="font-medium text-foreground">
                  {{ status.provider_name }}
                </div>
                <code class="text-xs text-muted-foreground">{{
                  status.provider_code
                }}</code>
              </div>
            </div>
            <Badge
              :status="getBadgeStatus(status)"
              :text="getStatusText(status)"
            />
          </div>

          <!-- 指标 -->
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span class="text-muted-foreground">{{
                $t('admin.ai.health.responseTime')
              }}</span>
              <div class="mt-0.5 font-medium text-foreground">
                <span
                  :class="
                    status.response_time_ms > 5000
                      ? 'text-destructive'
                      : status.response_time_ms > 3000
                        ? 'text-warning'
                        : ''
                  "
                >
                  {{ status.response_time_ms }}ms
                </span>
              </div>
            </div>
            <div>
              <span class="text-muted-foreground">{{
                $t('admin.ai.health.failures')
              }}</span>
              <div class="mt-0.5 font-medium">
                <Tag v-if="status.consecutive_failures === 0" color="success">
                  0
                </Tag>
                <Tag
                  v-else
                  :color="
                    status.consecutive_failures >= 3 ? 'error' : 'warning'
                  "
                >
                  {{ status.consecutive_failures }}
                </Tag>
              </div>
            </div>
          </div>

          <div class="mt-4 space-y-2 border-t border-border/60 pt-3 text-xs">
            <div class="flex items-center justify-between gap-2">
              <span class="text-muted-foreground">{{
                $t('admin.ai.health.wireApi')
              }}</span>
              <Tag color="blue">{{ status.wire_api || '-' }}</Tag>
            </div>
            <div class="flex items-center justify-between gap-2">
              <span class="text-muted-foreground">{{
                $t('admin.ai.health.baseConnectivity')
              }}</span>
              <Tag
                :color="getProbeBadgeStatus(status.base_connectivity_healthy)"
              >
                {{ getProbeText(status.base_connectivity_healthy) }}
              </Tag>
            </div>
            <div class="flex items-center justify-between gap-2">
              <span class="text-muted-foreground">{{
                $t('admin.ai.health.toolProbe')
              }}</span>
              <Tag :color="getProbeBadgeStatus(status.tool_calling_healthy)">
                {{ getProbeText(status.tool_calling_healthy) }}
              </Tag>
            </div>
            <div
              v-if="
                status.tool_probe_model || status.tool_probe_reasoning_effort
              "
              class="flex flex-col gap-1"
            >
              <span class="text-muted-foreground">{{
                $t('admin.ai.health.toolProbeModel')
              }}</span>
              <code class="break-all text-foreground">
                {{ status.tool_probe_model || '-' }}
                <template v-if="status.tool_probe_reasoning_effort">
                  ({{ status.tool_probe_reasoning_effort }})
                </template>
              </code>
            </div>
          </div>

          <!-- 错误信息 -->
          <div v-if="status.error_message" class="mt-3">
            <Tooltip :title="status.error_message">
              <div
                class="line-clamp-1 rounded bg-destructive/5 px-2 py-1 text-xs text-destructive"
              >
                {{ status.error_message }}
              </div>
            </Tooltip>
          </div>

          <!-- 最后检查时间 -->
          <div class="mt-3 text-xs text-muted-foreground">
            {{ $t('admin.ai.health.lastCheck') }}:
            <Tooltip :title="formatDate(status.checked_at)">
              <span
                class="ml-1 inline-flex cursor-default rounded-md px-1 py-0.5 tabular-nums transition-colors hover:bg-muted/80"
              >
                {{ formatRelativeTime(status.checked_at) }}
              </span>
            </Tooltip>
          </div>
        </Card>
      </div>
      <Empty v-else class="py-16" :description="$t('admin.ai.health.noData')" />
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
  </Page>
</template>
