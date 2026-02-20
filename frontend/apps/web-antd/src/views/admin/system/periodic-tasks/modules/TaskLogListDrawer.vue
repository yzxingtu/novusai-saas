<script lang="ts" setup>
defineOptions({ name: 'TaskLogListDrawer' });
/**
 * 定时任务 - 执行日志抽屉
 * 按 task_path 过滤展示该任务的历史执行记录，支持查看详情
 */
import type { adminApi } from '#/api';

import { ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Descriptions,
  DescriptionsItem,
  Empty,
  Spin,
  Statistic,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { getTaskLogDetailApi, getTaskLogListApi } from '#/api/admin/task-log';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

type TaskLogInfo = adminApi.TaskLogInfo;
type TaskLogDetailInfo = adminApi.TaskLogDetailInfo;

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange(isOpen: boolean) {
    if (isOpen) {
      const data = drawerApi.getData<{ taskPath: string; taskName: string }>();
      if (data) {
        taskPath.value = data.taskPath;
        taskName.value = data.taskName;
        selectedLog.value = null;
        loadLogs();
      }
    }
  },
});

const taskPath = ref('');
const taskName = ref('');
const loading = ref(false);
const logs = ref<TaskLogInfo[]>([]);
const total = ref(0);
const selectedLog = ref<TaskLogDetailInfo | null>(null);
const detailLoading = ref(false);

async function loadLogs() {
  loading.value = true;
  try {
    const res = await getTaskLogListApi({
      'filter[task_name][eq]': taskPath.value,
      'sort': '-created_at',
      'page[size]': 50,
    });
    logs.value = res.items;
    total.value = res.total;
  } catch {
    logs.value = [];
  } finally {
    loading.value = false;
  }
}

async function onSelectLog(log: TaskLogInfo) {
  detailLoading.value = true;
  try {
    selectedLog.value = await getTaskLogDetailApi(log.id);
  } catch {
    selectedLog.value = null;
  } finally {
    detailLoading.value = false;
  }
}

function onBackToList() {
  selectedLog.value = null;
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'success': return 'green';
    case 'failed': return 'red';
    case 'running': return 'blue';
    case 'retrying': return 'orange';
    default: return 'default';
  }
}

function getStatusIcon(status: string): string {
  switch (status) {
    case 'success': return 'lucide:circle-check';
    case 'failed': return 'lucide:circle-x';
    case 'running': return 'lucide:loader-2';
    case 'retrying': return 'lucide:refresh-cw';
    default: return 'lucide:circle-dashed';
  }
}

function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

function getResultText(row: TaskLogInfo): string {
  if (row.errorMessage) return row.errorMessage;
  if (!row.result || typeof row.result !== 'object') return '';
  const r = row.result as Record<string, unknown>;
  const parts: string[] = [];
  if ('total_cleaned' in r) parts.push(`${$t('admin.system.taskLog.resultKeys.cleaned')}: ${r.total_cleaned}`);
  if ('cleaned' in r) parts.push(`${$t('admin.system.taskLog.resultKeys.cleaned')}: ${r.cleaned}`);
  if ('reset_count' in r) parts.push(`${$t('admin.system.taskLog.resultKeys.reset')}: ${r.reset_count}`);
  if ('db' in r) parts.push(`DB: ${r.db}`);
  if ('redis' in r) parts.push(`Redis: ${r.redis}`);
  if ('error' in r) return String(r.error);
  return parts.length > 0 ? parts.join(' | ') : JSON.stringify(r);
}

const successCount = () => logs.value.filter((l) => l.status === 'success').length;
const failedCount = () => logs.value.filter((l) => l.status === 'failed').length;
const avgDuration = () => {
  const durations = logs.value.filter((l) => l.durationMs !== null).map((l) => l.durationMs!);
  if (durations.length === 0) return 0;
  return Math.round(durations.reduce((a, b) => a + b, 0) / durations.length);
};
</script>

<template>
  <Drawer
    :title="`${taskName} - ${$t('admin.system.periodicTask.executionLogs')}`"
    class="w-[640px]"
    :footer="false"
  >
    <!-- 日志列表视图 -->
    <template v-if="!selectedLog">
      <!-- 统计概览 -->
      <div
        v-if="logs.length > 0"
        class="mb-4 grid grid-cols-4 gap-3 rounded-lg border border-border p-3"
      >
        <Statistic
          :title="$t('admin.system.periodicTask.stats.total')"
          :value="total"
          :value-style="{ fontSize: '20px' }"
        />
        <Statistic
          :title="$t('admin.system.periodicTask.stats.success')"
          :value="successCount()"
          :value-style="{ fontSize: '20px', color: 'var(--success)' }"
        />
        <Statistic
          :title="$t('admin.system.periodicTask.stats.failed')"
          :value="failedCount()"
          :value-style="{ fontSize: '20px', color: failedCount() > 0 ? 'var(--destructive)' : undefined }"
        />
        <Statistic
          :title="$t('admin.system.periodicTask.stats.avgDuration')"
          :value="formatDuration(avgDuration())"
          :value-style="{ fontSize: '20px' }"
        />
      </div>

      <div class="mb-3 flex items-center justify-between">
        <span class="text-sm text-muted-foreground">
          {{ $t('admin.system.periodicTask.totalLogs', { count: total }) }}
        </span>
        <Button size="small" @click="loadLogs">
          <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-3" />
          {{ $t('admin.system.periodicTask.refresh') }}
        </Button>
      </div>

      <Spin :spinning="loading">
        <Empty
          v-if="!loading && logs.length === 0"
          :description="$t('admin.system.periodicTask.noLogs')"
        />

        <div v-else class="flex flex-col gap-2">
          <div
            v-for="log in logs"
            :key="log.id"
            class="cursor-pointer rounded-lg border border-border px-3 py-2.5 transition-all hover:border-primary/30 hover:bg-accent/30"
            @click="onSelectLog(log)"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <IconifyIcon
                  :icon="getStatusIcon(log.status)"
                  class="size-4 shrink-0"
                  :class="{
                    'text-success': log.status === 'success',
                    'text-destructive': log.status === 'failed',
                    'text-primary animate-spin': log.status === 'running',
                    'text-warning': log.status === 'retrying',
                  }"
                />
                <Tag :color="getStatusColor(log.status)" class="!m-0">
                  {{ $t(`admin.system.taskLog.status.${log.status}`) }}
                </Tag>
                <span class="tabular-nums text-xs text-muted-foreground">
                  {{ formatDuration(log.durationMs) }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <Tooltip :title="formatDate(log.createdAt)">
                  <span class="text-xs text-muted-foreground">
                    {{ formatRelativeTime(log.createdAt) }}
                  </span>
                </Tooltip>
                <IconifyIcon
                  icon="lucide:chevron-right"
                  class="size-3.5 text-muted-foreground/40"
                />
              </div>
            </div>
            <div
              v-if="getResultText(log)"
              class="mt-1.5 line-clamp-1 pl-6 text-xs"
              :class="log.errorMessage ? 'text-destructive' : 'text-muted-foreground'"
            >
              {{ getResultText(log) }}
            </div>
          </div>
        </div>
      </Spin>
    </template>

    <!-- 日志详情视图 -->
    <template v-else>
      <div class="mb-4">
        <Button size="small" type="text" @click="onBackToList">
          <IconifyIcon icon="lucide:arrow-left" class="mr-1 size-3.5" />
          {{ $t('admin.system.periodicTask.backToList') }}
        </Button>
      </div>

      <Spin :spinning="detailLoading">
        <template v-if="selectedLog">
          <!-- 基本信息 -->
          <div class="mb-4">
            <div class="mb-2 flex items-center gap-2 text-sm font-medium">
              <IconifyIcon icon="lucide:info" class="text-primary" />
              {{ $t('admin.system.taskLog.basicInfo') }}
            </div>
            <Descriptions :column="2" bordered size="small">
              <DescriptionsItem :label="$t('admin.system.taskLog.taskId')" :span="2">
                <code class="break-all text-xs">{{ selectedLog.taskId }}</code>
              </DescriptionsItem>
              <DescriptionsItem :label="$t('admin.system.taskLog.status.label')">
                <Tag :color="getStatusColor(selectedLog.status)">
                  {{ $t(`admin.system.taskLog.status.${selectedLog.status}`) }}
                </Tag>
              </DescriptionsItem>
              <DescriptionsItem :label="$t('admin.system.taskLog.duration')">
                <span
                  :class="selectedLog.durationMs && selectedLog.durationMs > 5000 ? 'font-medium text-warning' : ''"
                >
                  {{ formatDuration(selectedLog.durationMs) }}
                </span>
              </DescriptionsItem>
            </Descriptions>
          </div>

          <!-- 时间 -->
          <div class="mb-4">
            <div class="mb-2 flex items-center gap-2 text-sm font-medium">
              <IconifyIcon icon="lucide:clock" class="text-primary" />
              {{ $t('admin.system.taskLog.timeInfo') }}
            </div>
            <Descriptions :column="1" bordered size="small">
              <DescriptionsItem :label="$t('admin.system.taskLog.startedAt')">
                {{ selectedLog.startedAt ? formatDate(selectedLog.startedAt) : '-' }}
              </DescriptionsItem>
              <DescriptionsItem :label="$t('admin.system.taskLog.finishedAt')">
                {{ selectedLog.finishedAt ? formatDate(selectedLog.finishedAt) : '-' }}
              </DescriptionsItem>
            </Descriptions>
          </div>

          <!-- 结果 -->
          <template v-if="selectedLog.result || selectedLog.errorMessage || selectedLog.traceback">
            <div>
              <div class="mb-2 flex items-center gap-2 text-sm font-medium">
                <IconifyIcon icon="lucide:terminal" class="text-primary" />
                {{ $t('admin.system.taskLog.resultInfo') }}
              </div>
              <Descriptions :column="1" bordered size="small">
                <DescriptionsItem
                  v-if="selectedLog.result"
                  :label="$t('admin.system.taskLog.result')"
                >
                  <pre class="m-0 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-accent p-2 text-xs">{{ JSON.stringify(selectedLog.result, null, 2) }}</pre>
                </DescriptionsItem>
                <DescriptionsItem
                  v-if="selectedLog.errorMessage"
                  :label="$t('admin.system.taskLog.errorMessage')"
                >
                  <span class="text-destructive">{{ selectedLog.errorMessage }}</span>
                </DescriptionsItem>
                <DescriptionsItem
                  v-if="selectedLog.traceback"
                  :label="$t('admin.system.taskLog.traceback')"
                >
                  <pre class="m-0 max-h-60 overflow-auto whitespace-pre-wrap break-all rounded bg-destructive/5 p-2 text-xs text-destructive">{{ selectedLog.traceback }}</pre>
                </DescriptionsItem>
              </Descriptions>
            </div>
          </template>
        </template>
      </Spin>
    </template>
  </Drawer>
</template>
