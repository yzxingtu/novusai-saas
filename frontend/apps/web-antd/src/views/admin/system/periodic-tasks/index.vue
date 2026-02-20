<script lang="ts" setup>
/**
 * 定时任务管理列表页面
 */
import type { adminApi } from '#/api';

defineOptions({ name: 'SystemPeriodicTaskList' });

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Card, message, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  formatInterval,
  getFormDefaults,
  getScheduleTypeText,
  useColumns,
  useGridFormSchema,
} from './data';
import Form from './modules/PeriodicTaskForm.vue';
import TaskLogListDrawer from './modules/TaskLogListDrawer.vue';

type PeriodicTaskInfo = adminApi.PeriodicTaskInfo;

const [TaskLogListDrawerComp, taskLogDrawerApi] = useVbenDrawer({
  connectedComponent: TaskLogListDrawer,
});

function onViewLogs(row: PeriodicTaskInfo) {
  taskLogDrawerApi
    .setData({ taskPath: row.taskPath, taskName: row.name })
    .open();
}

async function onTriggerTask(row: PeriodicTaskInfo) {
  try {
    await admin.triggerPeriodicTaskApi(row.id);
    message.success($t('admin.system.periodicTask.messages.triggerSuccess'));
    onRefresh();
  } catch {
    // Error handled by request interceptor
  }
}

async function onToggleActive(row: PeriodicTaskInfo, checked: boolean) {
  try {
    await admin.togglePeriodicTaskApi(row.id, checked);
    message.success($t('admin.system.periodicTask.messages.toggleSuccess'));
    onRefresh();
  } catch {
    // Error handled by request interceptor
  }
}

const { Grid, FormDrawer, onCreate, onRefresh } =
  useCrudPage<PeriodicTaskInfo>({
    api: {
      list: admin.getPeriodicTaskListApi,
      resource: '/admin/periodic-tasks',
    },
    columns: useColumns,
    searchSchema: useGridFormSchema(),
    formComponent: Form,
    formDefaults: getFormDefaults,
    i18nPrefix: 'admin.system.periodicTask',
    nameField: 'name',
    defaultSort: '-created_at',
    recycleBin: true,
    customActions: {
      trigger: onTriggerTask,
      logs: onViewLogs,
    },
  });
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />
    <TaskLogListDrawerComp />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 名称列（含任务路径 + 描述） -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2.5">
            <div
              class="flex size-8 shrink-0 items-center justify-center rounded-lg"
              :class="row.isActive ? 'bg-success/10' : 'bg-muted'"
            >
              <IconifyIcon
                icon="lucide:timer"
                class="size-4"
                :class="row.isActive ? 'text-success' : 'text-muted-foreground'"
              />
            </div>
            <div class="flex min-w-0 flex-col gap-0.5">
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-foreground">{{ row.name }}</span>
                <IconifyIcon
                  v-if="row.isLocked"
                  icon="lucide:lock"
                  class="size-3.5 shrink-0 text-warning"
                />
              </div>
              <span
                v-if="row.description"
                class="line-clamp-1 text-xs text-muted-foreground"
              >
                {{ row.description }}
              </span>
              <Tooltip :title="row.taskPath">
                <code class="w-fit truncate text-[11px] text-muted-foreground/60">
                  {{ row.taskPath }}
                </code>
              </Tooltip>
            </div>
          </div>
        </template>

        <!-- 调度配置列（类型 + 表达式合并） -->
        <template #schedule_cell="{ row }">
          <div class="flex flex-col items-center gap-1">
            <Tag
              :color="row.scheduleType === 'cron' ? 'purple' : 'blue'"
              class="!m-0"
            >
              {{ getScheduleTypeText(row.scheduleType) }}
            </Tag>
            <code
              v-if="row.scheduleType === 'cron' && row.cronExpression"
              class="text-[11px] text-muted-foreground"
            >
              {{ row.cronExpression }}
            </code>
            <span
              v-else-if="row.scheduleType === 'interval'"
              class="text-xs text-muted-foreground"
            >
              {{ formatInterval(row.intervalSeconds) }}
            </span>
          </div>
        </template>

        <!-- 作用范围列 -->
        <template #scope_cell="{ row }">
          <Tag
            :color="row.scope === 'platform' ? 'geekblue' : row.scope === 'all_tenants' ? 'green' : 'orange'"
          >
            {{ $t(`admin.system.periodicTask.scope.${row.scope === 'all_tenants' ? 'allTenants' : row.scope}`) }}
          </Tag>
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['periodic_task:toggle']"
            :checked="row.isActive"
            size="small"
            @change="(checked: unknown) => onToggleActive(row, !!checked)"
          />
        </template>

        <!-- 执行信息列（上次 + 下次合并） -->
        <template #runInfo_cell="{ row }">
          <div class="flex flex-col gap-0.5 text-xs">
            <div class="flex items-center gap-1">
              <span class="text-muted-foreground/60">{{
                $t('admin.system.periodicTask.lastRunAt')
              }}:</span>
              <Tooltip
                v-if="row.lastRunAt"
                :title="formatDate(row.lastRunAt)"
              >
                <span class="text-muted-foreground">{{
                  formatRelativeTime(row.lastRunAt)
                }}</span>
              </Tooltip>
              <span v-else class="text-muted-foreground/40">-</span>
            </div>
            <div class="flex items-center gap-1">
              <span class="text-muted-foreground/60">{{
                $t('admin.system.periodicTask.nextRunAt')
              }}:</span>
              <template v-if="row.nextRunAt">
                <Tooltip :title="formatDate(row.nextRunAt)">
                  <span
                    :class="
                      new Date(row.nextRunAt).getTime() > Date.now()
                        ? 'text-success'
                        : 'text-warning'
                    "
                  >
                    {{ formatRelativeTime(row.nextRunAt) }}
                  </span>
                </Tooltip>
              </template>
              <span v-else class="text-muted-foreground/40">-</span>
            </div>
          </div>
        </template>

        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['periodic_task:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="onCreate"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('admin.system.periodicTask.create')
              }}</span>
            </div>
          </Card>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
