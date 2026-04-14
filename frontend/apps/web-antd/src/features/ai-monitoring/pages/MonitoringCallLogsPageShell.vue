<script lang="ts" setup>
import type { MonitoringCallLogInfo, MonitoringScope } from '../api';

import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';

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
import { $t } from '#/locales';

import { getMonitoringCallLogList } from '../api';
import MonitoringCallLogDrawer from './MonitoringCallLogDrawer.vue';
import MonitoringCallLogsGridCard from './monitoring-call-log/MonitoringCallLogsGridCard.vue';

const props = defineProps<{
  i18nPrefix: string;
  permissionResource: string;
  resource: string;
  scope: MonitoringScope;
  showTenantColumn?: boolean;
  title: string;
}>();

const MONITORING_CARD_BODY_STYLE = {
  height: '100%',
  padding: '12px',
};
const MONITORING_ROW_HEIGHT = 64;

const detailOpen = ref(false);
const detailId = ref<null | number>(null);
const providerSelectApi =
  props.scope === 'admin'
    ? getAIProviderSelectApi
    : getTenantAIProviderSelectApi;
const modelSelectApi =
  props.scope === 'admin' ? getAIModelSelectApi : getTenantAIModelSelectApi;
const agentSelectApi =
  props.scope === 'admin' ? getAIAgentSelectApi : getTenantAgentSelectApi;

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
  rowHeight: MONITORING_ROW_HEIGHT,
  customActions: {
    detail: viewDetail,
  },
});
</script>

<template>
  <Page
    auto-content-height
    content-class="monitoring-page flex flex-col gap-4 !p-4"
  >
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

    <MonitoringCallLogsGridCard
      :body-style="MONITORING_CARD_BODY_STYLE"
      :grid-component="Grid"
      :i18n-prefix="i18nPrefix"
      :scope="scope"
    />
  </Page>
</template>

<style scoped>
.monitoring-grid :deep(.vxe-body--row .vxe-cell) {
  padding-top: 6px;
  padding-bottom: 6px;
}
</style>
