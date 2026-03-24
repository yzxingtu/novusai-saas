<script lang="ts" setup>
/**
 * 任务日志列表页面
 */
import type { adminApi } from '#/api';

import { computed, ref, watch } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';

import { Badge, Card, message, Segmented, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  formatDuration,
  getQueueColor,
  getResultSummary,
  getStatusColor,
  getTaskShortName,
  useColumns,
  useGridFormSchema,
} from './data';
import TaskLogDetail from './modules/TaskLogDetail.vue';

defineOptions({ name: 'SystemTaskLogList' });

type TaskLogInfo = adminApi.TaskLogInfo;
type TaskLogListView = adminApi.TaskLogListView;

const activeView = ref<TaskLogListView>('execution');

const viewOptions = computed<Array<{ label: string; value: TaskLogListView }>>(
  () => [
    {
      label: $t('admin.system.taskLog.viewModes.execution'),
      value: 'execution',
    },
    {
      label: $t('admin.system.taskLog.viewModes.internal'),
      value: 'internal',
    },
    {
      label: $t('admin.system.taskLog.viewModes.all'),
      value: 'all',
    },
  ],
);

const [TaskLogDetailComp, detailDrawerApi] = useVbenDrawer({
  connectedComponent: TaskLogDetail,
});

function onViewDetail(row: TaskLogInfo) {
  detailDrawerApi.setData({ id: row.id, mode: 'view' }).open();
}

async function onRetryTask(row: TaskLogInfo) {
  try {
    await admin.retryTaskApi(row.id);
    message.success($t('admin.system.taskLog.messages.retrySuccess'));
    onRefresh();
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
  }
}

const { Grid, onRefresh, onReload } = useCrudPage<TaskLogInfo>({
  api: {
    list: (params: Record<string, unknown>) =>
      admin.getTaskLogListApi(
        {
          ...params,
          view: activeView.value,
        },
      ),
    resource: '/admin/tasks',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.system.taskLog',
  nameField: 'taskName',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
    retry: onRetryTask,
  },
});

watch(activeView, () => {
  onReload();
});
</script>

<template>
  <Page auto-content-height content-class="flex min-h-0 flex-col gap-4">
    <TaskLogDetailComp />

    <Card
      class="flex min-h-0 flex-1 flex-col overflow-hidden"
      :body-style="{
        display: 'flex',
        flex: 1,
        flexDirection: 'column',
        minHeight: 0,
        overflow: 'hidden',
        padding: '16px',
      }"
    >
      <div class="mb-4 flex shrink-0 flex-wrap items-center justify-between gap-3">
        <span class="text-sm font-medium text-foreground">
          {{ $t('admin.system.taskLog.viewLabel') }}
        </span>
        <Segmented
          v-model:value="activeView"
          :options="viewOptions"
        />
      </div>

      <div class="min-h-0 flex-1 overflow-hidden">
        <Grid>
          <!-- 任务名称列 -->
          <template #taskName_cell="{ row }">
            <div class="flex flex-col gap-0.5">
              <span class="font-medium text-foreground">
                {{ getTaskShortName(row.handlerPath || row.taskName) }}
              </span>
              <Tooltip :title="row.taskId">
                <span class="truncate text-xs text-muted-foreground">
                  {{ row.handlerPath || row.taskName }}
                </span>
              </Tooltip>
            </div>
          </template>

          <!-- 状态列 -->
          <template #status_cell="{ row }">
            <Badge v-if="row.status === 'running'" status="processing" />
            <Tag :color="getStatusColor(row.status)">
              {{ $t(`admin.system.taskLog.status.${row.status}`) }}
            </Tag>
          </template>

          <!-- 队列列 -->
          <template #queue_cell="{ row }">
            <Tag :color="getQueueColor(row.queue)">
              {{ $t(`admin.system.taskLog.queueNames.${row.queue}`, row.queue) }}
            </Tag>
          </template>

          <!-- 耗时列 -->
          <template #durationMs_cell="{ row }">
            <span
              v-if="row.durationMs !== null && row.durationMs !== undefined"
              class="tabular-nums"
              :class="[
                row.durationMs > 5000
                  ? 'font-medium text-warning'
                  : 'text-muted-foreground',
              ]"
            >
              {{ formatDuration(row.durationMs) }}
            </span>
            <span v-else class="text-muted-foreground">-</span>
          </template>

          <!-- 结果摘要列 -->
          <template #result_cell="{ row }">
            <template v-if="getResultSummary(row)">
              <Tooltip
                v-if="getResultSummary(row)!.type === 'error'"
                :title="getResultSummary(row)!.text"
              >
                <span class="line-clamp-1 text-xs text-destructive">
                  {{ getResultSummary(row)!.text }}
                </span>
              </Tooltip>
              <span
                v-else
                class="line-clamp-1 text-xs"
                :class="
                  getResultSummary(row)!.type === 'success'
                    ? 'text-success'
                    : 'text-muted-foreground'
                "
              >
                {{ getResultSummary(row)!.text }}
              </span>
            </template>
            <span v-else class="text-muted-foreground">-</span>
          </template>

          <!-- 创建时间列 -->
          <template #createdAt_cell="{ row }">
            <Tooltip :title="formatDate(row.createdAt)">
              <span class="text-muted-foreground">{{
                formatRelativeTime(row.createdAt)
              }}</span>
            </Tooltip>
          </template>
        </Grid>
      </div>
    </Card>
  </Page>
</template>
