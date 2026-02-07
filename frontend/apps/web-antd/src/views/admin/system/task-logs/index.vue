<script lang="ts" setup>
/**
 * 任务日志列表页面
 */
import type { adminApi } from '#/api';

defineOptions({ name: 'SystemTaskLogList' });

import { Page, useVbenDrawer } from '@vben/common-ui';

import { Badge, Card, message, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { getQueueColor, getStatusColor, useColumns, useGridFormSchema } from './data';
import TaskLogDetail from './modules/TaskLogDetail.vue';

type TaskLogInfo = adminApi.TaskLogInfo;

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
    // Error handled by request interceptor
  }
}

const { Grid, onRefresh } = useCrudPage<TaskLogInfo>({
  api: {
    list: admin.getTaskLogListApi,
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
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <TaskLogDetailComp />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 任务名称列 -->
        <template #taskName_cell="{ row }">
          <Tooltip :title="row.taskId">
            <code
              class="max-w-[300px] truncate rounded bg-accent px-1 py-0.5 text-xs"
            >
              {{ row.taskName }}
            </code>
          </Tooltip>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Badge
            v-if="row.status === 'running'"
            status="processing"
          />
          <Tag :color="getStatusColor(row.status)">
            {{ $t(`admin.system.taskLog.status.${row.status}`) }}
          </Tag>
        </template>

        <!-- 队列列 -->
        <template #queue_cell="{ row }">
          <Tag :color="getQueueColor(row.queue)">
            {{ row.queue }}
          </Tag>
        </template>

        <!-- 耗时列 -->
        <template #durationMs_cell="{ row }">
          <span
            v-if="row.durationMs !== null"
            :class="
              row.durationMs > 5000
                ? 'font-medium text-warning'
                : 'text-muted-foreground'
            "
          >
            {{ row.durationMs }} ms
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 重试次数列 -->
        <template #retryCount_cell="{ row }">
          <Tag v-if="row.retryCount > 0" color="orange">
            {{ row.retryCount }}
          </Tag>
          <span v-else class="text-muted-foreground">0</span>
        </template>

        <!-- 错误信息列 -->
        <template #errorMessage_cell="{ row }">
          <Tooltip v-if="row.errorMessage" :title="row.errorMessage">
            <span class="line-clamp-1 text-destructive">
              {{ row.errorMessage }}
            </span>
          </Tooltip>
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
    </Card>
  </Page>
</template>
