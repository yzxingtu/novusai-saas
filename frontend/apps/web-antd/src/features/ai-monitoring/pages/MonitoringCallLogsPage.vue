<script lang="ts" setup>
import type { MonitoringCallLogInfo, MonitoringScope } from '../api';

import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { Card, Tag, Tooltip } from 'ant-design-vue';

import { searchInput, select } from '#/adapter/form';
import { useCrudPage } from '#/adapter/vxe-table';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { createViewDetailPageOperation } from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { getMonitoringCallLogList } from '../api';
import MonitoringCallLogDrawer from './MonitoringCallLogDrawer.vue';

const props = defineProps<{
  i18nPrefix: string;
  permissionResource: string;
  resource: string;
  scope: MonitoringScope;
  showTenantColumn?: boolean;
  title: string;
}>();

const detailOpen = ref(false);
const detailId = ref<null | number>(null);
const searchSchema = [
  searchInput('filter[model_name][ilike]', $t(`${props.i18nPrefix}.modelName`)),
  searchInput('filter[conversation_id][eq]', 'Conversation ID'),
  select('filter[status][eq]', $t(`${props.i18nPrefix}.status`), {
    options: [
      { label: 'success', value: 'success' },
      { label: 'failed', value: 'failed' },
    ],
  }),
];

const heroChips = computed(() => [
  {
    key: 'focus',
    icon: 'lucide:file-search',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t(`${props.i18nPrefix}.modelName`)} / ${$t(`${props.i18nPrefix}.providerName`)} / ${$t(`${props.i18nPrefix}.status`)}`,
  },
  {
    key: 'metrics',
    icon: 'lucide:scan-search',
    className: 'bg-background/90 text-foreground',
    text: `${$t(`${props.i18nPrefix}.totalTokens`)} / ${$t(`${props.i18nPrefix}.cost`)} / ${$t(`${props.i18nPrefix}.latency`)}`,
  },
]);

function viewDetail(row: MonitoringCallLogInfo) {
  detailId.value = row.id;
  detailOpen.value = true;
}

function handleOperationClick(payload: { row: MonitoringCallLogInfo }) {
  if (!payload?.row) {
    return;
  }
  viewDetail(payload.row);
}

function formatCost(cost?: null | number) {
  return `$${Number(cost || 0).toFixed(4)}`;
}

const columns = computed(() => {
  const base = [
    {
      field: 'created_at',
      title: $t(`${props.i18nPrefix}.createdAt`),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      field: 'model_name',
      title: $t(`${props.i18nPrefix}.modelName`),
      minWidth: 140,
    },
    {
      field: 'provider_name',
      title: $t(`${props.i18nPrefix}.providerName`),
      minWidth: 120,
    },
  ];
  if (props.showTenantColumn) {
    base.push({
      field: 'tenant_name',
      title: $t(`${props.i18nPrefix}.tenantName`),
      minWidth: 140,
    });
  }
  return [
    ...base,
    {
      field: 'caller_name',
      title: $t(`${props.i18nPrefix}.callerName`) || 'caller',
      minWidth: 140,
    },
    {
      field: 'request_type',
      title: $t(`${props.i18nPrefix}.requestType`),
      width: 110,
    },
    {
      field: 'status',
      title: $t(`${props.i18nPrefix}.status`),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'total_tokens',
      title: $t(`${props.i18nPrefix}.totalTokens`),
      width: 120,
      align: 'right',
    },
    {
      field: 'cost',
      title: $t(`${props.i18nPrefix}.cost`),
      width: 110,
      align: 'right',
      slots: { default: 'cost_cell' },
    },
    {
      field: 'latency_ms',
      title: $t(`${props.i18nPrefix}.latency`),
      width: 110,
      align: 'right',
    },
    {
      align: 'center',
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 100,
      cellRender: {
        name: 'CellOperation',
        attrs: {
          resource: props.permissionResource,
          nameField: 'id',
          nameTitle: 'ID',
          onClick: handleOperationClick,
        },
        options: [
          {
            code: 'detail',
            text: $t(`${props.i18nPrefix}.viewDetail`),
            icon: 'lucide:eye',
            accessCodes: [`${props.permissionResource}:detail`],
          },
        ],
      },
    },
  ];
});

const { Grid } = useCrudPage<MonitoringCallLogInfo>({
  api: {
    list: (params) => getMonitoringCallLogList(props.scope, params),
    resource: props.resource,
  },
  columns: () => columns.value,
  searchSchema,
  i18nPrefix: props.i18nPrefix,
  defaultSort: '-created_at',
  customActions: {
    detail: viewDetail,
  },
  ai: {
    entityName: props.title,
    entityDescription: props.title,
    extra: [
      createViewDetailPageOperation({
        description: 'Open call log detail drawer / 打开调用日志详情抽屉',
        idDescription: 'Call log ID / 调用日志 ID',
        openDetail: async (id) => {
          detailId.value = id;
          detailOpen.value = true;
          return null;
        },
      }),
    ],
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t(`${i18nPrefix}.pageDesc`)"
      icon="lucide:file-search"
      icon-wrap-class="bg-primary/10 text-primary"
      :title="title"
    />

    <MonitoringCallLogDrawer
      v-model:open="detailOpen"
      :i18n-prefix="i18nPrefix"
      :log-id="detailId"
      :scope="scope"
    />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.created_at) }}
            </span>
          </Tooltip>
        </template>
        <template #status_cell="{ row }">
          <Tag :color="row.status === 'success' ? 'success' : 'error'">
            {{ row.status }}
          </Tag>
        </template>
        <template #cost_cell="{ row }">
          <span class="font-mono text-sm text-muted-foreground">{{
            formatCost(row.cost)
          }}</span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
