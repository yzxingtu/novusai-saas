<script lang="ts" setup>
import type { tenantApi } from '#/api';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, message, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { tenantApi as tenant } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  formatInterval,
  getFormDefaults,
  getScheduleTypeText,
  useColumns,
  useFormSchema,
  useGridFormSchema,
} from './data';
import Form from './modules/PeriodicTaskForm.vue';

defineOptions({ name: 'TenantSystemPeriodicTaskList' });

type PeriodicTaskInfo = tenantApi.PeriodicTaskInfo;

async function onTriggerTask(row: PeriodicTaskInfo) {
  try {
    await tenant.triggerPeriodicTaskApi(row.id);
    message.success($t('tenant.system.periodicTask.messages.triggerSuccess'));
    onRefresh();
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
  }
}

async function onToggleActive(row: PeriodicTaskInfo, checked: boolean) {
  try {
    await tenant.togglePeriodicTaskApi(row.id, checked);
    message.success($t('tenant.system.periodicTask.messages.toggleSuccess'));
    onRefresh();
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
  }
}

const { Grid, FormDrawer, onRefresh } =
  useCrudPage<PeriodicTaskInfo>({
    api: {
      list: tenant.getPeriodicTaskListApi,
      resource: '/tenant/periodic-tasks',
    },
    columns: useColumns,
    searchSchema: useGridFormSchema(),
    formComponent: Form,
    formDefaults: getFormDefaults,
    i18nPrefix: 'tenant.system.periodicTask',
    nameField: 'name',
    defaultSort: '-created_at',
    createPermission: 'periodic_task:create',
    recycleBin: true,
    customActions: {
      trigger: onTriggerTask,
    },
    ai: {
      pageKey: 'tenant.system.periodic-tasks',
      formSchema: (isEdit?: boolean) => useFormSchema(Boolean(isEdit)),
    },
  });
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-lg"
              :class="row.isActive ? 'bg-success/10' : 'bg-muted'"
            >
              <IconifyIcon
                icon="lucide:timer"
                class="size-4"
                :class="row.isActive ? 'text-success' : 'text-muted-foreground'"
              />
            </div>
            <div class="flex flex-col">
              <span class="font-medium text-foreground">{{ row.name }}</span>
              <span
                v-if="row.description"
                class="line-clamp-1 text-xs text-muted-foreground"
              >
                {{ row.description }}
              </span>
            </div>
          </div>
        </template>

        <template #taskPath_cell="{ row }">
          <Tooltip :title="row.taskPath">
            <code
              class="max-w-[250px] truncate rounded bg-accent px-1 py-0.5 text-xs"
            >
              {{ row.taskPath }}
            </code>
          </Tooltip>
        </template>

        <template #scheduleType_cell="{ row }">
          <Tag :color="row.scheduleType === 'cron' ? 'purple' : 'blue'">
            {{ getScheduleTypeText(row.scheduleType) }}
          </Tag>
        </template>

        <template #schedule_cell="{ row }">
          <code
            v-if="row.scheduleType === 'cron' && row.cronExpression"
            class="rounded bg-accent px-1 py-0.5 text-xs"
          >
            {{ row.cronExpression }}
          </code>
          <Tag v-else-if="row.scheduleType === 'interval'" color="cyan">
            {{ formatInterval(row.intervalSeconds) }}
          </Tag>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['periodic_task:toggle']"
            :checked="row.isActive"
            size="small"
            @change="
              (checked: boolean | string | number) =>
                onToggleActive(row, !!checked)
            "
          />
        </template>

        <template #lastRunAt_cell="{ row }">
          <Tooltip v-if="row.lastRunAt" :title="formatDate(row.lastRunAt)">
            <span class="text-muted-foreground">{{
              formatRelativeTime(row.lastRunAt)
            }}</span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <template #nextRunAt_cell="{ row }">
          <Tooltip v-if="row.nextRunAt" :title="formatDate(row.nextRunAt)">
            <span class="text-muted-foreground">{{
              formatRelativeTime(row.nextRunAt)
            }}</span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
