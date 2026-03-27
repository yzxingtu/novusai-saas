<script lang="ts" setup>
import type { MonitoringConversationInfo, MonitoringScope } from '../api';

import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { Avatar, Card, Tag, Tooltip } from 'ant-design-vue';

import { searchInput, select } from '#/adapter/form';
import { useCrudPage } from '#/adapter/vxe-table';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { createViewDetailPageOperation } from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

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
const searchSchema = [
  searchInput('filter[title][ilike]', $t(`${props.i18nPrefix}.title`)),
  searchInput('filter[agent_id][eq]', $t(`${props.i18nPrefix}.agentName`)),
  select('filter[status][eq]', $t(`${props.i18nPrefix}.status`), {
    options: [
      { label: 'active', value: 'active' },
      { label: 'archived', value: 'archived' },
      { label: 'closed', value: 'closed' },
    ],
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
  const base = [
    { field: 'id', title: 'ID', width: 90, sortable: true },
    {
      field: 'agent_name',
      title: $t(`${props.i18nPrefix}.agentName`),
      minWidth: 150,
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

const { Grid } = useCrudPage<MonitoringConversationInfo>({
  api: {
    list: (params) => getMonitoringConversationList(props.scope, params),
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
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
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
      <Grid>
        <template #title_cell="{ row }">
          <span>{{ row.title || '-' }}</span>
        </template>

        <template #tenant_cell="{ row }">
          <span>{{ row.tenant_name || '-' }}</span>
        </template>

        <template #actor_cell="{ row }">
          <div v-if="row.actor" class="flex items-center gap-2">
            <Avatar
              v-if="row.actor.avatar"
              :src="toAvatarDisplayUrl(row.actor.avatar)"
              :size="24"
            />
            <span>{{
              row.actor.display_name || row.actor.username || '-'
            }}</span>
            <Tag v-if="row.actor.type" color="blue">
              {{ actorTypeLabel(row.actor.type) }}
            </Tag>
          </div>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <template #status_cell="{ row }">
          <Tag :color="row.status === 'active' ? 'success' : 'default'">
            {{ row.status }}
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
