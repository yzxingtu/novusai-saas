<script lang="ts" setup>
/**
 * 企业端 AI 操作审计日志列表页面 / Tenant AI action audit log list page
 *
 * 包含统计卡片 + 操作列表
 */
import type {
  ActionLogDetail,
  ActionLogItem,
  ActionLogStats,
} from '#/api/tenant/action-logs';
import type { ExecutionDecisionItem } from '#/api/tenant/execution-decisions';

import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Avatar,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  message,
  Skeleton,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getActionLogDetailApi,
  getActionLogListApi,
  getActionLogStatsApi,
} from '#/api/tenant/action-logs';
import { getExecutionDecisionDetailApi } from '#/api/tenant/execution-decisions';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import {
  createRefreshPageOperation,
  createViewDetailPageOperation,
} from '#/composables';
import { $t } from '#/locales';
import {
  copyToClipboard,
  formatDate,
  formatRelativeTime,
} from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import {
  getExecutionDecisionStatusText,
  getExecutionDecisionTypeText,
  getLevelColor,
  getLevelText,
  getStatusColor,
  getStatusText,
  getTypeColor,
  getTypeText,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'TenantAIActionLogList' });

type DetailTabKey = 'error' | 'overview' | 'request' | 'response';
type PayloadEntryKind = 'json' | 'scalar';

interface PayloadEntry {
  key: string;
  kind: PayloadEntryKind;
  valueText: string;
}

interface OperatorIdentitySource {
  operator_avatar?: null | string;
  operator_display_name?: null | string;
  operator_id?: null | number;
  operator_is_active?: boolean;
  operator_is_leader?: boolean;
  operator_is_owner?: boolean;
  operator_name?: null | string;
  operator_nickname?: null | string;
  operator_org_node_name?: null | string;
  operator_role_name?: null | string;
  operator_type?: null | string;
}

function getAgentDisplayName(
  log: Pick<ActionLogDetail, 'agent_id' | 'agent_name'>,
): string {
  if (log.agent_name) {
    return log.agent_name;
  }
  if (log.agent_id && log.agent_id > 0) {
    return `#${log.agent_id}`;
  }
  return $t('tenant.ai.actionLog.agentUnavailable');
}

function getOperatorTypeText(operatorType: null | string | undefined): string {
  switch (operatorType) {
    case 'admin':
    case 'platform_admin': {
      return $t('tenant.ai.actionLog.operatorTypes.admin');
    }
    case 'tenant_admin': {
      return $t('tenant.ai.actionLog.operatorTypes.tenantAdmin');
    }
    case 'tenant_user': {
      return $t('tenant.ai.actionLog.operatorTypes.tenantUser');
    }
    default: {
      return '';
    }
  }
}

function getOperatorTypeColor(operatorType: null | string | undefined): string {
  switch (operatorType) {
    case 'admin':
    case 'platform_admin': {
      return 'gold';
    }
    case 'tenant_admin': {
      return 'blue';
    }
    case 'tenant_user': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

function getOperatorDisplayName(
  log: null | OperatorIdentitySource | undefined,
): string {
  return (
    log?.operator_display_name ||
    log?.operator_nickname ||
    log?.operator_name ||
    (log?.operator_id ? `#${log.operator_id}` : '-')
  );
}

function buildOperatorIdentityModel(
  log: null | OperatorIdentitySource | undefined,
) {
  const typeText = getOperatorTypeText(log?.operator_type);

  return {
    avatar: log?.operator_avatar,
    badges: typeText
      ? [
          {
            color: getOperatorTypeColor(log?.operator_type),
            key: `operator-type-${log?.operator_id ?? log?.operator_name ?? 'unknown'}`,
            label: typeText,
          },
        ]
      : [],
    displayName: log?.operator_display_name,
    id: log?.operator_id ?? '-',
    isActive: log?.operator_is_active,
    isLeader: log?.operator_is_leader,
    isOwner: log?.operator_is_owner,
    nickname: getOperatorDisplayName(log),
    orgNodeName: log?.operator_org_node_name,
    roleName: log?.operator_role_name,
    username:
      log?.operator_display_name || log?.operator_nickname
        ? undefined
        : (log?.operator_name ?? undefined),
  };
}

function buildOperatorMeta(
  log:
    | null
    | (OperatorIdentitySource & {
        created_at?: null | string;
      })
    | undefined,
): IdentityDetailMeta {
  return {
    createdAt: log?.created_at,
    orgNodeName: log?.operator_org_node_name,
    roleName: log?.operator_role_name,
    scope: 'tenant',
    subjectType: log?.operator_type,
    userType: log?.operator_type,
    username:
      log?.operator_name ||
      log?.operator_display_name ||
      log?.operator_nickname ||
      undefined,
  };
}

function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

function getInitialLetter(value: null | string | undefined): string {
  const text = String(value || '').trim();
  return text ? text.charAt(0).toUpperCase() : '?';
}

function isStructuredValue(
  value: unknown,
): value is Record<string, unknown> | unknown[] {
  return Array.isArray(value) || (!!value && typeof value === 'object');
}

function tryFormatStringAsJson(value: string): null | string {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const looksLikeJson =
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'));
  if (!looksLikeJson) {
    return null;
  }
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch {
    return null;
  }
}

function stringifyPayload(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string') {
    return tryFormatStringAsJson(value) ?? value;
  }
  if (isStructuredValue(value)) {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function buildPayloadEntries(
  payload: null | Record<string, unknown>,
): PayloadEntry[] {
  if (!payload) {
    return [];
  }
  return Object.entries(payload).map(([key, value]) => ({
    key,
    kind: isStructuredValue(value) ? 'json' : 'scalar',
    valueText: stringifyPayload(value) || '-',
  }));
}

function formatDuration(durationMs: null | number | undefined): string {
  return durationMs ? `${durationMs}ms` : '-';
}

function formatPayloadSize(payloadText: string): string {
  if (!payloadText) {
    return '-';
  }
  const bytes = new TextEncoder().encode(payloadText).length;
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function copyPayload(text: string) {
  if (!text) {
    return;
  }
  const success = await copyToClipboard(text);
  if (success) {
    message.success($t('common.copied'));
    return;
  }
  message.error($t('common.http.copyFailed'));
}

// ============ 统计 / Statistics ============

const stats = ref<ActionLogStats>({
  total: 0,
  success_count: 0,
  failed_count: 0,
  rejected_count: 0,
  pending_count: 0,
  level_read: 0,
  level_safe_write: 0,
  level_dangerous: 0,
  avg_duration_ms: null,
});

async function fetchStats() {
  try {
    stats.value = await getActionLogStatsApi();
  } catch {
    // ignore / 忽略统计拉取失败
  }
}

const successRate = ref('0%');
function computeSuccessRate() {
  const total = stats.value.total;
  if (total === 0) {
    successRate.value = '-';
    return;
  }
  const rate = (stats.value.success_count / total) * 100;
  successRate.value = `${rate.toFixed(1)}%`;
}

async function loadStats() {
  await fetchStats();
  computeSuccessRate();
}

const heroMetrics = computed(() => [
  {
    key: 'total',
    label: $t('tenant.ai.actionLog.stats.totalActions'),
    value: stats.value.total,
  },
  {
    key: 'successRate',
    label: $t('tenant.ai.actionLog.stats.successRate'),
    value: successRate.value,
  },
  {
    key: 'rejected',
    label: $t('tenant.ai.actionLog.stats.rejectedCount'),
    value: stats.value.rejected_count,
  },
  {
    key: 'failed',
    label: $t('tenant.ai.actionLog.status_options.failed'),
    value: stats.value.failed_count,
  },
]);

const heroChips = computed(() => [
  {
    key: 'audit',
    icon: 'lucide:shield-check',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t('tenant.ai.actionLog.actionType')} / ${$t('tenant.ai.actionLog.status')} / ${$t('tenant.ai.actionLog.executionTime')}`,
  },
  {
    key: 'levels',
    icon: 'lucide:badge-alert',
    className: 'bg-background/90 text-foreground',
    text: `${stats.value.level_read}/${stats.value.level_safe_write}/${stats.value.level_dangerous}`,
  },
]);

// ============ 详情抽屉 / Detail drawer ============

const detailOpen = ref(false);
const detailLoading = ref(false);
const detailData = ref<ActionLogDetail | null>(null);
const linkedDecision = ref<ExecutionDecisionItem | null>(null);
const linkedDecisionLoading = ref(false);
const activeTab = ref<DetailTabKey>('overview');

async function openDetail(row: ActionLogItem) {
  await openDetailById(row.id);
}

async function openDetailById(id: number) {
  detailOpen.value = true;
  detailLoading.value = true;
  linkedDecision.value = null;
  linkedDecisionLoading.value = false;
  activeTab.value = 'overview';
  try {
    detailData.value = await getActionLogDetailApi(id);
    if (detailData.value?.execution_decision_id) {
      linkedDecisionLoading.value = true;
      try {
        linkedDecision.value = await getExecutionDecisionDetailApi(
          detailData.value.execution_decision_id,
        );
      } catch {
        linkedDecision.value = null;
      } finally {
        linkedDecisionLoading.value = false;
      }
    }
    activeTab.value = detailData.value?.error_message ? 'error' : 'overview';
  } catch {
    detailData.value = null;
    linkedDecision.value = null;
  } finally {
    detailLoading.value = false;
  }
}

watch(detailOpen, (open) => {
  if (!open) {
    detailData.value = null;
    linkedDecision.value = null;
    linkedDecisionLoading.value = false;
    detailLoading.value = false;
    activeTab.value = 'overview';
  }
});

const detailRequestEntries = computed(() =>
  buildPayloadEntries(detailData.value?.request_data ?? null),
);
const detailResponseEntries = computed(() =>
  buildPayloadEntries(detailData.value?.response_data ?? null),
);
const requestPayloadText = computed(() =>
  stringifyPayload(detailData.value?.request_data ?? null),
);
const responsePayloadText = computed(() =>
  stringifyPayload(detailData.value?.response_data ?? null),
);
const errorPayloadText = computed(
  () => detailData.value?.error_message?.trim() ?? '',
);
const detailAgentLabel = computed(() => {
  if (!detailData.value) {
    return '-';
  }
  return getAgentDisplayName(detailData.value);
});

onMounted(() => {
  loadStats();
});

// ============ 列表 / List ============

const { Grid, onRefresh } = useCrudPage<ActionLogItem>({
  api: {
    list: getActionLogListApi,
    resource: '/tenant/ai/action-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  search: {
    defaultOpen: false,
    quickSearch: {
      defaultField: 'filter[action_name][ilike]',
      fields: [
        'filter[action_name][ilike]',
        'filter[trace_id][ilike]',
        'filter[tool_call_id][ilike]',
      ],
    },
  },
  i18nPrefix: 'tenant.ai.actionLog',
  defaultSort: '-created_at',
  rowHeight: 72,
  customActions: {
    detail: openDetail,
  },
  ai: {
    entityName: $t('tenant.ai.actionLog.name'),
    entityDescription: $t('tenant.ai.actionLog.pageDesc'),
    contextExtras: () => ({
      avg_duration_ms: stats.value.avg_duration_ms,
      failed_count: stats.value.failed_count,
      pending_count: stats.value.pending_count,
      rejected_count: stats.value.rejected_count,
      success_count: stats.value.success_count,
      success_rate: successRate.value,
      total_actions: stats.value.total,
    }),
    extra: [
      createRefreshPageOperation({
        description:
          'Reload the action log list and summary / 重新加载操作日志列表与摘要',
        action: async () => {
          await Promise.resolve(onRefresh());
          await loadStats();
        },
      }),
      createViewDetailPageOperation({
        description:
          'Open the action log detail drawer by ID / 按 ID 打开操作日志详情抽屉',
        idDescription: 'Action log ID / 操作日志 ID',
        openDetail: async (id) => {
          await openDetailById(id);
        },
      }),
    ],
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('tenant.ai.actionLog.pageDesc')"
      icon="lucide:shield-check"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="heroMetrics"
      :title="$t('tenant.ai.actionLog.title')"
    />

    <!-- 列表 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.created_at) }}
            </span>
          </Tooltip>
        </template>

        <!-- 操作名称列 -->
        <template #actionName_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon icon="lucide:zap" class="size-3.5 text-primary" />
            <code class="rounded bg-accent px-1 py-0.5 text-xs font-medium">
              {{ row.action_name }}
            </code>
          </div>
        </template>

        <!-- 类型列 -->
        <template #actionType_cell="{ row }">
          <Tag :color="getTypeColor(row.action_type)">
            {{ getTypeText(row.action_type) }}
          </Tag>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="getStatusColor(row.status)">
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <template #agent_cell="{ row }">
          <div class="flex items-center justify-start gap-2 text-left">
            <div
              class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-primary/10 text-primary shadow-sm"
            >
              <img
                v-if="row.agent_avatar && !isIconAvatar(row.agent_avatar)"
                :alt="getAgentDisplayName(row)"
                :src="toAvatarDisplayUrl(row.agent_avatar)"
                class="size-full object-cover"
              />
              <IconifyIcon
                v-else-if="isIconAvatar(row.agent_avatar)"
                :icon="String(row.agent_avatar)"
                class="size-4.5"
              />
              <span v-else class="text-sm font-semibold">
                {{ getInitialLetter(getAgentDisplayName(row)) }}
              </span>
            </div>
            <div class="min-w-0 flex-1 text-left">
              <div class="truncate text-sm font-medium text-foreground">
                {{ getAgentDisplayName(row) }}
              </div>
              <div
                v-if="row.agent_id"
                class="truncate text-xs text-muted-foreground"
              >
                #{{ row.agent_id }}
              </div>
            </div>
          </div>
        </template>

        <template #operator_cell="{ row }">
          <IdentityTrigger
            :avatar-size="36"
            :model="buildOperatorIdentityModel(row)"
            :meta="buildOperatorMeta(row)"
          />
        </template>

        <!-- 耗时列 -->
        <template #executionTime_cell="{ row }">
          <span v-if="row.duration_ms" class="text-muted-foreground">
            {{ row.duration_ms }}ms
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>
      </Grid>
    </Card>

    <Drawer v-model:open="detailOpen" width="920">
      <template #title>
        <div class="flex flex-wrap items-center gap-2">
          <IconifyIcon icon="lucide:file-search" class="text-primary" />
          <span>{{ $t('tenant.ai.actionLog.detailTitle') }}</span>
          <Tag v-if="detailData" :color="getStatusColor(detailData.status)">
            {{ getStatusText(detailData.status) }}
          </Tag>
        </div>
      </template>

      <div v-if="detailLoading" class="space-y-3 p-1">
        <Skeleton active :paragraph="{ rows: 4 }" />
        <Skeleton active :paragraph="{ rows: 6 }" />
      </div>

      <template v-else-if="detailData">
        <div class="space-y-4">
          <Card :bordered="false" class="bg-accent/35">
            <div class="space-y-4">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="space-y-2">
                  <div class="text-xs text-muted-foreground">
                    {{ $t('tenant.ai.actionLog.summary') }}
                  </div>
                  <div class="flex flex-wrap items-center gap-2">
                    <IconifyIcon icon="lucide:zap" class="text-primary" />
                    <code
                      class="rounded bg-background px-2 py-1 text-sm font-semibold"
                    >
                      {{ detailData.action_name }}
                    </code>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <Tag :color="getTypeColor(detailData.action_type)">
                      {{ getTypeText(detailData.action_type) }}
                    </Tag>
                    <Tag :color="getLevelColor(detailData.action_level)">
                      {{ getLevelText(detailData.action_level) }}
                    </Tag>
                    <Tag :color="getStatusColor(detailData.status)">
                      {{ getStatusText(detailData.status) }}
                    </Tag>
                  </div>
                </div>

                <Button
                  size="small"
                  @click="
                    copyPayload(responsePayloadText || requestPayloadText)
                  "
                >
                  {{ $t('tenant.ai.actionLog.copyPayload') }}
                </Button>
              </div>

              <div class="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
                <article
                  class="rounded-xl border border-border/70 bg-background/80 px-3 py-3 shadow-sm"
                >
                  <div class="text-xs text-muted-foreground">
                    {{ $t('tenant.ai.actionLog.agentName') }}
                  </div>
                  <div class="mt-2 flex items-center gap-3">
                    <div
                      class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-primary/10 text-primary"
                    >
                      <img
                        v-if="
                          detailData.agent_avatar &&
                          !isIconAvatar(detailData.agent_avatar)
                        "
                        :alt="detailAgentLabel"
                        :src="toAvatarDisplayUrl(detailData.agent_avatar)"
                        class="size-full object-cover"
                      />
                      <IconifyIcon
                        v-else-if="isIconAvatar(detailData.agent_avatar)"
                        :icon="String(detailData.agent_avatar)"
                        class="size-5"
                      />
                      <span v-else class="text-sm font-semibold">
                        {{ getInitialLetter(detailAgentLabel) }}
                      </span>
                    </div>
                    <div class="min-w-0">
                      <div
                        class="truncate text-sm font-semibold text-foreground"
                      >
                        {{ detailAgentLabel }}
                      </div>
                      <div
                        v-if="detailData.agent_id"
                        class="text-xs text-muted-foreground"
                      >
                        #{{ detailData.agent_id }}
                      </div>
                    </div>
                  </div>
                </article>

                <article
                  class="rounded-xl border border-border/70 bg-background/80 px-3 py-3 shadow-sm"
                >
                  <div class="text-xs text-muted-foreground">
                    {{ $t('tenant.ai.actionLog.operatorId') }}
                  </div>
                  <IdentityTrigger
                    class="mt-2"
                    :model="buildOperatorIdentityModel(detailData)"
                    :meta="buildOperatorMeta(detailData)"
                  />
                </article>
              </div>

              <div class="grid grid-cols-2 gap-3 xl:grid-cols-4">
                <div
                  class="rounded-lg border border-dashed border-border bg-background p-3"
                >
                  <div class="text-xs text-muted-foreground">
                    {{ $t('tenant.ai.actionLog.status') }}
                  </div>
                  <div class="mt-2 text-sm font-semibold">
                    {{ getStatusText(detailData.status) }}
                  </div>
                </div>
                <div
                  class="rounded-lg border border-dashed border-border bg-background p-3"
                >
                  <div class="text-xs text-muted-foreground">
                    {{ $t('tenant.ai.actionLog.executionTime') }}
                  </div>
                  <div class="mt-2 text-sm font-semibold">
                    {{ formatDuration(detailData.duration_ms) }}
                  </div>
                </div>
                <div
                  class="rounded-lg border border-dashed border-border bg-background p-3"
                >
                  <div class="text-xs text-muted-foreground">
                    {{ $t('tenant.ai.actionLog.traceId') }}
                  </div>
                  <div class="mt-2 text-sm font-semibold">
                    {{ detailData.trace_id || '-' }}
                  </div>
                  <div class="mt-1 text-xs text-muted-foreground">
                    {{ detailData.tool_call_id || '-' }}
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <Tabs v-model:active-key="activeTab" size="small">
            <Tabs.TabPane
              key="overview"
              :tab="$t('tenant.ai.actionLog.overviewTab')"
            >
              <div class="space-y-4">
                <Card size="small" :title="$t('tenant.ai.actionLog.basicInfo')">
                  <Descriptions :column="2" bordered size="small">
                    <Descriptions.Item :label="$t('tenant.ai.actionLog.id')">
                      {{ detailData.id }}
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.createdAt')"
                    >
                      {{ formatDate(detailData.created_at) }}
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.actionName')"
                    >
                      <code class="rounded bg-accent px-1.5 py-0.5 text-xs">
                        {{ detailData.action_name }}
                      </code>
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.actionType')"
                    >
                      <Tag :color="getTypeColor(detailData.action_type)">
                        {{ getTypeText(detailData.action_type) }}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.actionLevel')"
                    >
                      <Tag :color="getLevelColor(detailData.action_level)">
                        {{ getLevelText(detailData.action_level) }}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.status')"
                    >
                      <Tag :color="getStatusColor(detailData.status)">
                        {{ getStatusText(detailData.status) }}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.agentName')"
                    >
                      <div class="flex items-center gap-2">
                        <Avatar
                          v-if="
                            detailData.agent_avatar &&
                            !isIconAvatar(detailData.agent_avatar)
                          "
                          :size="24"
                          :src="toAvatarDisplayUrl(detailData.agent_avatar)"
                        />
                        <span class="flex items-center gap-1.5">
                          <IconifyIcon
                            v-if="isIconAvatar(detailData.agent_avatar)"
                            :icon="String(detailData.agent_avatar)"
                            class="size-4 text-primary"
                          />
                          <IconifyIcon
                            v-else-if="!detailData.agent_avatar"
                            icon="lucide:bot"
                            class="size-4 text-primary"
                          />
                          <span>{{ detailAgentLabel }}</span>
                        </span>
                      </div>
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.operatorId')"
                    >
                      <IdentityTrigger
                        :avatar-size="24"
                        :model="buildOperatorIdentityModel(detailData)"
                        :meta="buildOperatorMeta(detailData)"
                      />
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.traceId')"
                    >
                      <code>{{ detailData.trace_id || '-' }}</code>
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.toolCallId')"
                    >
                      <code>{{ detailData.tool_call_id || '-' }}</code>
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.actionLog.executionDecisionId')"
                    >
                      {{ detailData.execution_decision_id ?? '-' }}
                    </Descriptions.Item>
                  </Descriptions>
                </Card>

                <Alert
                  v-if="errorPayloadText"
                  show-icon
                  type="error"
                  :message="$t('tenant.ai.actionLog.errorMessage')"
                  :description="errorPayloadText"
                />

                <Card
                  v-if="linkedDecision || linkedDecisionLoading"
                  size="small"
                  :title="$t('tenant.ai.actionLog.linkedDecision')"
                >
                  <div
                    v-if="linkedDecisionLoading"
                    class="flex items-center justify-center py-6"
                  >
                    <Skeleton active :paragraph="{ rows: 2 }" />
                  </div>
                  <Descriptions
                    v-else-if="linkedDecision"
                    :column="2"
                    bordered
                    size="small"
                  >
                    <Descriptions.Item
                      :label="$t('tenant.ai.executionDecision.id')"
                    >
                      {{ linkedDecision.id }}
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.executionDecision.createdAt')"
                    >
                      {{ formatDate(linkedDecision.created_at) }}
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.executionDecision.decisionType')"
                    >
                      {{
                        getExecutionDecisionTypeText(
                          linkedDecision.decision_type,
                        )
                      }}
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.executionDecision.status')"
                    >
                      {{
                        getExecutionDecisionStatusText(linkedDecision.status)
                      }}
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.executionDecision.toolName')"
                    >
                      {{ linkedDecision.tool_name || '-' }}
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.executionDecision.actionName')"
                    >
                      {{ linkedDecision.action_name || '-' }}
                    </Descriptions.Item>
                    <Descriptions.Item
                      :label="$t('tenant.ai.executionDecision.correlationKey')"
                      :span="2"
                    >
                      <code>{{ linkedDecision.correlation_key }}</code>
                    </Descriptions.Item>
                  </Descriptions>
                </Card>
              </div>
            </Tabs.TabPane>

            <Tabs.TabPane
              key="request"
              :tab="$t('tenant.ai.actionLog.requestTab')"
            >
              <Card size="small" :title="$t('tenant.ai.actionLog.requestData')">
                <template #extra>
                  <div class="flex items-center gap-2">
                    <Tag>
                      {{
                        $t('tenant.ai.actionLog.fieldsCount', {
                          count: detailRequestEntries.length,
                        })
                      }}
                    </Tag>
                    <Tag>{{ formatPayloadSize(requestPayloadText) }}</Tag>
                    <Button
                      size="small"
                      type="text"
                      @click="copyPayload(requestPayloadText)"
                    >
                      {{ $t('tenant.ai.actionLog.copyPayload') }}
                    </Button>
                  </div>
                </template>

                <div v-if="detailRequestEntries.length > 0" class="space-y-3">
                  <div
                    v-for="entry in detailRequestEntries"
                    :key="`request-${entry.key}`"
                    class="rounded-lg border border-border bg-background p-3"
                  >
                    <div class="mb-2 flex items-center justify-between gap-2">
                      <span class="text-sm font-medium">{{ entry.key }}</span>
                      <Tag v-if="entry.kind === 'json'">JSON</Tag>
                    </div>

                    <pre
                      v-if="entry.kind === 'json'"
                      class="m-0 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded bg-accent/60 p-3 text-xs"
                      >{{ entry.valueText }}</pre
                    >
                    <code
                      v-else
                      class="block break-all rounded bg-accent/60 px-2 py-2 text-xs"
                      >{{ entry.valueText }}</code
                    >
                  </div>
                </div>

                <Empty
                  v-else
                  :description="$t('tenant.ai.actionLog.noRequestData')"
                />
              </Card>
            </Tabs.TabPane>

            <Tabs.TabPane
              key="response"
              :tab="$t('tenant.ai.actionLog.responseTab')"
            >
              <Card
                size="small"
                :title="$t('tenant.ai.actionLog.responseData')"
              >
                <template #extra>
                  <div class="flex items-center gap-2">
                    <Tag>
                      {{
                        $t('tenant.ai.actionLog.fieldsCount', {
                          count: detailResponseEntries.length,
                        })
                      }}
                    </Tag>
                    <Tag>{{ formatPayloadSize(responsePayloadText) }}</Tag>
                    <Button
                      size="small"
                      type="text"
                      @click="copyPayload(responsePayloadText)"
                    >
                      {{ $t('tenant.ai.actionLog.copyPayload') }}
                    </Button>
                  </div>
                </template>

                <div v-if="detailResponseEntries.length > 0" class="space-y-3">
                  <div
                    v-for="entry in detailResponseEntries"
                    :key="`response-${entry.key}`"
                    class="rounded-lg border border-border bg-background p-3"
                  >
                    <div class="mb-2 flex items-center justify-between gap-2">
                      <span class="text-sm font-medium">{{ entry.key }}</span>
                      <Tag v-if="entry.kind === 'json'">JSON</Tag>
                    </div>

                    <pre
                      v-if="entry.kind === 'json'"
                      class="m-0 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded bg-accent/60 p-3 text-xs"
                      >{{ entry.valueText }}</pre
                    >
                    <code
                      v-else
                      class="block break-all rounded bg-accent/60 px-2 py-2 text-xs"
                      >{{ entry.valueText }}</code
                    >
                  </div>
                </div>

                <Empty
                  v-else
                  :description="$t('tenant.ai.actionLog.noResponseData')"
                />
              </Card>
            </Tabs.TabPane>

            <Tabs.TabPane key="error" :tab="$t('tenant.ai.actionLog.errorTab')">
              <Card
                size="small"
                :title="$t('tenant.ai.actionLog.errorMessage')"
              >
                <template #extra>
                  <Button
                    v-if="errorPayloadText"
                    size="small"
                    type="text"
                    @click="copyPayload(errorPayloadText)"
                  >
                    {{ $t('tenant.ai.actionLog.copyPayload') }}
                  </Button>
                </template>

                <Alert
                  v-if="errorPayloadText"
                  show-icon
                  type="error"
                  :message="$t('tenant.ai.actionLog.errorMessage')"
                  :description="errorPayloadText"
                />
                <Empty
                  v-else
                  :description="$t('tenant.ai.actionLog.noErrorData')"
                />
              </Card>
            </Tabs.TabPane>
          </Tabs>
        </div>
      </template>

      <Empty v-else :description="$t('tenant.ai.actionLog.noDetailData')" />
    </Drawer>
  </Page>
</template>
