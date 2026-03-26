<script lang="ts" setup>
/**
 * 定时任务治理中心
 */
import type { adminApi } from '#/api';

import { onMounted } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, message, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { getScopeColor, getScopeIcon } from '#/utils/scope-helpers';

import {
  getDistributionCompactText,
  getDefinitionTypeText,
  getFormDefaults,
  normalizeScopeValue,
  getScheduleDisplay,
  getScheduleTypeText,
  getScopeModeLabel,
  getTaskIcon,
  getTaskIconBg,
  getTaskIconColor,
  useColumns,
  useFormSchema,
  useGridFormSchema,
} from './data';
import Form from './modules/PeriodicTaskForm.vue';
import TaskBindingDrawer from './modules/TaskBindingDrawer.vue';
import TaskLogListDrawer from './modules/TaskLogListDrawer.vue';

defineOptions({ name: 'SystemPeriodicTaskList' });

type PeriodicTaskInfo = adminApi.PeriodicTaskInfo;

const [TaskLogListDrawerComp, taskLogDrawerApi] = useVbenDrawer({
  connectedComponent: TaskLogListDrawer,
});
const [TaskBindingDrawerComp, taskBindingDrawerApi] = useVbenDrawer({
  connectedComponent: TaskBindingDrawer,
});

function onViewLogs(row: PeriodicTaskInfo) {
  taskLogDrawerApi
    .setData({ taskPath: row.taskPath, taskName: row.name })
    .open();
}

function onManageBindings(row: PeriodicTaskInfo) {
  taskBindingDrawerApi
    .setData({
      assignedTenantIds: row.assignedTenantIds,
      assignedTenantNames: row.assignedTenantNames,
      bindingCount: row.bindingCount,
      id: row.id,
      name: row.name,
      scope: row.scope,
    })
    .open();
}

async function onTriggerTask(row: PeriodicTaskInfo) {
  try {
    await admin.triggerPeriodicTaskApi(row.id);
    message.success($t('admin.system.periodicTask.messages.triggerSuccess'));
    await onRefresh();
  } catch {
    // handled by interceptor
  }
}

async function onToggleActive(row: PeriodicTaskInfo, checked: boolean) {
  try {
    await admin.togglePeriodicTaskApi(row.id, checked);
    message.success($t('admin.system.periodicTask.messages.toggleSuccess'));
    await onRefresh();
  } catch {
    // handled by interceptor
  }
}

const {
  Grid,
  FormDrawer,
  onRefresh: refreshGrid,
} = useCrudPage<PeriodicTaskInfo>({
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
  rowHeight: 84,
  recycleBin: true,
  createPermission: 'periodic_task:create',
  customActions: {
    trigger: onTriggerTask,
    logs: onViewLogs,
    bindings: onManageBindings,
  },
  ai: {
    formSchema: (isEdit?: boolean) => useFormSchema(Boolean(isEdit)),
  },
});

async function onRefresh() {
  refreshGrid();
}

onMounted(async () => {
  refreshGrid();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-3">
    <FormDrawer @success="onRefresh" />
    <TaskLogListDrawerComp />
    <TaskBindingDrawerComp @success="onRefresh" />

    <Card :body-style="{ padding: '16px' }">
      <Grid>
        <template #name_cell="{ row }">
          <div class="flex items-start gap-3 text-left">
            <div
              class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg"
              :class="[
                row.isActive ? getTaskIconBg(row.taskPath) : 'bg-slate-100',
              ]"
            >
              <IconifyIcon
                :icon="getTaskIcon(row.taskPath)"
                class="size-[15px]"
                :class="
                  row.isActive
                    ? getTaskIconColor(row.taskPath)
                    : 'text-slate-300'
                "
              />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-1">
                <span
                  class="truncate text-[13px] font-semibold leading-5 text-slate-900"
                >
                  {{ row.name }}
                </span>
                <Tag
                  :color="
                    row.definitionType === 'plugin' ? 'magenta' : 'default'
                  "
                  class="!m-0 !px-1 !text-[10px] !leading-4"
                >
                  {{ getDefinitionTypeText(row.definitionType) }}
                </Tag>
              </div>
              <Tooltip
                :title="row.description || row.taskPath"
                placement="topLeft"
              >
                <div class="mt-1 truncate text-[11px] leading-4 text-slate-400">
                  {{ row.description || row.taskPath }}
                </div>
              </Tooltip>
            </div>
          </div>
        </template>

        <template #distribution_cell="{ row }">
          <div class="flex flex-col gap-1 text-left">
            <div class="flex flex-wrap items-center gap-2">
              <Tag
                :color="
                  getScopeColor(normalizeScopeValue(row.scope) ?? undefined)
                "
                class="!m-0"
              >
                <div class="flex items-center gap-1">
                  <IconifyIcon
                    :icon="
                      getScopeIcon(normalizeScopeValue(row.scope) ?? undefined)
                    "
                    class="size-3"
                  />
                  {{ getScopeModeLabel(row.scope) }}
                </div>
              </Tag>
              <Tag
                v-if="row.bindingCount > 0"
                color="default"
                class="!m-0 !px-1 !text-[10px] !leading-4"
              >
                {{ row.bindingCount }}
              </Tag>
            </div>
            <div
              class="line-clamp-1 text-xs leading-5"
              :class="
                row.bindingRequired && !row.bindingConfigured
                  ? 'font-medium text-amber-600'
                  : 'text-slate-500'
              "
            >
              {{ getDistributionCompactText(row) }}
            </div>
          </div>
        </template>

        <template #schedule_cell="{ row }">
          <div class="flex flex-col gap-1 text-left">
            <Tag
              :color="row.scheduleType === 'cron' ? 'purple' : 'blue'"
              class="!m-0 !w-fit !text-xs"
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
              <span class="text-xs text-slate-500">
                {{ getScheduleDisplay(row) }}
              </span>
            </Tooltip>
            <span
              v-else-if="row.scheduleType === 'interval'"
              class="text-xs text-slate-500"
            >
              {{ getScheduleDisplay(row) }}
            </span>
          </div>
        </template>

        <template #isActive_cell="{ row }">
          <div class="flex flex-col items-center gap-1">
            <Switch
              v-access:code="['periodic_task:toggle']"
              :checked="row.isActive"
              :disabled="
                row.definitionType === 'plugin' && row.pluginEnabled === false
              "
              size="small"
              @change="(checked: unknown) => onToggleActive(row, !!checked)"
            />
            <span
              class="text-[11px] font-medium"
              :class="row.isActive ? 'text-emerald-600' : 'text-slate-400'"
            >
              {{
                row.isActive
                  ? $t('admin.system.periodicTask.status.enabled')
                  : $t('admin.system.periodicTask.status.disabled')
              }}
            </span>
          </div>
        </template>

        <template #runInfo_cell="{ row }">
          <div class="flex flex-col gap-1 text-left text-xs">
            <div class="flex items-center gap-1.5">
              <IconifyIcon
                icon="lucide:history"
                class="size-3 shrink-0 text-slate-400"
              />
              <Tooltip v-if="row.lastRunAt" :title="formatDate(row.lastRunAt)">
                <span class="tabular-nums text-slate-600">
                  {{ formatRelativeTime(row.lastRunAt) }}
                </span>
              </Tooltip>
              <span v-else class="text-slate-300">—</span>
            </div>
            <div class="flex items-center gap-1.5">
              <IconifyIcon
                icon="lucide:timer"
                class="size-3 shrink-0 text-slate-400"
              />
              <template v-if="row.nextRunAt">
                <Tooltip :title="formatDate(row.nextRunAt)">
                  <span
                    class="tabular-nums"
                    :class="
                      new Date(row.nextRunAt).getTime() > Date.now()
                        ? 'text-emerald-600'
                        : 'text-amber-600'
                    "
                  >
                    {{ formatRelativeTime(row.nextRunAt) }}
                  </span>
                </Tooltip>
              </template>
              <span v-else class="text-slate-300">—</span>
            </div>
          </div>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
