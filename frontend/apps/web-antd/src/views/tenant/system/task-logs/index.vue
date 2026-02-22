<script lang="ts" setup>
/**
 * 租户端任务日志列表页面
 */
import type { tenantApi } from '#/api';

defineOptions({ name: 'TenantSystemTaskLogList' });

import { Page, useVbenDrawer } from '@vben/common-ui';

import { Badge, Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { tenantApi as tenant } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { getTaskShortName } from '#/views/admin/system/task-logs/data';

import { getQueueColor, getStatusColor, useColumns, useGridFormSchema } from './data';
import TaskLogDetail from './modules/TaskLogDetail.vue';

type TaskLogInfo = tenantApi.TaskLogInfo;

const [TaskLogDetailComp, detailDrawerApi] = useVbenDrawer({
  connectedComponent: TaskLogDetail,
});

function onViewDetail(row: TaskLogInfo) {
  detailDrawerApi.setData({ id: row.id, mode: 'view' }).open();
}

const { Grid } = useCrudPage<TaskLogInfo>({
  api: {
    list: tenant.getTaskLogListApi,
    resource: '/tenant/tasks',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'tenant.system.taskLog',
  nameField: 'taskName',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <TaskLogDetailComp />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
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

        <template #status_cell="{ row }">
          <Badge v-if="row.status === 'running'" status="processing" />
          <Tag :color="getStatusColor(row.status)">
            {{ $t(`tenant.system.taskLog.status.${row.status}`) }}
          </Tag>
        </template>

        <template #queue_cell="{ row }">
          <Tag :color="getQueueColor(row.queue)">
            {{ $t(`tenant.system.taskLog.queueNames.${row.queue}`, row.queue) }}
          </Tag>
        </template>

        <template #durationMs_cell="{ row }">
          <span v-if="row.durationMs !== null" :class="row.durationMs > 5000 ? 'font-medium text-warning' : 'text-muted-foreground'">
            {{ row.durationMs }} ms
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <template #retryCount_cell="{ row }">
          <Tag v-if="row.retryCount > 0" color="orange">{{ row.retryCount }}</Tag>
          <span v-else class="text-muted-foreground">0</span>
        </template>

        <template #errorMessage_cell="{ row }">
          <Tooltip v-if="row.errorMessage" :title="row.errorMessage">
            <span class="line-clamp-1 text-destructive">{{ row.errorMessage }}</span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.createdAt)">
            <span class="text-muted-foreground">{{ formatRelativeTime(row.createdAt) }}</span>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
