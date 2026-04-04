<script lang="ts" setup>
import type { MonitoringCallLogInfo, MonitoringScope } from '../api';

import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Tag, Tooltip } from 'ant-design-vue';

import { searchDateRange, searchInput, select } from '#/adapter/form';
import { useCrudPage } from '#/adapter/vxe-table';
import { getAIAgentSelectApi } from '#/api/admin/ai-agents';
import { getAIModelSelectApi } from '#/api/admin/ai-models';
import { getAIProviderSelectApi } from '#/api/admin/ai-providers';
import { getTenantAgentSelectApi } from '#/api/tenant/agents';
import {
  getTenantAIModelSelectApi,
  getTenantAIProviderSelectApi,
} from '#/api/tenant/ai';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { createViewDetailPageOperation } from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

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
const providerSelectApi =
  props.scope === 'admin' ? getAIProviderSelectApi : getTenantAIProviderSelectApi;
const modelSelectApi =
  props.scope === 'admin' ? getAIModelSelectApi : getTenantAIModelSelectApi;
const agentSelectApi =
  props.scope === 'admin' ? getAIAgentSelectApi : getTenantAgentSelectApi;

function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

function getStatusText(status?: null | string) {
  if (!status) {
    return '-';
  }
  const key = `${props.i18nPrefix}.status_options.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

function getAgentDisplayName(row: MonitoringCallLogInfo) {
  if (row.agent_name) {
    return row.agent_name;
  }
  if (row.agent_id) {
    return `#${row.agent_id}`;
  }
  return '-';
}

function onProviderChange(providerId: null | number | string | undefined) {
  gridApi.formApi?.setValues({
    'filter[model_id][eq]': undefined,
  });
  gridApi.formApi?.updateSchema([
    {
      componentProps: {
        disabled: !providerId,
        params: providerId ? { provider_id: Number(providerId) } : {},
      },
      fieldName: 'filter[model_id][eq]',
    },
  ]);
}

const searchSchema = [
  searchInput('agent_name', $t(`${props.i18nPrefix}.agentName`), {
    placeholder: $t(`${props.i18nPrefix}.placeholder.searchAgentName`),
  }),
  searchInput('trace_id', $t(`${props.i18nPrefix}.traceId`), {
    placeholder: $t(`${props.i18nPrefix}.placeholder.searchTrace`),
  }),
  searchInput('conversation_id', $t(`${props.i18nPrefix}.conversationId`), {
    op: 'eq',
    placeholder: $t(`${props.i18nPrefix}.placeholder.searchConversation`),
  }),
  select('filter[provider_id][eq]', $t(`${props.i18nPrefix}.providerName`), {
    api: providerSelectApi,
    componentProps: {
      onChange: onProviderChange,
    },
    extraField: 'code',
    placeholder: $t(`${props.i18nPrefix}.placeholder.selectProvider`),
  }),
  select('filter[model_id][eq]', $t(`${props.i18nPrefix}.modelName`), {
    api: modelSelectApi,
    componentProps: {
      disabled: true,
    },
    extraField: 'code',
    placeholder: $t(`${props.i18nPrefix}.placeholder.selectModel`),
  }),
  select('filter[agent_id][eq]', $t(`${props.i18nPrefix}.agentName`), {
    api: agentSelectApi,
    extraField: 'scope',
    placeholder: $t(`${props.i18nPrefix}.placeholder.selectAgent`),
  }),
  select('filter[status][eq]', $t(`${props.i18nPrefix}.status`), {
    options: [
      {
        label: $t(`${props.i18nPrefix}.status_options.success`),
        value: 'success',
      },
      {
        label: $t(`${props.i18nPrefix}.status_options.failed`),
        value: 'failed',
      },
      {
        label: $t(`${props.i18nPrefix}.status_options.timeout`),
        value: 'timeout',
      },
    ],
    placeholder: $t(`${props.i18nPrefix}.placeholder.allStatuses`),
  }),
  searchDateRange({
    field: 'created_at',
    label: $t(`${props.i18nPrefix}.createdAt`),
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
  {
    key: 'filters',
    icon: 'lucide:sliders-horizontal',
    className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
    text: `${$t(`${props.i18nPrefix}.providerName`)} / ${$t(`${props.i18nPrefix}.modelName`)} / ${$t(`${props.i18nPrefix}.agentName`)}`,
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
  const base: any[] = [
    {
      field: 'created_at',
      title: $t(`${props.i18nPrefix}.createdAt`),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      field: 'agent_name',
      title: $t(`${props.i18nPrefix}.agentName`),
      minWidth: 220,
      slots: { default: 'agent_cell' },
    },
    {
      field: 'model_name',
      title: $t(`${props.i18nPrefix}.modelName`),
      minWidth: 180,
      slots: { default: 'model_cell' },
    },
    {
      field: 'provider_name',
      title: $t(`${props.i18nPrefix}.providerName`),
      minWidth: 160,
      slots: { default: 'provider_cell' },
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
      minWidth: 180,
      slots: { default: 'caller_cell' },
    },
    {
      field: 'request_type',
      title: $t(`${props.i18nPrefix}.requestType`),
      width: 110,
      slots: { default: 'requestType_cell' },
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

const { Grid, gridApi } = useCrudPage<MonitoringCallLogInfo>({
  api: {
    list: (params) => getMonitoringCallLogList(props.scope, params),
    resource: props.resource,
  },
  columns: () => columns.value,
  searchSchema,
  search: {
    defaultOpen: false,
    quickSearch: {
      defaultField: 'filter[agent_name][ilike]',
      fields: [
        'filter[agent_name][ilike]',
        'filter[trace_id][ilike]',
        'filter[conversation_id]',
      ],
    },
  },
  i18nPrefix: props.i18nPrefix,
  defaultSort: '-created_at',
  rowHeight: 72,
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
  <Page auto-content-height content-class="monitoring-page flex flex-col gap-4 !p-4">
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
      <Grid class="monitoring-grid">
        <template #agent_cell="{ row }">
          <div class="flex items-center gap-3 py-0.5">
            <div
              class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-primary/10 text-primary shadow-sm"
            >
              <IconifyIcon
                v-if="isIconAvatar(row.agent_avatar)"
                :icon="String(row.agent_avatar)"
                class="size-4.5"
              />
              <img
                v-else-if="row.agent_avatar"
                :alt="getAgentDisplayName(row)"
                :src="toAvatarDisplayUrl(row.agent_avatar)"
                class="size-full object-cover"
              />
              <span v-else class="text-sm font-semibold">
                {{ getAgentDisplayName(row).charAt(0).toUpperCase() }}
              </span>
            </div>
            <div class="min-w-0">
              <div class="truncate text-sm font-medium text-foreground">
                {{ getAgentDisplayName(row) }}
              </div>
              <div class="truncate text-xs text-muted-foreground">
                {{ row.conversation_id ? `#${row.conversation_id}` : '-' }}
              </div>
            </div>
          </div>
        </template>
        <template #model_cell="{ row }">
          <div class="min-w-0">
            <div class="truncate font-medium text-foreground">
              {{ row.model_name || '-' }}
            </div>
            <div class="text-xs text-muted-foreground">
              {{ Number(row.total_tokens ?? 0).toLocaleString() }}
              {{ $t(`${i18nPrefix}.totalTokens`) }}
            </div>
          </div>
        </template>
        <template #provider_cell="{ row }">
          <div class="flex items-center gap-2">
            <span
              class="inline-flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted/70 text-muted-foreground"
            >
              <IconifyIcon icon="lucide:cpu" class="size-3.5" />
            </span>
            <span class="truncate text-sm text-foreground">{{
              row.provider_name || '-'
            }}</span>
          </div>
        </template>
        <template #caller_cell="{ row }">
          <div class="min-w-0">
            <div class="truncate text-sm text-foreground">
              {{ row.caller_name || '-' }}
            </div>
            <div class="truncate text-xs text-muted-foreground">
              {{ row.tenant_name || '-' }}
            </div>
          </div>
        </template>
        <template #requestType_cell="{ row }">
          <Tag color="blue">
            {{ row.request_type }}
          </Tag>
        </template>
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.created_at) }}
            </span>
          </Tooltip>
        </template>
        <template #status_cell="{ row }">
          <Tag
            :color="
              row.status === 'success'
                ? 'success'
                : row.status === 'timeout'
                  ? 'warning'
                  : 'error'
            "
          >
            {{ getStatusText(row.status) }}
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

<style scoped>
.monitoring-grid :deep(.vxe-body--row .vxe-cell) {
  padding-top: 10px;
  padding-bottom: 10px;
}
</style>
