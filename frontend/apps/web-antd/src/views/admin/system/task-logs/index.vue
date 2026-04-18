<script lang="ts" setup>
import type { adminApi } from '#/api';

import { computed, ref } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, message, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  formatDuration,
  getBindingContextText,
  getEffectiveContextText,
  getOwnerContextText,
  getQueueColor,
  getQueueText,
  getResultSummary,
  getRunKindText,
  getStatusColor,
  getTaskShortName,
  getTriggerSourceText,
  useColumns,
  useGridFormSchema,
} from './data';
import TaskLogDetail from './modules/TaskLogDetail.vue';

defineOptions({ name: 'SystemTaskLogList' });

type TaskLogInfo = adminApi.TaskLogInfo;
type TaskLogListParams = adminApi.TaskLogListParams;
type TaskLogListView = adminApi.TaskLogListView;

const activeView = ref<TaskLogListView>('execution');

const [DetailDrawerComp, detailDrawerApi] = useVbenDrawer({
  connectedComponent: TaskLogDetail,
});

const viewOptions = computed<
  Array<{ icon: string; label: string; value: TaskLogListView }>
>(() => [
  {
    icon: 'lucide:activity',
    label: $t('admin.system.taskLog.viewModes.execution'),
    value: 'execution',
  },
  {
    icon: 'lucide:cpu',
    label: $t('admin.system.taskLog.viewModes.internal'),
    value: 'internal',
  },
  {
    icon: 'lucide:layers-3',
    label: $t('admin.system.taskLog.viewModes.all'),
    value: 'all',
  },
]);

function getResultSummaryClass(type: 'error' | 'info' | 'success') {
  switch (type) {
    case 'error': {
      return 'text-destructive';
    }
    case 'success': {
      return 'text-success';
    }
    default: {
      return 'text-muted-foreground';
    }
  }
}

function getResultText(row: TaskLogInfo): string {
  return getResultSummary(row)?.text ?? '';
}

function getResultTypeClass(row: TaskLogInfo): string {
  return getResultSummaryClass(getResultSummary(row)?.type ?? 'info');
}

function getTaskMetaText(row: TaskLogInfo): string {
  const parts = [];
  if (row.runKind) {
    parts.push(getRunKindText(row.runKind));
  }
  if (row.triggerSource) {
    parts.push(getTriggerSourceText(row.triggerSource));
  }
  return parts.join(' / ') || '-';
}

function getQueueMetaText(row: TaskLogInfo): string {
  const parts = [getTaskMetaText(row)];
  if (row.retryCount > 0) {
    parts.push(`${$t('admin.system.taskLog.retryCount')} ${row.retryCount}`);
  }
  return parts.join(' · ');
}

function getTaskRelationPrimaryText(row: TaskLogInfo): string {
  return getBindingContextText(row.bindingId);
}

function getTaskRelationSecondaryText(row: TaskLogInfo): string {
  const ownerText = getOwnerContextText(row.ownerTenantId, row.ownerTenantName);
  const effectiveText = getEffectiveContextText(
    row.effectiveTenantId,
    row.effectiveTenantName,
  );

  if (!ownerText || ownerText === effectiveText) {
    return effectiveText;
  }
  return `${ownerText} / ${effectiveText}`;
}

async function listTaskLogsApi(params?: TaskLogListParams) {
  return await admin.getTaskLogListApi({
    ...params,
    view: activeView.value,
  });
}

function onViewDetail(row: TaskLogInfo) {
  detailDrawerApi.setData({ id: row.id, mode: 'view' }).open();
}

async function onRetryTask(row: TaskLogInfo) {
  try {
    await admin.retryTaskApi(row.id);
    message.success($t('admin.system.taskLog.messages.retrySuccess'));
    await Promise.resolve(gridApi.reload({ page: 1 }));
  } catch {
    // handled by interceptor
  }
}

async function onChangeView(view: TaskLogListView) {
  if (activeView.value === view) {
    return;
  }
  activeView.value = view;
  await Promise.resolve(gridApi.reload({ page: 1 }));
}

const { Grid, gridApi } = useCrudPage<TaskLogInfo>({
  api: {
    list: listTaskLogsApi,
    resource: '/admin/tasks',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  search: {
    defaultOpen: false,
    quickSearch: {
      defaultField: 'filter[task_name][ilike]',
      fields: [
        'filter[task_name][ilike]',
        'filter[task_id][ilike]',
        'filter[handler_path][ilike]',
      ],
    },
  },
  i18nPrefix: 'admin.system.taskLog',
  nameField: 'taskName',
  defaultSort: '-created_at',
  rowHeight: 84,
  customActions: {
    detail: (row) => {
      onViewDetail(row);
    },
    retry: (row) => {
      void onRetryTask(row);
    },
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <DetailDrawerComp />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <template #toolbar-actions>
          <div class="flex flex-wrap items-center gap-2">
            <button
              v-for="view in viewOptions"
              :key="view.value"
              type="button"
              class="inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs font-medium transition-colors"
              :class="
                activeView === view.value
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border/60 bg-background text-muted-foreground hover:border-primary/40 hover:text-foreground'
              "
              @click="void onChangeView(view.value)"
            >
              <IconifyIcon :icon="view.icon" class="size-3.5" />
              {{ view.label }}
            </button>
          </div>
        </template>

        <template #taskName_cell="{ row }">
          <div class="flex min-w-0 flex-col gap-1 text-left">
            <Tooltip :title="row.taskName">
              <span class="truncate font-medium text-foreground">
                {{ getTaskShortName(row.handlerPath || row.taskName) }}
              </span>
            </Tooltip>
            <Tooltip :title="row.handlerPath || row.taskName">
              <code
                class="block truncate rounded bg-accent px-1.5 py-0.5 text-xs text-muted-foreground"
              >
                {{ row.handlerPath || row.taskName }}
              </code>
            </Tooltip>
            <Tooltip :title="getTaskRelationSecondaryText(row)">
              <span class="line-clamp-1 text-xs text-muted-foreground">
                {{ getTaskRelationPrimaryText(row) }} ·
                {{ getTaskRelationSecondaryText(row) }}
              </span>
            </Tooltip>
          </div>
        </template>

        <template #queue_cell="{ row }">
          <div class="flex flex-col gap-1 text-left">
            <Tag :color="getQueueColor(row.queue)" class="!m-0">
              {{ getQueueText(row.queue) }}
            </Tag>
            <Tooltip :title="getQueueMetaText(row)">
              <span class="line-clamp-1 text-[11px] text-muted-foreground">
                {{ getQueueMetaText(row) }}
              </span>
            </Tooltip>
          </div>
        </template>

        <template #status_cell="{ row }">
          <Tag :color="getStatusColor(row.status)" class="!m-0">
            {{ $t(`admin.system.taskLog.status.${row.status}`) }}
          </Tag>
        </template>

        <template #durationMs_cell="{ row }">
          <span
            :class="
              row.durationMs && row.durationMs > 5000
                ? 'font-medium text-warning'
                : 'text-muted-foreground'
            "
          >
            {{ formatDuration(row.durationMs) }}
          </span>
        </template>

        <template #result_cell="{ row }">
          <Tooltip v-if="getResultText(row)" :title="getResultText(row)">
            <span class="line-clamp-1 text-xs" :class="getResultTypeClass(row)">
              {{ getResultText(row) }}
            </span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.createdAt)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.createdAt) }}
            </span>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
