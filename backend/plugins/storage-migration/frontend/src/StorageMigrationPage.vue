<script lang="ts" setup>
import type { ImpactAnalysis, MigrationTask, StorageDriverInfo } from './types';

import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  InputNumber,
  Modal,
  Progress,
  Space,
  Table,
  Tooltip,
  message,
} from 'ant-design-vue';

import { $t } from '@novus/plugin-shared';

import {
  cancelMigrationTaskApi,
  cleanupSourceFilesApi,
  createMigrationTaskApi,
  getImpactAnalysisApi,
  getStorageDriversApi,
  listMigrationTasksApi,
  pauseMigrationTaskApi,
  resumeMigrationTaskApi,
  retryFailedFilesApi,
  rollbackMigrationTaskApi,
} from './api';
import {
  ACTIVE_STATUSES,
  formatBytes,
  formatTime,
  getDriverLabel,
  getProgressPercent,
  getStatusColor,
  getStatusText,
} from './data';
import DetailDrawer from './DetailDrawer.vue';

defineOptions({ name: 'StorageMigrationPage' });

const route = useRoute();

const [DetailDrawerComp, detailDrawerApi] = useVbenDrawer({
  connectedComponent: DetailDrawer,
});

const loading = ref(false);
const creating = ref(false);
const analyzingImpact = ref(false);
const drivers = ref<StorageDriverInfo[]>([]);
const tasks = ref<MigrationTask[]>([]);
const totalTasks = ref(0);
const currentPage = ref(1);
const impactAnalysis = ref<ImpactAnalysis | null>(null);

const sourceDriver = ref('');
const targetDriver = ref('');
const concurrency = ref(5);

let pollTimer: ReturnType<typeof setInterval> | null = null;

const availableDrivers = computed(() => drivers.value.filter((driver) => driver.is_available));
const targetDriverOptions = computed(() =>
  availableDrivers.value.filter((driver) => driver.name !== sourceDriver.value),
);
const activeTasks = computed(() => tasks.value.filter((task) => ACTIVE_STATUSES.includes(task.status)));
const hasSelectedDrivers = computed(() => Boolean(sourceDriver.value && targetDriver.value));
const canCreateTask = computed(() => hasSelectedDrivers.value && availableDrivers.value.length >= 2);
const selectedFlowText = computed(() => {
  if (!hasSelectedDrivers.value) {
    return $t('admin.storageMigration.common.flowPlaceholder');
  }
  return `${driverLabel(sourceDriver.value)} -> ${driverLabel(targetDriver.value)}`;
});

const stats = computed(() => ({
  running: tasks.value.filter((task) => task.status === 'running').length,
  completed: tasks.value.filter((task) => task.status === 'completed').length,
  failed: tasks.value.filter((task) => task.status === 'failed').length,
  total: totalTasks.value,
}));

watch(sourceDriver, () => {
  impactAnalysis.value = null;
  if (
    targetDriver.value
    && !targetDriverOptions.value.some((driver) => driver.name === targetDriver.value)
  ) {
    targetDriver.value = '';
  }
});

watch(targetDriver, () => {
  impactAnalysis.value = null;
});

const DRIVER_ICONS: Record<string, string> = {
  local: 'lucide:hard-drive',
  'aliyun-oss': 'lucide:cloud',
  'amazon-s3': 'lucide:database',
  'qiniu-kodo': 'lucide:cloud-rain-wind',
  'tencent-cos': 'lucide:cloudy',
};

function getDriverIcon(name: string): string {
  return DRIVER_ICONS[name] ?? 'lucide:cloud';
}

function openDetail(taskId: number) {
  detailDrawerApi.setData({ taskId, drivers: drivers.value }).open();
}

function driverLabel(name: string): string {
  return getDriverLabel(name, drivers.value);
}

function taskProgress(task: MigrationTask): number {
  return getProgressPercent(task);
}

function progressStatus(task: MigrationTask): 'active' | 'exception' | 'success' {
  if (task.status === 'completed') return 'success';
  if (task.status === 'paused' || task.status === 'failed' || task.status === 'cancelled') {
    return 'exception';
  }
  return 'active';
}

function progressColor(task: MigrationTask): string | undefined {
  return task.status === 'paused' ? '#faad14' : undefined;
}

function toSafeNumber(value: number | null | undefined): number {
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? num : 0;
}

function formatCount(value: number | null | undefined): string {
  return toSafeNumber(value).toLocaleString();
}

function normalizeImpactAnalysis(
  payload: null | Partial<ImpactAnalysis> | undefined,
): ImpactAnalysis {
  return {
    source_driver: payload?.source_driver ?? sourceDriver.value,
    target_driver: payload?.target_driver ?? targetDriver.value,
    source_available: Boolean(payload?.source_available),
    target_available: Boolean(payload?.target_available),
    total_files: toSafeNumber(payload?.total_files),
    total_size_bytes: toSafeNumber(payload?.total_size_bytes),
    private_files: toSafeNumber(payload?.private_files),
    private_size_bytes: toSafeNumber(payload?.private_size_bytes),
    public_files: toSafeNumber(payload?.public_files),
    public_size_bytes: toSafeNumber(payload?.public_size_bytes),
    tenant_breakdown: Array.isArray(payload?.tenant_breakdown)
      ? payload.tenant_breakdown
      : [],
    scope: payload?.scope ?? 'all',
  };
}

async function loadDrivers() {
  try {
    drivers.value = await getStorageDriversApi();
  } catch {
    // handled
  }
}

async function loadTasks() {
  loading.value = true;
  try {
    const result = await listMigrationTasksApi(currentPage.value);
    tasks.value = result.items ?? [];
    totalTasks.value = result.total ?? 0;
  } catch {
    // handled
  } finally {
    loading.value = false;
  }
}

async function refreshAll() {
  await Promise.all([loadDrivers(), loadTasks()]);
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    void loadTasks();
  }, 3000);
}

function stopPolling() {
  if (!pollTimer) return;
  clearInterval(pollTimer);
  pollTimer = null;
}

function onTaskPageChange(page: number) {
  currentPage.value = page;
  void loadTasks();
}

async function onAnalyzeImpact() {
  if (!sourceDriver.value || !targetDriver.value) return;
  analyzingImpact.value = true;
  try {
    const result = await getImpactAnalysisApi(
      sourceDriver.value,
      targetDriver.value,
    );
    impactAnalysis.value = normalizeImpactAnalysis(
      result as Partial<ImpactAnalysis>,
    );
  } catch {
    // handled
  } finally {
    analyzingImpact.value = false;
  }
}
function onCreateTask() {
  if (!sourceDriver.value || !targetDriver.value) {
    message.warning($t('admin.storageMigration.error.selectDrivers'));
    return;
  }

  Modal.confirm({
    title: $t('admin.storageMigration.task.create'),
    content: $t('admin.storageMigration.action.confirmCreate'),
    onOk: async () => {
      creating.value = true;
      try {
        const result = await createMigrationTaskApi({
          source_driver: sourceDriver.value,
          target_driver: targetDriver.value,
          concurrency: concurrency.value,
        });
        message.success($t('admin.storageMigration.task.created', { count: result.total_files }));
        impactAnalysis.value = null;
        await loadTasks();
        startPolling();
        if (result.task_id) {
          openDetail(result.task_id);
        }
      } catch {
        // handled
      } finally {
        creating.value = false;
      }
    },
  });
}

async function onPause(taskId: number) {
  try {
    await pauseMigrationTaskApi(taskId);
    message.success($t('admin.storageMigration.action.paused'));
    await loadTasks();
  } catch {
    // handled
  }
}

async function onResume(taskId: number) {
  try {
    await resumeMigrationTaskApi(taskId);
    message.success($t('admin.storageMigration.action.resumed'));
    await loadTasks();
    startPolling();
  } catch {
    // handled
  }
}

function onCancel(taskId: number) {
  Modal.confirm({
    title: $t('admin.storageMigration.action.cancel'),
    content: $t('admin.storageMigration.action.confirmCancel'),
    okType: 'danger',
    onOk: async () => {
      try {
        await cancelMigrationTaskApi(taskId);
        message.success($t('admin.storageMigration.action.cancelled'));
        await loadTasks();
      } catch {
        // handled
      }
    },
  });
}

async function onRetryFailed(taskId: number) {
  try {
    await retryFailedFilesApi(taskId);
    message.success($t('admin.storageMigration.action.retryStarted'));
    await loadTasks();
    startPolling();
  } catch {
    // handled
  }
}

function onRollback(taskId: number) {
  Modal.confirm({
    title: $t('admin.storageMigration.action.rollback'),
    content: $t('admin.storageMigration.action.confirmRollback'),
    okType: 'danger',
    onOk: async () => {
      try {
        await rollbackMigrationTaskApi(taskId);
        message.success($t('admin.storageMigration.action.rollbackDone'));
        await loadTasks();
      } catch {
        // handled
      }
    },
  });
}

function onCleanupSource(taskId: number) {
  Modal.confirm({
    title: $t('admin.storageMigration.action.cleanup'),
    content: $t('admin.storageMigration.action.confirmCleanup'),
    okType: 'danger',
    onOk: async () => {
      try {
        const result = await cleanupSourceFilesApi(taskId);
        message.success($t('admin.storageMigration.action.cleanupDone', { count: result.deleted_files }));
        await loadTasks();
      } catch {
        // handled
      }
    },
  });
}

onMounted(async () => {
  await refreshAll();

  const qSource = route.query.source as string | undefined;
  const qTarget = route.query.target as string | undefined;

  if (qSource) sourceDriver.value = qSource;
  if (qTarget) targetDriver.value = qTarget;

  if (tasks.value.some((task) => ACTIVE_STATUSES.includes(task.status))) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <Page auto-content-height>
    <DetailDrawerComp />

    <div class="space-y-4">
      <section class="relative overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-primary/5" />
        <div class="relative flex flex-col gap-4 p-5">
          <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <div
                class="mb-2 inline-flex items-center gap-1.5 rounded-full border bg-background/80 px-3 py-1 text-xs text-muted-foreground"
              >
                <IconifyIcon icon="lucide:database-zap" class="h-3.5 w-3.5" />
                {{ $t('admin.storageMigration.menu.title') }}
              </div>
              <h1 class="text-xl font-semibold text-foreground md:text-2xl">
                {{ $t('admin.storageMigration.page.title') }}
              </h1>
              <p class="mt-1 text-sm text-muted-foreground">
                {{ $t('admin.storageMigration.page.subtitle') }}
              </p>
            </div>
            <Button :loading="loading" @click="refreshAll">
              <template #icon>
                <IconifyIcon icon="lucide:refresh-cw" />
              </template>
              {{ $t('admin.storageMigration.common.refresh') }}
            </Button>
          </div>

          <div class="grid grid-cols-2 gap-2 md:grid-cols-4">
            <div class="rounded-xl border bg-background/85 p-3">
              <div class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.common.totalTasks') }}</div>
              <div class="mt-1 text-lg font-semibold tabular-nums">{{ stats.total }}</div>
            </div>
            <div class="rounded-xl border bg-background/85 p-3">
              <div class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.task.status.running') }}</div>
              <div class="mt-1 text-lg font-semibold text-blue-600 tabular-nums">{{ stats.running }}</div>
            </div>
            <div class="rounded-xl border bg-background/85 p-3">
              <div class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.task.status.completed') }}</div>
              <div class="mt-1 text-lg font-semibold text-green-600 tabular-nums">{{ stats.completed }}</div>
            </div>
            <div class="rounded-xl border bg-background/85 p-3">
              <div class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.common.availableDrivers') }}</div>
              <div class="mt-1 text-lg font-semibold tabular-nums">{{ availableDrivers.length }}/{{ drivers.length }}</div>
            </div>
          </div>
        </div>
      </section>
      <div class="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(330px,0.65fr)]">
        <Card>
          <template #title>
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:waypoints" class="h-4 w-4 text-primary" />
              {{ $t('admin.storageMigration.panel.plannerTitle') }}
            </div>
          </template>
          <template #extra>
            <span class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.panel.plannerDesc') }}</span>
          </template>

          <div class="space-y-4">
            <Alert
              v-if="availableDrivers.length < 2"
              show-icon
              type="warning"
              :message="$t('admin.storageMigration.error.needTwoDrivers')"
            />

            <div class="grid gap-4 md:grid-cols-2">
              <div class="space-y-2">
                <div class="flex items-center gap-2 text-sm font-medium text-foreground">
                  <span class="flex h-5 w-5 items-center justify-center rounded-full bg-muted text-xs font-semibold">S</span>
                  {{ $t('admin.storageMigration.impactAnalysis.sourceDriver') }}
                </div>
                <button
                  v-for="driver in availableDrivers"
                  :key="driver.name"
                  class="w-full rounded-xl border p-3 text-left transition-all"
                  :class="sourceDriver === driver.name ? 'border-primary bg-primary/5 shadow-sm' : 'border-border hover:border-primary/35 hover:bg-accent/30'"
                  type="button"
                  @click="sourceDriver = driver.name"
                >
                  <div class="flex items-center gap-3">
                    <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/50">
                      <IconifyIcon :icon="getDriverIcon(driver.name)" class="h-4 w-4" />
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="truncate text-sm font-medium text-foreground">{{ driverLabel(driver.name) }}</div>
                      <div class="mt-0.5 text-xs text-muted-foreground">
                        {{ driver.is_builtin ? $t('admin.storageMigration.common.builtinDriver') : driver.plugin_name }}
                      </div>
                    </div>
                    <IconifyIcon v-if="sourceDriver === driver.name" icon="lucide:check-circle-2" class="h-4 w-4 text-primary" />
                  </div>
                </button>
              </div>

              <div class="space-y-2">
                <div class="flex items-center gap-2 text-sm font-medium text-foreground">
                  <span class="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">T</span>
                  {{ $t('admin.storageMigration.impactAnalysis.targetDriver') }}
                </div>
                <div
                  v-if="!sourceDriver"
                  class="flex min-h-[120px] items-center justify-center rounded-xl border border-dashed text-center text-sm text-muted-foreground"
                >
                  {{ $t('admin.storageMigration.common.selectSourceFirst') }}
                </div>
                <template v-else>
                  <button
                    v-for="driver in targetDriverOptions"
                    :key="driver.name"
                    class="w-full rounded-xl border p-3 text-left transition-all"
                    :class="targetDriver === driver.name ? 'border-primary bg-primary/5 shadow-sm' : 'border-border hover:border-primary/35 hover:bg-accent/30'"
                    type="button"
                    @click="targetDriver = driver.name"
                  >
                    <div class="flex items-center gap-3">
                      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/50">
                        <IconifyIcon :icon="getDriverIcon(driver.name)" class="h-4 w-4" />
                      </div>
                      <div class="min-w-0 flex-1">
                        <div class="truncate text-sm font-medium text-foreground">{{ driverLabel(driver.name) }}</div>
                        <div class="mt-0.5 text-xs text-muted-foreground">
                          {{ driver.is_builtin ? $t('admin.storageMigration.common.builtinDriver') : driver.plugin_name }}
                        </div>
                      </div>
                      <IconifyIcon v-if="targetDriver === driver.name" icon="lucide:check-circle-2" class="h-4 w-4 text-primary" />
                    </div>
                  </button>
                </template>
              </div>
            </div>

            <div class="rounded-xl border bg-accent/20 p-4">
              <div class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{{ $t('admin.storageMigration.common.flowPreview') }}</div>
              <div class="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                <span class="rounded-md bg-primary/10 px-2 py-1">{{ selectedFlowText }}</span>
                <span class="text-muted-foreground">{{ $t('admin.storageMigration.task.concurrency') }}</span>
                <InputNumber v-model:value="concurrency" :min="1" :max="20" size="small" style="width: 88px" />
                <div class="ml-auto flex items-center gap-2">
                  <Button :loading="analyzingImpact" :disabled="!hasSelectedDrivers" @click="onAnalyzeImpact">
                    <template #icon><IconifyIcon icon="lucide:scan-search" /></template>
                    {{ $t('admin.storageMigration.action.impactAnalysis') }}
                  </Button>
                  <Button type="primary" :loading="creating" :disabled="!canCreateTask" @click="onCreateTask">
                    <template #icon><IconifyIcon icon="lucide:play" /></template>
                    {{ $t('admin.storageMigration.action.start') }}
                  </Button>
                </div>
              </div>
            </div>

            <div v-if="impactAnalysis" class="rounded-xl border bg-background p-4">
              <div class="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <IconifyIcon icon="lucide:activity" class="h-4 w-4 text-primary" />
                {{ $t('admin.storageMigration.impactAnalysis.title') }}
              </div>
              <div class="grid gap-3 sm:grid-cols-3">
                <div class="rounded-lg border bg-accent/20 p-3">
                  <div class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.impactAnalysis.totalFiles') }}</div>
                  <div class="mt-1 text-base font-semibold tabular-nums">{{ formatCount(impactAnalysis.total_files) }}</div>
                </div>
                <div class="rounded-lg border bg-accent/20 p-3">
                  <div class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.impactAnalysis.totalSize') }}</div>
                  <div class="mt-1 text-base font-semibold tabular-nums">{{ formatBytes(toSafeNumber(impactAnalysis.total_size_bytes)) }}</div>
                </div>
                <div class="rounded-lg border bg-accent/20 p-3">
                  <div class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.impactAnalysis.privateFiles') }}</div>
                  <div class="mt-1 text-base font-semibold tabular-nums">{{ formatCount(impactAnalysis.private_files) }}</div>
                </div>
              </div>
              <Alert
                v-if="!impactAnalysis.source_available || !impactAnalysis.target_available"
                class="mt-3"
                show-icon
                type="error"
                :message="$t('admin.storageMigration.error.driverNotAvailable')"
              />
            </div>
          </div>
        </Card>

        <Card>
          <template #title>
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:radar" class="h-4 w-4 text-primary" />
              {{ $t('admin.storageMigration.panel.monitorTitle') }}
            </div>
          </template>
          <template #extra>
            <span class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.panel.monitorDesc') }}</span>
          </template>

          <div v-if="activeTasks.length > 0" class="space-y-3">
            <div v-for="task in activeTasks" :key="task.id" class="rounded-xl border bg-accent/10 p-3">
              <div class="mb-2 flex items-center justify-between gap-2">
                <span class="text-xs text-muted-foreground">{{ $t('admin.storageMigration.common.taskId') }} #{{ task.id }}</span>
                <Badge :status="getStatusColor(task.status)" :text="getStatusText(task.status)" />
              </div>
              <div class="mb-2 text-sm font-medium text-foreground">
                {{ driverLabel(task.source_driver) }} -> {{ driverLabel(task.target_driver) }}
              </div>
              <Progress :percent="taskProgress(task)" :status="progressStatus(task)" :stroke-color="progressColor(task)" size="small" />
              <div class="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                <span>{{ task.migrated_files }}/{{ task.total_files }} {{ $t('admin.storageMigration.task.fileUnit') }}</span>
                <span :class="task.failed_files > 0 ? 'text-red-500' : ''">
                  {{ task.failed_files > 0 ? $t('admin.storageMigration.task.failedCount', { count: task.failed_files }) : formatBytes(task.migrated_bytes) }}
                </span>
              </div>
              <div class="mt-3 flex items-center justify-between gap-2">
                <Button size="small" type="link" @click="openDetail(task.id)">{{ $t('shared.common.detail') }}</Button>
                <Space :size="4">
                  <Tooltip v-if="task.status === 'running'" :title="$t('admin.storageMigration.action.pause')">
                    <Button size="small" @click="onPause(task.id)">
                      <template #icon><IconifyIcon icon="lucide:pause" class="h-3.5 w-3.5" /></template>
                    </Button>
                  </Tooltip>
                  <Tooltip v-if="task.status === 'paused'" :title="$t('admin.storageMigration.action.resume')">
                    <Button size="small" type="primary" @click="onResume(task.id)">
                      <template #icon><IconifyIcon icon="lucide:play" class="h-3.5 w-3.5" /></template>
                    </Button>
                  </Tooltip>
                  <Tooltip :title="$t('admin.storageMigration.action.cancel')">
                    <Button size="small" danger @click="onCancel(task.id)">
                      <template #icon><IconifyIcon icon="lucide:x" class="h-3.5 w-3.5" /></template>
                    </Button>
                  </Tooltip>
                </Space>
              </div>
            </div>
          </div>
          <Empty
            v-else
            :description="$t('admin.storageMigration.common.noActiveTasks')"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
          />
        </Card>
      </div>

      <Card>
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:history" class="h-4 w-4 text-primary" />
            {{ $t('admin.storageMigration.history.title') }}
          </div>
        </template>

        <Table
          :data-source="tasks"
          :loading="loading"
          :pagination="{
            current: currentPage,
            total: totalTasks,
            pageSize: 20,
            showTotal: (total: number) => $t('admin.storageMigration.history.totalCount', { total }),
            onChange: onTaskPageChange,
          }"
          row-key="id"
          size="middle"
          :custom-row="(record: MigrationTask) => ({
            onClick: () => openDetail(record.id),
            style: { cursor: 'pointer' },
          })"
        >
          <Table.Column :title="$t('admin.storageMigration.common.taskId')" data-index="id" :width="76" />
          <Table.Column :title="$t('admin.storageMigration.common.flow')" :width="260">
            <template #default="{ record }">
              <div class="flex items-center gap-2">
                <span class="truncate">{{ driverLabel(record.source_driver) }}</span>
                <IconifyIcon icon="lucide:arrow-right" class="h-3.5 w-3.5 text-muted-foreground" />
                <span class="truncate">{{ driverLabel(record.target_driver) }}</span>
              </div>
            </template>
          </Table.Column>
          <Table.Column :title="$t('admin.storageMigration.task.progress')" key="progress" :width="220">
            <template #default="{ record }">
              <div class="flex items-center gap-2">
                <Progress :percent="taskProgress(record)" :status="progressStatus(record)" :stroke-color="progressColor(record)" class="mb-0 flex-1" size="small" />
                <span class="whitespace-nowrap text-xs tabular-nums text-muted-foreground">{{ record.migrated_files }}/{{ record.total_files }}</span>
              </div>
            </template>
          </Table.Column>
          <Table.Column :title="$t('shared.common.status')" data-index="status" :width="120">
            <template #default="{ record }">
              <Badge :status="getStatusColor(record.status)" :text="getStatusText(record.status)" />
            </template>
          </Table.Column>
          <Table.Column :title="$t('shared.common.createdAt')" data-index="created_at" :width="170">
            <template #default="{ record }">
              <span class="text-xs text-muted-foreground">{{ formatTime(record.created_at) }}</span>
            </template>
          </Table.Column>
          <Table.Column :title="$t('shared.common.operation')" key="actions" :width="180">
            <template #default="{ record }">
              <Space :size="4" @click.stop>
                <Tooltip v-if="record.status === 'running'" :title="$t('admin.storageMigration.action.pause')">
                  <Button size="small" @click="onPause(record.id)"><template #icon><IconifyIcon icon="lucide:pause" class="h-3.5 w-3.5" /></template></Button>
                </Tooltip>
                <Tooltip v-if="record.status === 'paused'" :title="$t('admin.storageMigration.action.resume')">
                  <Button size="small" type="primary" @click="onResume(record.id)"><template #icon><IconifyIcon icon="lucide:play" class="h-3.5 w-3.5" /></template></Button>
                </Tooltip>
                <Tooltip v-if="['running', 'paused'].includes(record.status)" :title="$t('admin.storageMigration.action.cancel')">
                  <Button size="small" danger @click="onCancel(record.id)"><template #icon><IconifyIcon icon="lucide:x" class="h-3.5 w-3.5" /></template></Button>
                </Tooltip>
                <Tooltip v-if="['completed', 'failed'].includes(record.status)" :title="$t('admin.storageMigration.action.rollback')">
                  <Button size="small" danger @click="onRollback(record.id)"><template #icon><IconifyIcon icon="lucide:undo-2" class="h-3.5 w-3.5" /></template></Button>
                </Tooltip>
                <Tooltip v-if="record.failed_files > 0 && ['completed', 'failed'].includes(record.status)" :title="$t('admin.storageMigration.action.retry')">
                  <Button size="small" type="primary" @click="onRetryFailed(record.id)"><template #icon><IconifyIcon icon="lucide:refresh-cw" class="h-3.5 w-3.5" /></template></Button>
                </Tooltip>
                <Tooltip v-if="record.status === 'completed'" :title="$t('admin.storageMigration.action.cleanup')">
                  <Button size="small" danger @click="onCleanupSource(record.id)"><template #icon><IconifyIcon icon="lucide:trash-2" class="h-3.5 w-3.5" /></template></Button>
                </Tooltip>
              </Space>
            </template>
          </Table.Column>
          <template #emptyText>
            <Empty :description="$t('admin.storageMigration.history.empty')" />
          </template>
        </Table>
      </Card>
    </div>
  </Page>
</template>
