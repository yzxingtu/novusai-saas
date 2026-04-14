<script lang="ts" setup>
import type { MonitoringConversationInfo, MonitoringScope } from '../api';

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

import { getMonitoringConversationList } from '../api';
import MonitoringConversationDrawer from './MonitoringConversationDrawer.vue';
import MonitoringConversationsGridCard from './monitoring-conversation/MonitoringConversationsGridCard.vue';

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

function getStatusText(status?: null | string) {
  if (!status) {
    return '-';
  }
  const key = `${props.i18nPrefix}.status_options.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

function getConversationAgentName(row: MonitoringConversationInfo) {
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
  searchInput('title', $t(`${props.i18nPrefix}.conversationTitle`), {
    placeholder: $t(`${props.i18nPrefix}.placeholder.searchTitle`),
  }),
  searchInput('id', $t(`${props.i18nPrefix}.conversationId`), {
    op: 'eq',
    placeholder: $t(`${props.i18nPrefix}.placeholder.searchConversationId`),
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
        label: $t(`${props.i18nPrefix}.status_options.active`),
        value: 'active',
      },
      {
        label: $t(`${props.i18nPrefix}.status_options.archived`),
        value: 'archived',
      },
      {
        label: $t(`${props.i18nPrefix}.status_options.closed`),
        value: 'closed',
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
    key: 'scope',
    icon: 'lucide:messages-square',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t(`${props.i18nPrefix}.agentName`)} / ${$t(`${props.i18nPrefix}.user`)} / ${$t(`${props.i18nPrefix}.title`)}`,
  },
  {
    key: 'monitoring',
    icon: 'lucide:chart-column-big',
    className: 'bg-background/90 text-foreground',
    text: `${$t(`${props.i18nPrefix}.messageCount`)} / ${$t(`${props.i18nPrefix}.tokenCount`)} / ${$t(`${props.i18nPrefix}.cost`)}`,
  },
  {
    key: 'filters',
    icon: 'lucide:sliders-horizontal',
    className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
    text: `${$t(`${props.i18nPrefix}.providerName`)} / ${$t(`${props.i18nPrefix}.modelName`)} / ${$t(`${props.i18nPrefix}.status`)}`,
  },
]);

function formatTokens(tokens?: null | number) {
  return Number(tokens || 0).toLocaleString();
}

function formatCost(cost?: null | number) {
  return `$${Number(cost || 0).toFixed(4)}`;
}

function viewDetail(row: MonitoringConversationInfo) {
  detailId.value = row.id;
  detailOpen.value = true;
}

function handleOperationClick(payload: { row: MonitoringConversationInfo }) {
  if (!payload?.row) {
    return;
  }
  viewDetail(payload.row);
}

const columns = computed(() => {
  const base: any[] = [
    { field: 'id', title: 'ID', width: 90, sortable: true },
    {
      field: 'agent_name',
      title: $t(`${props.i18nPrefix}.agentName`),
      minWidth: 210,
      slots: { default: 'agent_cell' },
    },
    {
      field: 'title',
      title: $t(`${props.i18nPrefix}.title`),
      minWidth: 220,
      slots: { default: 'title_cell' },
    },
  ];

  if (props.showTenantColumn) {
    base.push({
      field: 'tenant_name',
      title: $t(`${props.i18nPrefix}.tenantName`),
      minWidth: 140,
      slots: { default: 'tenant_cell' },
    });
  }

  return [
    ...base,
    {
      field: 'actor',
      title: $t(`${props.i18nPrefix}.user`),
      minWidth: 180,
      slots: { default: 'actor_cell' },
    },
    {
      field: 'status',
      title: $t(`${props.i18nPrefix}.status`),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'message_count',
      title: $t(`${props.i18nPrefix}.messageCount`),
      width: 110,
      align: 'right',
    },
    {
      field: 'call_count',
      title: $t(`${props.i18nPrefix}.totalCalls`),
      width: 100,
      align: 'right',
    },
    {
      field: 'total_tokens',
      title: $t(`${props.i18nPrefix}.tokenCount`),
      width: 130,
      align: 'right',
      slots: { default: 'tokens_cell' },
    },
    {
      field: 'total_cost',
      title: $t(`${props.i18nPrefix}.cost`),
      width: 120,
      align: 'right',
      slots: { default: 'cost_cell' },
    },
    {
      field: 'last_call_at',
      title: $t(`${props.i18nPrefix}.lastCallAt`),
      width: 170,
      slots: { default: 'lastCall_cell' },
    },
    {
      field: 'created_at',
      title: $t(`${props.i18nPrefix}.createdAt`),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
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
          nameField: 'title',
          nameTitle: $t(`${props.i18nPrefix}.title`),
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

const { Grid, gridApi } = useCrudPage<MonitoringConversationInfo>({
  api: {
    list: (params) => getMonitoringConversationList(props.scope, params),
    resource: props.resource,
  },
  columns: () => columns.value,
  searchSchema,
  search: {
    defaultOpen: false,
    quickSearch: {
      defaultField: 'filter[title][ilike]',
      fields: ['filter[title][ilike]', 'filter[id]'],
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
      icon="lucide:messages-square"
      icon-wrap-class="bg-primary/10 text-primary"
      :title="title"
    />

    <MonitoringConversationDrawer
      v-model:open="detailOpen"
      :conversation-id="detailId"
      :i18n-prefix="i18nPrefix"
      :scope="scope"
    />

    <MonitoringConversationsGridCard
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
