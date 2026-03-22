<script lang="ts" setup>
/**
 * 平台端 AI 操作审计日志列表页面 / Platform AI action audit log list page
 *
 * 全局审计日志查询，支持跨企业筛选
 */
import type {
  AdminActionLogDetail,
  AdminActionLogItem,
} from '#/api/admin/action-logs';

import { computed, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Skeleton,
  Tabs,
  Tag,
  Tooltip,
  message,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAdminActionLogDetailApi,
  getAdminActionLogListApi,
} from '#/api/admin/action-logs';
import { createViewDetailPageOperation } from '#/composables';
import { PLATFORM_TENANT_ID } from '#/constants';
import { $t } from '#/locales';
import { copyToClipboard, formatDate, formatRelativeTime } from '#/utils/common';

import {
  getLevelColor,
  getLevelText,
  getStatusColor,
  getStatusText,
  getTenantDisplay,
  getTypeColor,
  getTypeText,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'AdminAIActionLogList' });

type DetailTabKey = 'error' | 'overview' | 'request' | 'response';
type PayloadEntryKind = 'json' | 'scalar';

interface PayloadEntry {
  key: string;
  kind: PayloadEntryKind;
  valueText: string;
}

// ============ 详情抽屉 ============

const detailOpen = ref(false);
const detailLoading = ref(false);
const detailData = ref<AdminActionLogDetail | null>(null);
const activeTab = ref<DetailTabKey>('overview');

function isStructuredValue(value: unknown): value is Record<string, unknown> | unknown[] {
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

async function openDetail(row: AdminActionLogItem) {
  await openDetailById(row.id);
}

async function openDetailById(id: number) {
  detailOpen.value = true;
  detailLoading.value = true;
  activeTab.value = 'overview';
  try {
    detailData.value = await getAdminActionLogDetailApi(id);
    activeTab.value = detailData.value?.error_message ? 'error' : 'overview';
  } catch {
    detailData.value = null;
  } finally {
    detailLoading.value = false;
  }
}

watch(detailOpen, (open) => {
  if (!open) {
    detailData.value = null;
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
const errorPayloadText = computed(() => detailData.value?.error_message?.trim() ?? '');

// ============ 列表 ============

const { Grid } = useCrudPage<AdminActionLogItem>({
  api: {
    list: getAdminActionLogListApi,
    resource: '/admin/ai/action-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.ai.actionLog',
  defaultSort: '-created_at',
  customActions: {
    detail: openDetail,
  },
  ai: {
    entityName: $t('admin.ai.actionLog.name'),
    entityDescription: $t('admin.ai.actionLog.pageDesc'),
    extra: [
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
  <Page
    auto-content-height
    :description="$t('admin.ai.actionLog.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.created_at) }}
            </span>
          </Tooltip>
        </template>

        <template #actionName_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon icon="lucide:zap" class="size-3.5 text-primary" />
            <code class="rounded bg-accent px-1 py-0.5 text-xs font-medium">
              {{ row.action_name }}
            </code>
          </div>
        </template>

        <template #actionType_cell="{ row }">
          <Tag :color="getTypeColor(row.action_type)">
            {{ getTypeText(row.action_type) }}
          </Tag>
        </template>

        <template #actionLevel_cell="{ row }">
          <Tag :color="getLevelColor(row.action_level)">
            {{ getLevelText(row.action_level) }}
          </Tag>
        </template>

        <template #status_cell="{ row }">
          <Tag :color="getStatusColor(row.status)">
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <template #tenantInfo_cell="{ row }">
          <div class="flex min-w-0 flex-col">
            <span class="truncate font-medium">
              {{ getTenantDisplay(row) }}
            </span>
            <span
              v-if="row.tenant_id !== PLATFORM_TENANT_ID && row.tenant_code"
              class="text-xs text-muted-foreground"
            >
              {{ row.tenant_code }}
            </span>
          </div>
        </template>

        <template #duration_cell="{ row }">
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
          <span>{{ $t('admin.ai.actionLog.detailTitle') }}</span>
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
                    {{ $t('admin.ai.actionLog.summary') }}
                  </div>
                  <div class="flex flex-wrap items-center gap-2">
                    <IconifyIcon icon="lucide:zap" class="text-primary" />
                    <code class="rounded bg-background px-2 py-1 text-sm font-semibold">
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
                  @click="copyPayload(responsePayloadText || requestPayloadText)"
                >
                  {{ $t('admin.ai.actionLog.copyPayload') }}
                </Button>
              </div>

              <div class="grid grid-cols-2 gap-3 xl:grid-cols-4">
                <div class="rounded-lg border border-dashed border-border bg-background p-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t('admin.ai.actionLog.status') }}
                  </div>
                  <div class="mt-2 text-sm font-semibold">
                    {{ getStatusText(detailData.status) }}
                  </div>
                </div>
                <div class="rounded-lg border border-dashed border-border bg-background p-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t('admin.ai.actionLog.executionTime') }}
                  </div>
                  <div class="mt-2 text-sm font-semibold">
                    {{ formatDuration(detailData.duration_ms) }}
                  </div>
                </div>
                <div class="rounded-lg border border-dashed border-border bg-background p-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t('admin.ai.actionLog.tenantInfo') }}
                  </div>
                  <div class="mt-2 text-sm font-semibold">
                    {{ getTenantDisplay(detailData) }}
                  </div>
                </div>
                <div class="rounded-lg border border-dashed border-border bg-background p-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t('admin.ai.actionLog.operatorId') }}
                  </div>
                  <div class="mt-2 text-sm font-semibold">
                    {{ detailData.operator_id ?? '-' }}
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <Tabs v-model:active-key="activeTab" size="small">
            <Tabs.TabPane key="overview" :tab="$t('admin.ai.actionLog.overviewTab')">
              <div class="space-y-4">
                <Card size="small" :title="$t('admin.ai.actionLog.basicInfo')">
                  <Descriptions :column="2" bordered size="small">
                    <Descriptions.Item :label="$t('admin.ai.actionLog.id')">
                      {{ detailData.id }}
                    </Descriptions.Item>
                    <Descriptions.Item :label="$t('admin.ai.actionLog.createdAt')">
                      {{ formatDate(detailData.created_at) }}
                    </Descriptions.Item>
                    <Descriptions.Item :label="$t('admin.ai.actionLog.actionName')">
                      <code class="rounded bg-accent px-1.5 py-0.5 text-xs">
                        {{ detailData.action_name }}
                      </code>
                    </Descriptions.Item>
                    <Descriptions.Item :label="$t('admin.ai.actionLog.actionType')">
                      <Tag :color="getTypeColor(detailData.action_type)">
                        {{ getTypeText(detailData.action_type) }}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item :label="$t('admin.ai.actionLog.actionLevel')">
                      <Tag :color="getLevelColor(detailData.action_level)">
                        {{ getLevelText(detailData.action_level) }}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item :label="$t('admin.ai.actionLog.status')">
                      <Tag :color="getStatusColor(detailData.status)">
                        {{ getStatusText(detailData.status) }}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item :label="$t('admin.ai.actionLog.tenantInfo')">
                      {{ getTenantDisplay(detailData) }}
                    </Descriptions.Item>
                    <Descriptions.Item :label="$t('admin.ai.actionLog.operatorId')">
                      {{ detailData.operator_id ?? '-' }}
                    </Descriptions.Item>
                  </Descriptions>
                </Card>

                <Alert
                  v-if="errorPayloadText"
                  show-icon
                  type="error"
                  :message="$t('admin.ai.actionLog.error')"
                  :description="errorPayloadText"
                />
              </div>
            </Tabs.TabPane>

            <Tabs.TabPane key="request" :tab="$t('admin.ai.actionLog.requestTab')">
              <Card size="small" :title="$t('admin.ai.actionLog.requestData')">
                <template #extra>
                  <div class="flex items-center gap-2">
                    <Tag>{{ $t('admin.ai.actionLog.fieldsCount', { count: detailRequestEntries.length }) }}</Tag>
                    <Tag>{{ formatPayloadSize(requestPayloadText) }}</Tag>
                    <Button size="small" type="text" @click="copyPayload(requestPayloadText)">
                      {{ $t('admin.ai.actionLog.copyPayload') }}
                    </Button>
                  </div>
                </template>

                <div v-if="detailRequestEntries.length" class="space-y-3">
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
                    >{{ entry.valueText }}</pre>
                    <code
                      v-else
                      class="block break-all rounded bg-accent/60 px-2 py-2 text-xs"
                    >{{ entry.valueText }}</code>
                  </div>
                </div>

                <Empty v-else :description="$t('admin.ai.actionLog.noRequestData')" />
              </Card>
            </Tabs.TabPane>

            <Tabs.TabPane key="response" :tab="$t('admin.ai.actionLog.responseTab')">
              <Card size="small" :title="$t('admin.ai.actionLog.responseData')">
                <template #extra>
                  <div class="flex items-center gap-2">
                    <Tag>{{ $t('admin.ai.actionLog.fieldsCount', { count: detailResponseEntries.length }) }}</Tag>
                    <Tag>{{ formatPayloadSize(responsePayloadText) }}</Tag>
                    <Button size="small" type="text" @click="copyPayload(responsePayloadText)">
                      {{ $t('admin.ai.actionLog.copyPayload') }}
                    </Button>
                  </div>
                </template>

                <div v-if="detailResponseEntries.length" class="space-y-3">
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
                    >{{ entry.valueText }}</pre>
                    <code
                      v-else
                      class="block break-all rounded bg-accent/60 px-2 py-2 text-xs"
                    >{{ entry.valueText }}</code>
                  </div>
                </div>

                <Empty v-else :description="$t('admin.ai.actionLog.noResponseData')" />
              </Card>
            </Tabs.TabPane>

            <Tabs.TabPane key="error" :tab="$t('admin.ai.actionLog.errorTab')">
              <Card size="small" :title="$t('admin.ai.actionLog.error')">
                <template #extra>
                  <Button
                    v-if="errorPayloadText"
                    size="small"
                    type="text"
                    @click="copyPayload(errorPayloadText)"
                  >
                    {{ $t('admin.ai.actionLog.copyPayload') }}
                  </Button>
                </template>

                <Alert
                  v-if="errorPayloadText"
                  show-icon
                  type="error"
                  :message="$t('admin.ai.actionLog.error')"
                  :description="errorPayloadText"
                />
                <Empty v-else :description="$t('admin.ai.actionLog.noErrorData')" />
              </Card>
            </Tabs.TabPane>
          </Tabs>
        </div>
      </template>

      <Empty v-else :description="$t('admin.ai.actionLog.noDetailData')" />
    </Drawer>
  </Page>
</template>
