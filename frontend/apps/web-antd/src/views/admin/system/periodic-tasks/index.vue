<script lang="ts" setup>
/**
 * 定时任务管理列表页面
 */
import type { adminApi } from '#/api';

import { onUnmounted } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, message, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import {
  formatInterval,
  getFormDefaults,
  getScheduleDisplay,
  getScheduleTypeText,
  getTaskIcon,
  getTaskIconBg,
  getTaskIconColor,
  useColumns,
  useFormSchema,
  useGridFormSchema,
} from './data';
import Form from './modules/PeriodicTaskForm.vue';
import TaskLogListDrawer from './modules/TaskLogListDrawer.vue';

defineOptions({ name: 'SystemPeriodicTaskList' });

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

const { Grid, FormDrawer, onRefresh, onCreate, gridApi, formAiOperations } =
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
    defaultSort: 'name',
    rowHeight: 72,
    recycleBin: true,
    createPermission: 'periodic_task:create',
    customActions: {
      trigger: onTriggerTask,
      logs: onViewLogs,
    },
    ai: { pageKey: 'admin.system.periodic-tasks', formSchema: useFormSchema },
  });

const cleanupPageContext = registerPageContext('admin/system/periodic-tasks', () => ({
  page_key: 'admin.system.periodic-tasks',
  page_title: $t('admin.system.periodicTask.name'),
  page_data: {
    resource: '/admin/periodic-tasks',
  },
}));

const cleanupPageOps = registerPageOperations('admin.system.periodic-tasks', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the periodic task list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Periodic task list refreshed' };
    },
  },
  {
    name: 'create_record',
    label: $t('shared.pageOperation.createRecord'),
    description: 'Open the create periodic task form',
    readonly: false,
    handler: async () => {
      onCreate();
      return { success: true, message: 'Create periodic task form opened' };
    },
  },
  {
    name: 'search',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search periodic tasks by name',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Task name keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[name][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
  ...formAiOperations,
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />
    <TaskLogListDrawerComp />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- ═══ 任务名称（图标 + 名称 + 描述 + 路径 + scope 标签） ═══ -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-3">
            <!-- 彩色任务图标 -->
            <div
              class="flex size-9 shrink-0 items-center justify-center rounded-xl transition-colors"
              :class="[row.isActive ? getTaskIconBg(row.taskPath) : 'bg-muted']"
            >
              <IconifyIcon
                :icon="getTaskIcon(row.taskPath)"
                class="size-[18px]"
                :class="
                  row.isActive
                    ? getTaskIconColor(row.taskPath)
                    : 'text-muted-foreground/50'
                "
              />
            </div>
            <!-- 文本信息 -->
            <div class="flex min-w-0 flex-1 flex-col gap-0.5">
              <div class="flex items-center gap-1.5">
                <span
                  class="truncate text-[13px] font-medium"
                  :class="
                    row.isActive ? 'text-foreground' : 'text-muted-foreground'
                  "
                >
                  {{ row.name }}
                </span>
                <IconifyIcon
                  v-if="row.isLocked"
                  icon="lucide:lock"
                  class="size-3 shrink-0 text-warning/70"
                />
                <Tag
                  v-if="row.scope && row.scope !== 'admin_only'"
                  :color="getScopeColor(row.scope)"
                  class="!m-0 !px-1 !text-[10px] !leading-4"
                >
                  {{ getScopeText(row.scope) }}
                </Tag>
              </div>
              <Tooltip
                v-if="row.description"
                :title="row.description.trim()"
                placement="topLeft"
              >
                <span
                  class="block w-full truncate text-left text-xs text-muted-foreground"
                  >{{ row.description.trim() }}</span
                >
              </Tooltip>
              <Tooltip :title="row.taskPath" placement="topLeft">
                <code
                  class="w-fit max-w-[280px] truncate text-[11px] leading-4 text-muted-foreground/50"
                >
                  {{ row.taskPath }}
                </code>
              </Tooltip>
            </div>
          </div>
        </template>

        <!-- ═══ 调度配置（类型标签 + 人类可读表达式） ═══ -->
        <template #schedule_cell="{ row }">
          <div class="flex flex-col items-center gap-1">
            <Tag
              :color="row.scheduleType === 'cron' ? 'purple' : 'blue'"
              class="!m-0 !text-xs"
            >
              <div class="flex items-center gap-1">
                <IconifyIcon
                  :icon="
                    row.scheduleType === 'cron'
                      ? 'lucide:calendar-clock'
                      : 'lucide:repeat'
                  "
                  class="size-3"
                />
                {{ getScheduleTypeText(row.scheduleType) }}
              </div>
            </Tag>
            <Tooltip
              v-if="row.scheduleType === 'cron' && row.cronExpression"
              :title="row.cronExpression"
            >
              <span class="text-xs text-muted-foreground">
                {{ getScheduleDisplay(row) }}
              </span>
            </Tooltip>
            <span
              v-else-if="row.scheduleType === 'interval'"
              class="text-xs text-muted-foreground"
            >
              {{ $t('admin.system.periodicTask.every') }}
              {{ formatInterval(row.intervalSeconds) }}
            </span>
          </div>
        </template>

        <!-- ═══ 启用状态 ═══ -->
        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['periodic_task:toggle']"
            :checked="row.isActive"
            size="small"
            @change="(checked: unknown) => onToggleActive(row, !!checked)"
          />
        </template>

        <!-- ═══ 执行信息（上次 + 下次） ═══ -->
        <template #runInfo_cell="{ row }">
          <div class="flex flex-col gap-1 text-xs">
            <div class="flex items-center gap-1.5">
              <IconifyIcon
                icon="lucide:history"
                class="size-3 shrink-0 text-muted-foreground/40"
              />
              <Tooltip v-if="row.lastRunAt" :title="formatDate(row.lastRunAt)">
                <span class="tabular-nums text-muted-foreground">
                  {{ formatRelativeTime(row.lastRunAt) }}
                </span>
              </Tooltip>
              <span v-else class="text-muted-foreground/30">—</span>
            </div>
            <div class="flex items-center gap-1.5">
              <IconifyIcon
                icon="lucide:timer"
                class="size-3 shrink-0 text-muted-foreground/40"
              />
              <template v-if="row.nextRunAt">
                <Tooltip :title="formatDate(row.nextRunAt)">
                  <span
                    class="tabular-nums"
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
              <span v-else class="text-muted-foreground/30">—</span>
            </div>
          </div>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
