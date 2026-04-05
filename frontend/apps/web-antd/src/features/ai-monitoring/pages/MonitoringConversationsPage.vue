<script lang="ts" setup>
import type { MonitoringConversationInfo, MonitoringScope } from '../api';

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
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import { getMonitoringConversationList } from '../api';
import MonitoringConversationDrawer from './MonitoringConversationDrawer.vue';

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
  props.scope === 'admin'
    ? getAIProviderSelectApi
    : getTenantAIProviderSelectApi;
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

function actorTypeLabel(type?: null | string) {
  if (!type) {
    return '-';
  }
  const key = `${props.i18nPrefix}.actorType.${type}`;
  const translated = $t(key);
  return translated === key ? type : translated;
}

function getActorDisplayName(actor?: MonitoringConversationInfo['actor']) {
  if (!actor) {
    return '-';
  }
  return actor.display_name || actor.nickname || actor.username || '-';
}

function buildActorIdentityModel(actor?: MonitoringConversationInfo['actor']) {
  if (!actor) {
    return null;
  }

  return {
    avatar: actor.avatar,
    badges: actor.type
      ? [
          {
            color: 'blue',
            key: `actor-type-${actor.id ?? actor.username ?? 'unknown'}`,
            label: actorTypeLabel(actor.type),
          },
        ]
      : [],
    displayName: actor.display_name,
    id: actor.id ?? '-',
    isActive: actor.is_active,
    isLeader: actor.is_leader,
    isOwner: actor.is_owner,
    nickname: getActorDisplayName(actor),
    orgNodeName: actor.org_node_name,
    roleName: actor.role_name,
    username: actor.display_name || actor.nickname ? undefined : actor.username,
  };
}

function buildActorMeta(row: MonitoringConversationInfo): IdentityDetailMeta {
  return {
    orgNodeName: row.actor?.org_node_name,
    roleName: row.actor?.role_name,
    scope: props.scope,
    subjectType: row.actor?.type,
    tenantName: row.tenant_name,
    userType: row.actor?.type,
    username:
      row.actor?.username ||
      row.actor?.display_name ||
      row.actor?.nickname ||
      undefined,
  };
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
  rowHeight: 72,
  customActions: {
    detail: viewDetail,
  },
  ai: {
    entityName: props.title,
    entityDescription: props.title,
    extra: [
      createViewDetailPageOperation({
        description: 'Open conversation detail drawer / 打开对话详情抽屉',
        idDescription: 'Conversation ID / 对话 ID',
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
                :alt="getConversationAgentName(row)"
                :src="toAvatarDisplayUrl(row.agent_avatar)"
                class="size-full object-cover"
              />
              <span v-else class="text-sm font-semibold">
                {{ getConversationAgentName(row).charAt(0).toUpperCase() }}
              </span>
            </div>
            <div class="min-w-0">
              <div class="truncate text-sm font-medium text-foreground">
                {{ getConversationAgentName(row) }}
              </div>
              <div class="truncate text-xs text-muted-foreground">
                #{{ row.id }}
              </div>
            </div>
          </div>
        </template>
        <template #title_cell="{ row }">
          <div class="min-w-0">
            <div class="line-clamp-2 text-sm font-medium text-foreground">
              {{ row.title || $t(`${i18nPrefix}.untitled`) }}
            </div>
            <div class="truncate text-xs text-muted-foreground">
              {{
                row.last_call_at ? formatRelativeTime(row.last_call_at) : '-'
              }}
            </div>
          </div>
        </template>

        <template #tenant_cell="{ row }">
          <span class="truncate text-sm text-foreground">{{
            row.tenant_name || '-'
          }}</span>
        </template>

        <template #actor_cell="{ row }">
          <IdentityTrigger
            v-if="row.actor"
            :model="buildActorIdentityModel(row.actor)!"
            :meta="buildActorMeta(row)"
          />
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <template #status_cell="{ row }">
          <Tag :color="row.status === 'active' ? 'success' : 'default'">
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <template #tokens_cell="{ row }">
          <span class="font-mono text-sm text-muted-foreground">
            {{ formatTokens(row.total_tokens) }}
          </span>
        </template>

        <template #cost_cell="{ row }">
          <span class="font-mono text-sm text-muted-foreground">
            {{ formatCost(row.total_cost) }}
          </span>
        </template>

        <template #lastCall_cell="{ row }">
          <Tooltip
            :title="row.last_call_at ? formatDate(row.last_call_at) : '-'"
          >
            <span class="text-muted-foreground">
              {{
                row.last_call_at ? formatRelativeTime(row.last_call_at) : '-'
              }}
            </span>
          </Tooltip>
        </template>

        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.created_at) }}
            </span>
          </Tooltip>
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
