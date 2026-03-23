<script lang="ts" setup>
import type {
  AdminReleaseListQuery,
  WorkflowReleaseSummary,
} from '../../../types/admin';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  InputNumber,
  Modal,
  Pagination,
  Select,
  Table,
  Tag,
  Tooltip,
  message,
} from 'ant-design-vue';

import { listAdminReleasesApi, rollbackAdminReleaseApi } from '../../../api/admin';
import { formatCompactNumber, formatDateTime } from '../shared/format';
import { usePaginatedCollection } from '../shared/use-paginated-collection';

import {
  getReleaseChannelOptions,
  getReleaseChannelText,
  getReleaseEnvironmentColor,
  getReleaseEnvironmentText,
  getReleaseScopeOptions,
  getReleaseScopeText,
  getReleaseStatusColor,
  getReleaseStatusOptions,
  getReleaseStatusText,
} from './data';

import { ADMIN_I18N_PREFIX } from '../shared/constants';
import { $t } from '@novus/plugin-shared';

defineOptions({ name: 'WorkflowOrchestrationAdminReleases' });

const keyword = ref('');
const environmentCode = ref('');
const workflowIdInput = ref<null | number>(null);
const rollingBackId = ref<null | number>(null);

const collection = usePaginatedCollection<
  WorkflowReleaseSummary,
  Omit<AdminReleaseListQuery, 'page' | 'pageSize'>
>({
  initialPageSize: 10,
  initialQuery: {
    channel: '',
    environmentCode: '',
    keyword: '',
    releaseScope: '',
    sort: '-published_at',
    status: '',
    workflowId: undefined,
  },
  loader: ({ page, pageSize, query }) =>
    listAdminReleasesApi({
      ...query,
      page,
      pageSize,
    }),
});

const statusOptions = computed(() => getReleaseStatusOptions());
const releaseScopeOptions = computed(() => getReleaseScopeOptions());
const channelOptions = computed(() => getReleaseChannelOptions());

const visibleItems = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase();
  if (!normalizedKeyword) {
    return collection.items.value;
  }

  return collection.items.value.filter((item) =>
    [
      item.workflow_name,
      item.workflow_code,
      item.code,
      item.environment_code,
      item.workflow_version_id,
    ]
      .filter((value) => value !== null && value !== undefined)
      .some((value) => String(value).toLowerCase().includes(normalizedKeyword)),
  );
});

const tableColumns = computed(() => [
  {
    title: $t(`${ADMIN_I18N_PREFIX}.releases.table.workflowName`),
    dataIndex: 'workflow_name',
    key: 'workflow_name',
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.releases.table.releaseCode`),
    dataIndex: 'code',
    key: 'code',
    width: 180,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.status`),
    dataIndex: 'status',
    key: 'status',
    width: 150,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.environment`),
    dataIndex: 'environment_code',
    key: 'environment_code',
    width: 160,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.releaseScopeLabel`),
    dataIndex: 'release_scope',
    key: 'release_scope',
    width: 180,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.channelLabel`),
    dataIndex: 'channel',
    key: 'channel',
    width: 140,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.publishedAt`),
    dataIndex: 'published_at',
    key: 'published_at',
    width: 180,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.releases.table.notes`),
    dataIndex: 'notes',
    key: 'notes',
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.action`),
    key: 'action',
    width: 160,
    fixed: 'right',
  },
]);

const summaryCards = computed(() => {
  const items = visibleItems.value;
  return [
    {
      key: 'total',
      icon: 'lucide:rocket',
      label: $t(`${ADMIN_I18N_PREFIX}.releases.stats.total`),
      value: formatCompactNumber(collection.total.value),
    },
    {
      key: 'published',
      icon: 'lucide:badge-check',
      label: $t(`${ADMIN_I18N_PREFIX}.releases.stats.published`),
      value: formatCompactNumber(
        items.filter((item) => item.status === 'published').length,
      ),
    },
    {
      key: 'rolledBack',
      icon: 'lucide:undo-2',
      label: $t(`${ADMIN_I18N_PREFIX}.releases.stats.rolledBack`),
      value: formatCompactNumber(
        items.filter((item) => item.status === 'rolled_back').length,
      ),
    },
    {
      key: 'environments',
      icon: 'lucide:layers-2',
      label: $t(`${ADMIN_I18N_PREFIX}.releases.stats.environments`),
      value: formatCompactNumber(
        new Set(
          items
            .map((item) => item.environment_code)
            .filter((item): item is string => Boolean(item)),
        ).size,
      ),
    },
  ];
});

async function applyFilters() {
  await collection.patchQuery({
    channel: collection.query.value.channel,
    environmentCode: environmentCode.value,
    releaseScope: collection.query.value.releaseScope,
    status: collection.query.value.status,
    workflowId: workflowIdInput.value ?? undefined,
  });
}

async function handlePaginationChange(page: number, pageSize: number) {
  if (pageSize !== collection.pageSize.value) {
    await collection.setPageSize(pageSize);
    return;
  }

  await collection.setPage(page);
}

function confirmRollback(record: WorkflowReleaseSummary) {
  Modal.confirm({
    title: $t(`${ADMIN_I18N_PREFIX}.releases.rollback.confirmTitle`),
    content: $t(`${ADMIN_I18N_PREFIX}.releases.rollback.confirmContent`, {
      name:
        record.workflow_name
        || record.code
        || $t(`${ADMIN_I18N_PREFIX}.common.unknown`),
      version: record.workflow_version_id ? `#${record.workflow_version_id}` : '--',
    }),
    onOk: async () => {
      rollingBackId.value = record.id;
      try {
        await rollbackAdminReleaseApi(record.id);
        message.success($t(`${ADMIN_I18N_PREFIX}.releases.rollback.success`));
        await collection.load();
      } finally {
        rollingBackId.value = null;
      }
    },
  });
}

onMounted(() => {
  keyword.value = collection.query.value.keyword ?? '';
  environmentCode.value = collection.query.value.environmentCode ?? '';
  workflowIdInput.value = collection.query.value.workflowId ?? null;
  void collection.load();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <section class="relative overflow-hidden rounded-2xl border bg-card shadow-sm">
      <div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-primary/5" />
      <div class="relative flex flex-col gap-4 p-5">
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div
              class="mb-2 inline-flex items-center gap-2 rounded-full border bg-background/85 px-3 py-1 text-xs text-muted-foreground"
            >
              <IconifyIcon icon="lucide:rocket" class="h-3.5 w-3.5" />
              {{ $t(`${ADMIN_I18N_PREFIX}.releases.badge`) }}
            </div>
            <h1 class="text-xl font-semibold text-foreground md:text-2xl">
              {{ $t(`${ADMIN_I18N_PREFIX}.releases.title`) }}
            </h1>
            <p class="mt-1 text-sm text-muted-foreground">
              {{ $t(`${ADMIN_I18N_PREFIX}.releases.subtitle`) }}
            </p>
          </div>

          <Button :loading="collection.loading.value" @click="collection.load">
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" />
            </template>
            {{ $t(`${ADMIN_I18N_PREFIX}.common.refresh`) }}
          </Button>
        </div>

        <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div
            v-for="card in summaryCards"
            :key="card.key"
            class="rounded-xl border bg-background/85 p-3"
          >
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <IconifyIcon :icon="card.icon" class="h-3.5 w-3.5" />
              {{ card.label }}
            </div>
            <div class="mt-2 text-lg font-semibold text-foreground">
              {{ card.value }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <Alert
      :message="$t(`${ADMIN_I18N_PREFIX}.releases.contractNotice.title`)"
      :description="$t(`${ADMIN_I18N_PREFIX}.releases.contractNotice.description`)"
      show-icon
      type="info"
    />

    <Card :body-style="{ padding: '18px' }">
      <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Input
            v-model:value="keyword"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.releases.filters.searchPlaceholder`)"
            allow-clear
            class="min-w-[220px]"
            @press-enter="applyFilters"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:search" class="h-4 w-4 text-muted-foreground" />
            </template>
          </Input>

          <Select
            :value="collection.query.value.status"
            :options="statusOptions"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.releases.filters.allStatuses`)"
            allow-clear
            class="min-w-[180px]"
            @change="(value) => collection.patchQuery({ status: typeof value === 'string' ? value : '' })"
          />

          <Select
            :value="collection.query.value.releaseScope"
            :options="releaseScopeOptions"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.releases.filters.allScopes`)"
            allow-clear
            class="min-w-[180px]"
            @change="(value) => collection.patchQuery({ releaseScope: typeof value === 'string' ? value : '' })"
          />

          <Select
            :value="collection.query.value.channel"
            :options="channelOptions"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.releases.filters.allChannels`)"
            allow-clear
            class="min-w-[180px]"
            @change="(value) => collection.patchQuery({ channel: typeof value === 'string' ? value : '' })"
          />

          <Input
            v-model:value="environmentCode"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.releases.filters.environmentPlaceholder`)"
            allow-clear
            class="min-w-[180px]"
            @press-enter="applyFilters"
          />

          <InputNumber
            v-model:value="workflowIdInput"
            :min="1"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.releases.filters.workflowIdPlaceholder`)"
            class="w-full min-w-[180px]"
          />
        </div>

        <Button type="primary" @click="applyFilters">
          <template #icon>
            <IconifyIcon icon="lucide:filter" />
          </template>
          {{ $t(`${ADMIN_I18N_PREFIX}.releases.filters.apply`) }}
        </Button>
      </div>
    </Card>

    <Card :body-style="{ padding: '0' }">
      <Table
        :columns="tableColumns"
        :data-source="visibleItems"
        :loading="collection.loading.value"
        :pagination="false"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'workflow_name'">
            <div class="space-y-1">
              <div class="text-sm font-medium text-foreground">
                {{ record.workflow_name || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{
                  record.workflow_version_id
                    ? `version #${record.workflow_version_id}`
                    : $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`)
                }}
              </div>
            </div>
          </template>

          <template v-else-if="column.key === 'code'">
            <span class="font-mono text-sm text-foreground">
              {{ record.code || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
            </span>
          </template>

          <template v-else-if="column.key === 'status'">
            <Tag :color="getReleaseStatusColor(record.status)">
              {{ getReleaseStatusText(record.status) }}
            </Tag>
          </template>

          <template v-else-if="column.key === 'environment_code'">
            <Tag :color="getReleaseEnvironmentColor(record.environment_code)">
              {{ getReleaseEnvironmentText(record.environment_code) }}
            </Tag>
          </template>

          <template v-else-if="column.key === 'release_scope'">
            <span class="text-sm text-foreground">
              {{ getReleaseScopeText(record.release_scope) }}
            </span>
          </template>

          <template v-else-if="column.key === 'channel'">
            <span class="text-sm text-foreground">
              {{ getReleaseChannelText(record.channel) }}
            </span>
          </template>

          <template v-else-if="column.key === 'published_at'">
            <Tooltip :title="formatDateTime(record.published_at || record.created_at)">
              <span class="text-sm text-muted-foreground">
                {{ formatDateTime(record.published_at || record.created_at) }}
              </span>
            </Tooltip>
          </template>

          <template v-else-if="column.key === 'notes'">
            <span class="line-clamp-2 text-sm leading-6 text-muted-foreground">
              {{
                record.notes
                || $t(`${ADMIN_I18N_PREFIX}.common.noDescription`)
              }}
            </span>
          </template>

          <template v-else-if="column.key === 'action'">
            <Button
              type="link"
              size="small"
              :loading="rollingBackId === record.id"
              @click="confirmRollback(record)"
            >
              {{ $t(`${ADMIN_I18N_PREFIX}.common.rollback`) }}
            </Button>
          </template>
        </template>

        <template #emptyText>
          <div class="py-10">
            <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
          </div>
        </template>
      </Table>

      <div class="flex justify-end border-t px-4 py-4">
        <Pagination
          :current="collection.page.value"
          :page-size="collection.pageSize.value"
          :total="collection.total.value"
          show-size-changer
          @change="handlePaginationChange"
        />
      </div>
    </Card>
  </Page>
</template>
