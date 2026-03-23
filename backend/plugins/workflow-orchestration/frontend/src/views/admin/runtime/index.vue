<script lang="ts" setup>
import type { AdminRunDetail, AdminRunListQuery, GlobalRunSummary } from '../../../types/admin';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Card,
  Drawer,
  Empty,
  Input,
  InputNumber,
  Modal,
  Pagination,
  Select,
  Spin,
  Table,
  Tag,
  Tooltip,
  message,
} from 'ant-design-vue';

import {
  getAdminRunDetailApi,
  listAdminRunsApi,
  recoverAdminRunApi,
  replayAdminRunApi,
  terminateAdminRunApi,
} from '../../../api/admin';
import { formatCompactNumber, formatDateTime, formatDurationMs } from '../shared/format';
import { usePaginatedCollection } from '../shared/use-paginated-collection';

import {
  getArtifactStatusColor,
  getArtifactStatusText,
  getArtifactTypeText,
  getNodeStatusColor,
  getNodeStatusText,
  getRunStatusColor,
  getRunStatusOptions,
  getRunStatusText,
  hasRunAction,
} from './data';

import { getRiskColor, getRiskText } from '../templates/data';
import { ADMIN_I18N_PREFIX } from '../shared/constants';
import { $t } from '@novus/plugin-shared';

defineOptions({ name: 'WorkflowOrchestrationAdminRuntime' });

type RuntimeAction = 'recover' | 'replay' | 'terminate';

const keyword = ref('');
const workflowIdInput = ref<null | number>(null);
const tenantIdInput = ref<null | number>(null);
const drawerOpen = ref(false);
const detailLoading = ref(false);
const actionLoadingKey = ref('');
const selectedRunId = ref<null | number>(null);
const runDetail = ref<AdminRunDetail | null>(null);

const collection = usePaginatedCollection<
  GlobalRunSummary,
  Omit<AdminRunListQuery, 'page' | 'pageSize'>
>({
  initialPageSize: 10,
  initialQuery: {
    keyword: '',
    sort: '-updated_at',
    status: '',
    tenantId: undefined,
    workflowId: undefined,
  },
  loader: ({ page, pageSize, query }) => listAdminRunsApi({ ...query, page, pageSize }),
});

const runStatusOptions = computed(() => getRunStatusOptions());
const currentRun = computed(() => runDetail.value?.run ?? null);
const visibleItems = computed(() => collection.items.value);

const summaryCards = computed(() => [
  {
    key: 'total',
    icon: 'lucide:activity',
    label: $t(`${ADMIN_I18N_PREFIX}.runtime.stats.total`),
    value: formatCompactNumber(collection.total.value),
  },
  {
    key: 'running',
    icon: 'lucide:loader-circle',
    label: $t(`${ADMIN_I18N_PREFIX}.runtime.stats.running`),
    value: formatCompactNumber(visibleItems.value.filter((item) => item.status === 'running').length),
  },
  {
    key: 'waitingHuman',
    icon: 'lucide:badge-alert',
    label: $t(`${ADMIN_I18N_PREFIX}.runtime.stats.waitingHuman`),
    value: formatCompactNumber(
      visibleItems.value.filter((item) => item.status === 'waiting_human').length,
    ),
  },
  {
    key: 'failed',
    icon: 'lucide:shield-alert',
    label: $t(`${ADMIN_I18N_PREFIX}.runtime.stats.failed`),
    value: formatCompactNumber(visibleItems.value.filter((item) => item.status === 'failed').length),
  },
]);

const tableColumns = computed(() => [
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.table.workflow`), dataIndex: 'workflow_name', key: 'workflow_name' },
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.table.tenant`), dataIndex: 'tenant_id', key: 'tenant_id', width: 180 },
  { title: $t(`${ADMIN_I18N_PREFIX}.common.status`), dataIndex: 'status', key: 'status', width: 180 },
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.table.currentNode`), dataIndex: 'current_node_name', key: 'current_node_name', width: 180 },
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.table.nodeCounts`), dataIndex: 'node_counts', key: 'node_counts', width: 180 },
  { title: $t(`${ADMIN_I18N_PREFIX}.common.updatedAt`), dataIndex: 'updated_at', key: 'updated_at', width: 180 },
  { title: $t(`${ADMIN_I18N_PREFIX}.common.action`), key: 'action', width: 280, fixed: 'right' },
]);

const nodeRunColumns = computed(() => [
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.nodeRuns.node`), dataIndex: 'node_key', key: 'node_key' },
  { title: $t(`${ADMIN_I18N_PREFIX}.common.status`), dataIndex: 'status', key: 'status', width: 140 },
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.nodeRuns.executor`), dataIndex: 'executor_type', key: 'executor_type', width: 140 },
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.nodeRuns.duration`), dataIndex: 'duration_ms', key: 'duration_ms', width: 140 },
]);

const artifactColumns = computed(() => [
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.artifacts.title`), dataIndex: 'title', key: 'title' },
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.artifacts.type`), dataIndex: 'artifact_type', key: 'artifact_type', width: 160 },
  { title: $t(`${ADMIN_I18N_PREFIX}.common.status`), dataIndex: 'status', key: 'status', width: 140 },
  { title: $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.artifacts.size`), dataIndex: 'size_bytes', key: 'size_bytes', width: 140 },
]);

function buildRunName(
  record: null | Pick<GlobalRunSummary, 'code' | 'id' | 'name' | 'template_name' | 'workflow_name'>,
) {
  if (!record) {
    return '--';
  }
  return (
    record.workflow_name
    || record.template_name
    || record.name
    || record.code
    || `${$t(`${ADMIN_I18N_PREFIX}.runtime.runLabel`)} #${record.id}`
  );
}

async function loadRunDetail(runId = selectedRunId.value) {
  if (!runId) {
    runDetail.value = null;
    return;
  }
  detailLoading.value = true;
  try {
    runDetail.value = await getAdminRunDetailApi(runId);
  } finally {
    detailLoading.value = false;
  }
}

async function applyFilters() {
  await collection.patchQuery({
    keyword: keyword.value.trim(),
    status: collection.query.value.status,
    tenantId: tenantIdInput.value ?? undefined,
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

function openRunDetail(runId: number) {
  selectedRunId.value = runId;
  drawerOpen.value = true;
  void loadRunDetail(runId);
}

function closeDrawer() {
  drawerOpen.value = false;
  selectedRunId.value = null;
  runDetail.value = null;
}

async function executeRunAction(action: RuntimeAction, runId: number) {
  const loadingKey = `${runId}:${action}`;
  actionLoadingKey.value = loadingKey;
  try {
    if (action === 'replay') {
      await replayAdminRunApi(runId);
      message.success($t(`${ADMIN_I18N_PREFIX}.runtime.actions.replay.success`));
    }
    if (action === 'recover') {
      await recoverAdminRunApi(runId);
      message.success($t(`${ADMIN_I18N_PREFIX}.runtime.actions.recover.success`));
    }
    if (action === 'terminate') {
      await terminateAdminRunApi(runId);
      message.success($t(`${ADMIN_I18N_PREFIX}.runtime.actions.terminate.success`));
    }
    await collection.load();
    if (selectedRunId.value === runId) {
      await loadRunDetail(runId);
    }
  } finally {
    actionLoadingKey.value = '';
  }
}

function confirmRunAction(record: GlobalRunSummary, action: RuntimeAction) {
  Modal.confirm({
    title: $t(`${ADMIN_I18N_PREFIX}.runtime.actions.${action}.confirmTitle`),
    content: $t(`${ADMIN_I18N_PREFIX}.runtime.actions.${action}.confirmContent`, {
      name: buildRunName(record),
    }),
    onOk: async () => executeRunAction(action, record.id),
  });
}

onMounted(() => {
  workflowIdInput.value = collection.query.value.workflowId ?? null;
  tenantIdInput.value = collection.query.value.tenantId ?? null;
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
            <div class="mb-2 inline-flex items-center gap-2 rounded-full border bg-background/85 px-3 py-1 text-xs text-muted-foreground">
              <IconifyIcon icon="lucide:activity" class="h-3.5 w-3.5" />
              {{ $t(`${ADMIN_I18N_PREFIX}.runtime.badge`) }}
            </div>
            <h1 class="text-xl font-semibold text-foreground md:text-2xl">
              {{ $t(`${ADMIN_I18N_PREFIX}.runtime.title`) }}
            </h1>
            <p class="mt-1 text-sm text-muted-foreground">
              {{ $t(`${ADMIN_I18N_PREFIX}.runtime.subtitle`) }}
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
          <div v-for="card in summaryCards" :key="card.key" class="rounded-xl border bg-background/85 p-3">
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
      :message="$t(`${ADMIN_I18N_PREFIX}.runtime.contractNotice.title`)"
      :description="$t(`${ADMIN_I18N_PREFIX}.runtime.contractNotice.description`)"
      show-icon
      type="info"
    />

    <Card :body-style="{ padding: '18px' }">
      <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Input v-model:value="keyword" :placeholder="$t(`${ADMIN_I18N_PREFIX}.runtime.filters.searchPlaceholder`)" allow-clear class="min-w-[220px]" @press-enter="applyFilters">
            <template #prefix>
              <IconifyIcon icon="lucide:search" class="h-4 w-4 text-muted-foreground" />
            </template>
          </Input>
          <Select
            :value="collection.query.value.status"
            :options="runStatusOptions"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.runtime.filters.allStatuses`)"
            allow-clear
            class="min-w-[180px]"
            @change="(value) => collection.patchQuery({ status: typeof value === 'string' ? value : '' })"
          />
          <InputNumber v-model:value="workflowIdInput" :min="1" :placeholder="$t(`${ADMIN_I18N_PREFIX}.runtime.filters.workflowIdPlaceholder`)" class="w-full min-w-[180px]" />
          <InputNumber v-model:value="tenantIdInput" :min="1" :placeholder="$t(`${ADMIN_I18N_PREFIX}.runtime.filters.tenantIdPlaceholder`)" class="w-full min-w-[180px]" />
        </div>

        <Button type="primary" @click="applyFilters">
          <template #icon>
            <IconifyIcon icon="lucide:filter" />
          </template>
          {{ $t(`${ADMIN_I18N_PREFIX}.runtime.filters.apply`) }}
        </Button>
      </div>
    </Card>

    <Card :body-style="{ padding: '0' }">
      <Table :columns="tableColumns" :data-source="visibleItems" :loading="collection.loading.value" :pagination="false" row-key="id">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'workflow_name'">
            <button class="flex max-w-[320px] items-start gap-3 text-left" type="button" @click="openRunDetail(record.id)">
              <div class="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <IconifyIcon icon="lucide:activity" class="h-4 w-4 text-primary" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm font-medium text-foreground">
                  {{ buildRunName(record) }}
                </div>
                <div class="mt-1 truncate text-xs text-muted-foreground">
                  {{ record.trigger_source || record.mode || record.code || '--' }}
                </div>
              </div>
            </button>
          </template>

          <template v-else-if="column.key === 'tenant_id'">
            <div class="space-y-1 text-sm text-foreground">
              <div>#{{ record.tenant_id || '--' }}</div>
              <div class="text-xs text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.runtime.table.tenantNameUnavailable`) }}
              </div>
            </div>
          </template>

          <template v-else-if="column.key === 'status'">
            <div class="flex flex-wrap gap-1.5">
              <Tag :color="getRunStatusColor(record.status)" class="!m-0">
                {{ getRunStatusText(record.status) }}
              </Tag>
              <Tag v-if="record.risk_level" :color="getRiskColor(record.risk_level)" class="!m-0">
                {{ getRiskText(record.risk_level) }}
              </Tag>
            </div>
          </template>

          <template v-else-if="column.key === 'current_node_name'">
            <span class="text-sm text-foreground">
              {{ record.current_node_name || record.current_node_key || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
            </span>
          </template>

          <template v-else-if="column.key === 'node_counts'">
            <div class="space-y-1 text-xs text-muted-foreground">
              <div>
                {{ $t(`${ADMIN_I18N_PREFIX}.runtime.table.nodeCountSummary`, { total: record.node_counts?.total ?? 0, running: record.node_counts?.running ?? 0 }) }}
              </div>
              <div>
                {{ $t(`${ADMIN_I18N_PREFIX}.runtime.table.nodeResultSummary`, { succeeded: record.node_counts?.succeeded ?? 0, failed: record.node_counts?.failed ?? 0 }) }}
              </div>
            </div>
          </template>

          <template v-else-if="column.key === 'updated_at'">
            <Tooltip :title="formatDateTime(record.updated_at || record.started_at)">
              <span class="text-sm text-muted-foreground">
                {{ formatDateTime(record.updated_at || record.started_at) }}
              </span>
            </Tooltip>
          </template>

          <template v-else-if="column.key === 'action'">
            <div class="flex flex-wrap items-center gap-2">
              <Button type="link" size="small" @click="openRunDetail(record.id)">
                {{ $t(`${ADMIN_I18N_PREFIX}.common.detail`) }}
              </Button>
              <Button type="link" size="small" :disabled="!hasRunAction(record, 'replay')" :loading="actionLoadingKey === `${record.id}:replay`" @click="confirmRunAction(record, 'replay')">
                {{ $t(`${ADMIN_I18N_PREFIX}.runtime.actions.replay.label`) }}
              </Button>
              <Button type="link" size="small" :disabled="!hasRunAction(record, 'recover')" :loading="actionLoadingKey === `${record.id}:recover`" @click="confirmRunAction(record, 'recover')">
                {{ $t(`${ADMIN_I18N_PREFIX}.runtime.actions.recover.label`) }}
              </Button>
              <Button type="link" size="small" danger :disabled="!hasRunAction(record, 'terminate')" :loading="actionLoadingKey === `${record.id}:terminate`" @click="confirmRunAction(record, 'terminate')">
                {{ $t(`${ADMIN_I18N_PREFIX}.runtime.actions.terminate.label`) }}
              </Button>
            </div>
          </template>
        </template>

        <template #emptyText>
          <div class="py-10">
            <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
          </div>
        </template>
      </Table>

      <div class="flex justify-end border-t px-4 py-4">
        <Pagination :current="collection.page.value" :page-size="collection.pageSize.value" :total="collection.total.value" show-size-changer @change="handlePaginationChange" />
      </div>
    </Card>

    <Drawer :open="drawerOpen" :title="$t(`${ADMIN_I18N_PREFIX}.runtime.drawer.title`, { name: buildRunName(currentRun) })" destroy-on-close placement="right" width="720" @close="closeDrawer">
      <Spin :spinning="detailLoading">
        <template v-if="currentRun">
          <div class="space-y-4">
            <div class="flex flex-wrap gap-2">
              <Tag :color="getRunStatusColor(currentRun.status)" class="!m-0">
                {{ getRunStatusText(currentRun.status) }}
              </Tag>
              <Tag v-if="currentRun.risk_level" :color="getRiskColor(currentRun.risk_level)" class="!m-0">
                {{ getRiskText(currentRun.risk_level) }}
              </Tag>
              <Tag v-for="action in currentRun.available_actions || []" :key="action" class="!m-0">
                {{ action }}
              </Tag>
            </div>

            <div class="grid gap-3 md:grid-cols-2">
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">{{ $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.overview.workflow`) }}</div>
                <div class="mt-2 text-sm font-medium text-foreground">{{ buildRunName(currentRun) }}</div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">{{ $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.overview.tenant`) }}</div>
                <div class="mt-2 text-sm font-medium text-foreground">#{{ currentRun.tenant_id || '--' }}</div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">{{ $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.overview.currentNode`) }}</div>
                <div class="mt-2 text-sm font-medium text-foreground">{{ currentRun.current_node_name || currentRun.current_node_key || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}</div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">{{ $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.overview.workflowVersion`) }}</div>
                <div class="mt-2 text-sm font-medium text-foreground">{{ currentRun.workflow_version_id ? `#${currentRun.workflow_version_id}` : $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}</div>
              </div>
            </div>

            <Card :body-style="{ padding: '0' }" size="small">
              <template #title>
                <div class="flex items-center gap-2 px-4 py-4">
                  <IconifyIcon icon="lucide:git-branch" class="h-4 w-4 text-primary" />
                  {{ $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.nodeRuns.title`) }}
                </div>
              </template>
              <Table :columns="nodeRunColumns" :data-source="runDetail?.node_runs || []" :pagination="false" row-key="id" size="small">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'node_key'">
                    <div class="space-y-1">
                      <div class="text-sm font-medium text-foreground">{{ record.node_label || record.node_key || '--' }}</div>
                      <div class="text-xs text-muted-foreground">{{ record.node_type || '--' }}</div>
                    </div>
                  </template>
                  <template v-else-if="column.key === 'status'">
                    <Tag :color="getNodeStatusColor(record.status)">{{ getNodeStatusText(record.status) }}</Tag>
                  </template>
                  <template v-else-if="column.key === 'executor_type'">
                    <span class="text-sm text-foreground">{{ record.executor_type || '--' }}</span>
                  </template>
                  <template v-else-if="column.key === 'duration_ms'">
                    <span class="text-sm text-foreground">{{ formatDurationMs(record.duration_ms) }}</span>
                  </template>
                </template>
              </Table>
            </Card>

            <Card :body-style="{ padding: '0' }" size="small">
              <template #title>
                <div class="flex items-center gap-2 px-4 py-4">
                  <IconifyIcon icon="lucide:package-open" class="h-4 w-4 text-primary" />
                  {{ $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.artifacts.sectionTitle`) }}
                </div>
              </template>
              <Table :columns="artifactColumns" :data-source="runDetail?.artifacts || []" :pagination="false" row-key="id" size="small">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'title'">
                    <div class="space-y-1">
                      <div class="text-sm font-medium text-foreground">{{ record.title || record.name || '--' }}</div>
                      <div class="text-xs text-muted-foreground">{{ record.summary || '--' }}</div>
                    </div>
                  </template>
                  <template v-else-if="column.key === 'artifact_type'">
                    <span class="text-sm text-foreground">{{ getArtifactTypeText(record.artifact_type) }}</span>
                  </template>
                  <template v-else-if="column.key === 'status'">
                    <Tag :color="getArtifactStatusColor(record.status)">{{ getArtifactStatusText(record.status) }}</Tag>
                  </template>
                  <template v-else-if="column.key === 'size_bytes'">
                    <span class="text-sm text-foreground">{{ record.size_bytes ?? '--' }}</span>
                  </template>
                </template>
              </Table>
            </Card>

            <Card :body-style="{ padding: '18px' }" size="small">
              <template #title>
                <div class="flex items-center gap-2">
                  <IconifyIcon icon="lucide:history" class="h-4 w-4 text-primary" />
                  {{ $t(`${ADMIN_I18N_PREFIX}.runtime.drawer.events.title`) }}
                </div>
              </template>
              <div v-if="(runDetail?.events || []).length === 0" class="py-4">
                <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
              </div>
              <div v-else class="space-y-3">
                <div v-for="event in runDetail?.events || []" :key="event.id" class="rounded-xl border bg-accent/10 px-4 py-3">
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0 flex-1">
                      <div class="text-sm font-medium text-foreground">{{ event.message || event.event_type || '--' }}</div>
                      <div class="mt-1 text-xs leading-5 text-muted-foreground">{{ event.status_from || '--' }} → {{ event.status_to || '--' }}</div>
                    </div>
                    <span class="whitespace-nowrap text-xs text-muted-foreground">{{ formatDateTime(event.created_at || event.occurred_at) }}</span>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </template>

        <template v-else-if="detailLoading">
          <div class="flex justify-center py-10">
            <Spin />
          </div>
        </template>

        <template v-else>
          <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
        </template>
      </Spin>
    </Drawer>
  </Page>
</template>
