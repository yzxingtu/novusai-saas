<script lang="ts" setup>
/**
 * 任务日志列表页面
 */
import type { adminApi } from '#/api';

import { onUnmounted } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page, useVbenDrawer } from '@vben/common-ui';

import { Badge, Card, message, Tag, Tooltip } from 'ant-design-vue';

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

const { Grid, onRefresh, gridApi } = useCrudPage<TaskLogInfo>({
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

const cleanupPageContext = registerPageContext('admin/system/task-logs', () => ({
  page_key: 'admin.system.task-logs',
  page_title: $t('admin.system.taskLog.name'),
  page_data: {
    resource: '/admin/tasks',
  },
}));

const cleanupPageOps = registerPageOperations('admin.system.task-logs', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the task log list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Task log list refreshed' };
    },
  },
  {
    name: 'search_logs',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search task logs by task name',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Task name keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[task_name][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <TaskLogDetailComp />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 任务名称列 -->
        <template #taskName_cell="{ row }">
          <div class="flex flex-col gap-0.5">
            <span class="font-medium text-foreground">
              {{ getTaskShortName(row.taskName) }}
            </span>
            <Tooltip :title="row.taskId">
              <span class="truncate text-xs text-muted-foreground">
                {{ row.taskName }}
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
    </Card>
  </Page>
</template>
