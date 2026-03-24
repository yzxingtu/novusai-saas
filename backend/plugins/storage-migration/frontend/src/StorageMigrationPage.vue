<script lang="ts" setup>
import type {
  ImpactAnalysis,
  MigrationTask,
  NovusPluginSharedAPI,
  StorageDriverInfo,
} from './types';

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
  getScopeText,
  getStatusColor,
  getStatusText,
  hasCleanupResult,
} from './data';
import DetailDrawer from './DetailDrawer.vue';

defineOptions({ name: 'StorageMigrationPage' });

const ACTION_CODES = {
  analyze: 'plugin.storage-migration.storage_migration:analyze',
  cancel: 'plugin.storage-migration.storage_migration:cancel',
  cleanup: 'plugin.storage-migration.storage_migration:cleanup',
  create: 'plugin.storage-migration.storage_migration:create',
  pause: 'plugin.storage-migration.storage_migration:pause',
  resume: 'plugin.storage-migration.storage_migration:resume',
  retry: 'plugin.storage-migration.storage_migration:retry',
  rollback: 'plugin.storage-migration.storage_migration:rollback',
} as const;

const DRIVER_ICONS: Record<string, string> = {
  local: 'lucide:hard-drive',
  'aliyun-oss': 'lucide:cloud',
  'amazon-s3': 'lucide:database',
  'qiniu-kodo': 'lucide:cloud-rain-wind',
  'tencent-cos': 'lucide:cloudy',
};

const route = useRoute();
const shared = (window as unknown as { NovusPluginShared?: NovusPluginSharedAPI })
  .NovusPluginShared;
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
const concurrency = ref<number | null>(5);
const scopeMode = ref<'all' | 'tenant'>('all');
const tenantId = ref<number | null>(null);
let pollTimer: ReturnType<typeof setInterval> | null = null;

const routeAccessCodes = computed(() => {
  const raw = (route.meta as { accessCodes?: unknown }).accessCodes;
  return Array.isArray(raw)
    ? raw.filter((code): code is string => typeof code === 'string' && code.trim().length > 0)
    : ['plugin.storage-migration.storage_migration:view'];
});

function hasAccess(codes: string | string[] | undefined): boolean {
  return shared?.hasAccessByCodes?.(codes) ?? true;
}

const permissionState = computed(() => ({
  analyze: hasAccess(ACTION_CODES.analyze),
  cancel: hasAccess(ACTION_CODES.cancel),
  cleanup: hasAccess(ACTION_CODES.cleanup),
  create: hasAccess(ACTION_CODES.create),
  pause: hasAccess(ACTION_CODES.pause),
  resume: hasAccess(ACTION_CODES.resume),
  retry: hasAccess(ACTION_CODES.retry),
  rollback: hasAccess(ACTION_CODES.rollback),
  view: hasAccess(routeAccessCodes.value),
}));

const availableDrivers = computed(() => drivers.value.filter((driver) => driver.is_available));
const targetDriverOptions = computed(() =>
  availableDrivers.value.filter((driver) => driver.name !== sourceDriver.value),
);
const activeTasks = computed(() =>
  tasks.value.filter((task) => ACTIVE_STATUSES.includes(task.status)),
);
const hasSelectedDrivers = computed(() => Boolean(sourceDriver.value && targetDriver.value));
const isScopeValid = computed(() => scopeMode.value === 'all' || Boolean((tenantId.value ?? 0) > 0));
const migrationScope = computed(() =>
  scopeMode.value === 'tenant' && (tenantId.value ?? 0) > 0 ? `tenant:${tenantId.value}` : 'all',
);
const selectedFlowText = computed(() =>
  hasSelectedDrivers.value
    ? `${driverLabel(sourceDriver.value)} -> ${driverLabel(targetDriver.value)}`
    : $t('plugin.storage-migration.common.flowPlaceholder'),
);
const readOnly = computed(
  () =>
    permissionState.value.view &&
    ![
      permissionState.value.analyze,
      permissionState.value.create,
      permissionState.value.pause,
      permissionState.value.resume,
      permissionState.value.cancel,
      permissionState.value.retry,
      permissionState.value.rollback,
      permissionState.value.cleanup,
    ].some(Boolean),
);
const stats = computed(() => ({
  completed: tasks.value.filter((task) => task.status === "completed").length,
  running: tasks.value.filter((task) => task.status === "running").length,
  total: totalTasks.value,
}));

watch([sourceDriver, targetDriver, scopeMode, tenantId], () => {
  impactAnalysis.value = null;
  if (targetDriver.value && !targetDriverOptions.value.some((driver) => driver.name === targetDriver.value)) {
    targetDriver.value = '';
  }
});

watch(
  activeTasks,
  (value) => {
    if (value.length > 0 && !pollTimer) {
      pollTimer = setInterval(() => void loadTasks(), 3000);
      return;
    }
    if (value.length === 0 && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  },
  { immediate: true },
);

function driverLabel(name: string): string {
  return getDriverLabel(name, drivers.value);
}

function getDriverIcon(name: string): string {
  return DRIVER_ICONS[name] ?? 'lucide:cloud';
}

function openDetail(taskId: number) {
  detailDrawerApi.setData({ taskId, drivers: drivers.value }).open();
}

function toSafeNumber(value: number | null | undefined): number {
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? num : 0;
}

function sanitizePositiveInt(value: number | null | undefined, fallback: number) {
  return Math.max(1, Math.trunc(Number(value ?? fallback) || fallback));
}

function normalizeImpactAnalysis(payload: null | Partial<ImpactAnalysis> | undefined): ImpactAnalysis {
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
    tenant_breakdown: Array.isArray(payload?.tenant_breakdown) ? payload.tenant_breakdown : [],
    scope: payload?.scope ?? migrationScope.value,
  };
}

function applyRoutePreset() {
  const qSource = typeof route.query.source === 'string' ? route.query.source.trim() : '';
  const qTarget = typeof route.query.target === 'string' ? route.query.target.trim() : '';
  const qScope = typeof route.query.scope === 'string' ? route.query.scope.trim() : '';
  if (qSource) sourceDriver.value = qSource;
  if (qTarget) targetDriver.value = qTarget;
  if (qScope.startsWith('tenant:')) {
    scopeMode.value = 'tenant';
    tenantId.value = sanitizePositiveInt(Number(qScope.split(':', 2)[1] || 0), 1);
  }
}

async function loadDrivers() {
  try {
    drivers.value = await getStorageDriversApi();
  } catch {}
}

async function loadTasks() {
  loading.value = true;
  try {
    const result = await listMigrationTasksApi(currentPage.value);
    tasks.value = result.items ?? [];
    totalTasks.value = result.total ?? 0;
  } finally {
    loading.value = false;
  }
}

async function refreshAll() {
  if (!permissionState.value.view) return;
  try {
    await Promise.all([loadDrivers(), loadTasks()]);
  } catch {}
}

function onTaskPageChange(page: number) {
  currentPage.value = page;
  void loadTasks();
}

async function onAnalyzeImpact() {
  if (!permissionState.value.analyze) return;
  if (!hasSelectedDrivers.value) {
    message.warning($t('plugin.storage-migration.error.selectDrivers'));
    return;
  }
  if (!isScopeValid.value) {
    message.warning($t('plugin.storage-migration.error.selectTenant'));
    return;
  }
  analyzingImpact.value = true;
  try {
    impactAnalysis.value = normalizeImpactAnalysis(
      await getImpactAnalysisApi(sourceDriver.value, targetDriver.value, migrationScope.value),
    );
  } catch {
  } finally {
    analyzingImpact.value = false;
  }
}

function onCreateTask() {
  if (!permissionState.value.create) return;
  if (!hasSelectedDrivers.value) {
    message.warning($t('plugin.storage-migration.error.selectDrivers'));
    return;
  }
  if (!isScopeValid.value) {
    message.warning($t('plugin.storage-migration.error.selectTenant'));
    return;
  }
  Modal.confirm({
    title: $t('plugin.storage-migration.task.create'),
    content:
      permissionState.value.analyze && impactAnalysis.value === null
        ? $t('plugin.storage-migration.action.confirmCreateWithoutAnalysis')
        : $t('plugin.storage-migration.action.confirmCreate'),
    onOk: async () => {
      creating.value = true;
      try {
        const result = await createMigrationTaskApi({
          source_driver: sourceDriver.value,
          target_driver: targetDriver.value,
          scope: migrationScope.value,
          concurrency: sanitizePositiveInt(concurrency.value, 5),
        });
        message.success($t('plugin.storage-migration.task.created', { count: result.total_files }));
        impactAnalysis.value = null;
        await loadTasks();
        if (result.task_id) openDetail(result.task_id);
      } catch {
      } finally {
        creating.value = false;
      }
    },
  });
}

const canPauseTask = (task: MigrationTask) => permissionState.value.pause && task.status === 'running';
const canResumeTask = (task: MigrationTask) => permissionState.value.resume && task.status === 'paused';
const canCancelTask = (task: MigrationTask) => permissionState.value.cancel && ['pending', 'paused', 'running'].includes(task.status);
const canRetryTask = (task: MigrationTask) => permissionState.value.retry && task.failed_files > 0 && ['completed', 'failed'].includes(task.status);
const canRollbackTask = (task: MigrationTask) => permissionState.value.rollback && ['completed', 'failed'].includes(task.status) && !hasCleanupResult(task);
const canCleanupTask = (task: MigrationTask) => permissionState.value.cleanup && task.status === 'completed' && !task.source_cleanup_completed_at;

async function onPause(taskId: number) {
  try {
    await pauseMigrationTaskApi(taskId);
    message.success($t('plugin.storage-migration.action.paused'));
    await loadTasks();
  } catch {}
}

async function onResume(taskId: number) {
  try {
    await resumeMigrationTaskApi(taskId);
    message.success($t('plugin.storage-migration.action.resumed'));
    await loadTasks();
  } catch {}
}

function onCancel(taskId: number) {
  Modal.confirm({
    title: $t('plugin.storage-migration.action.cancel'),
    content: $t('plugin.storage-migration.action.confirmCancel'),
    okType: 'danger',
    onOk: async () => {
      try {
        await cancelMigrationTaskApi(taskId);
        message.success($t('plugin.storage-migration.action.cancelled'));
        await loadTasks();
      } catch {}
    },
  });
}

async function onRetryFailed(taskId: number) {
  try {
    await retryFailedFilesApi(taskId);
    message.success($t('plugin.storage-migration.action.retryStarted'));
    await loadTasks();
  } catch {}
}

function onRollback(taskId: number) {
  Modal.confirm({
    title: $t('plugin.storage-migration.action.rollback'),
    content: $t('plugin.storage-migration.action.confirmRollback'),
    okType: 'danger',
    onOk: async () => {
      try {
        const result = await rollbackMigrationTaskApi(taskId);
        message.success($t('plugin.storage-migration.action.rollbackDone', { count: result.reverted_files ?? 0 }));
        if ((result.target_delete_errors ?? 0) > 0) {
          message.warning($t('plugin.storage-migration.action.rollbackDeleteWarning', { count: result.target_delete_errors }));
        }
        await loadTasks();
      } catch {}
    },
  });
}

function onCleanupSource(taskId: number) {
  Modal.confirm({
    title: $t('plugin.storage-migration.action.cleanup'),
    content: $t('plugin.storage-migration.action.confirmCleanup'),
    okType: 'danger',
    onOk: async () => {
      try {
        const result = await cleanupSourceFilesApi(taskId);
        if ((result.errors ?? 0) > 0) {
          message.warning($t('plugin.storage-migration.action.cleanupPartial', { count: result.deleted_files, errors: result.errors }));
        } else {
          message.success($t('plugin.storage-migration.action.cleanupDone', { count: result.deleted_files }));
        }
        await loadTasks();
      } catch {}
    },
  });
}

onMounted(async () => {
  applyRoutePreset();
  await refreshAll();
  if (permissionState.value.analyze && hasSelectedDrivers.value) {
    void onAnalyzeImpact();
  }
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
  <Page auto-content-height>
    <DetailDrawerComp />
    <div v-if="!permissionState.view" class="rounded-2xl border bg-card p-8">
      <Empty :description="$t('plugin.storage-migration.access.deniedDesc')" />
    </div>
    <div v-else class="space-y-4">
      <section class="rounded-2xl border bg-card p-5 shadow-sm">
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div class="mb-2 inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1 text-xs text-muted-foreground">
              <IconifyIcon icon="lucide:database-zap" class="h-3.5 w-3.5" />
              {{ $t('plugin.storage-migration.menu.title') }}
            </div>
            <h1 class="text-xl font-semibold text-foreground md:text-2xl">{{ $t('plugin.storage-migration.page.title') }}</h1>
            <p class="mt-1 text-sm text-muted-foreground">{{ $t('plugin.storage-migration.page.subtitle') }}</p>
          </div>
          <Button :loading="loading" @click="refreshAll">
            <template #icon><IconifyIcon icon="lucide:refresh-cw" /></template>
            {{ $t('plugin.storage-migration.common.refresh') }}
          </Button>
        </div>
        <Alert v-if="readOnly" class="mt-4" show-icon type="info" :message="$t('plugin.storage-migration.access.readOnlyHint')" />
        <div class="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          <div class="rounded-xl border bg-background/85 p-3"><div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.common.totalTasks') }}</div><div class="mt-1 text-lg font-semibold">{{ stats.total }}</div></div>
          <div class="rounded-xl border bg-background/85 p-3"><div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.task.status.running') }}</div><div class="mt-1 text-lg font-semibold text-blue-600">{{ stats.running }}</div></div>
          <div class="rounded-xl border bg-background/85 p-3"><div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.task.status.completed') }}</div><div class="mt-1 text-lg font-semibold text-green-600">{{ stats.completed }}</div></div>
          <div class="rounded-xl border bg-background/85 p-3"><div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.common.availableDrivers') }}</div><div class="mt-1 text-lg font-semibold">{{ availableDrivers.length }}/{{ drivers.length }}</div></div>
        </div>
      </section>

      <div class="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <Card :title="$t('plugin.storage-migration.panel.plannerTitle')">
          <div class="space-y-4">
            <Alert v-if="availableDrivers.length < 2" show-icon type="warning" :message="$t('plugin.storage-migration.error.needTwoDrivers')" />
            <div class="rounded-xl border bg-accent/20 p-4">
              <div class="mb-3 text-sm font-semibold text-foreground">{{ $t('plugin.storage-migration.scope.title') }}</div>
              <div class="grid gap-2 md:grid-cols-2">
                <button class="rounded-xl border p-3 text-left" :class="scopeMode === 'all' ? 'border-primary bg-primary/5' : 'border-border'" type="button" @click="scopeMode = 'all'"><div class="text-sm font-medium">{{ $t('plugin.storage-migration.scope.all') }}</div><div class="mt-1 text-xs text-muted-foreground">{{ $t('plugin.storage-migration.scope.allDesc') }}</div></button>
                <button class="rounded-xl border p-3 text-left" :class="scopeMode === 'tenant' ? 'border-primary bg-primary/5' : 'border-border'" type="button" @click="scopeMode = 'tenant'"><div class="text-sm font-medium">{{ $t('plugin.storage-migration.scope.singleTenant') }}</div><div class="mt-1 text-xs text-muted-foreground">{{ $t('plugin.storage-migration.scope.singleTenantDesc') }}</div></button>
              </div>
              <InputNumber v-if="scopeMode === 'tenant'" v-model:value="tenantId" class="mt-3" :min="1" :precision="0" style="width: 100%" />
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <div class="space-y-2">
                <div class="text-sm font-medium text-foreground">{{ $t('plugin.storage-migration.impactAnalysis.sourceDriver') }}</div>
                <button v-for="driver in availableDrivers" :key="driver.name" class="w-full rounded-xl border p-3 text-left" :class="sourceDriver === driver.name ? 'border-primary bg-primary/5' : 'border-border'" type="button" @click="sourceDriver = driver.name">
                  <div class="flex items-center gap-3">
                    <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-muted/50"><IconifyIcon :icon="getDriverIcon(driver.name)" class="h-4 w-4" /></div>
                    <div class="min-w-0 flex-1"><div class="truncate text-sm font-medium">{{ driverLabel(driver.name) }}</div><div class="text-xs text-muted-foreground">{{ driver.is_builtin ? $t('plugin.storage-migration.common.builtinDriver') : driver.plugin_name }}</div></div>
                  </div>
                </button>
              </div>
              <div class="space-y-2">
                <div class="text-sm font-medium text-foreground">{{ $t('plugin.storage-migration.impactAnalysis.targetDriver') }}</div>
                <div v-if="!sourceDriver" class="flex min-h-[120px] items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground">{{ $t('plugin.storage-migration.common.selectSourceFirst') }}</div>
                <template v-else>
                  <button v-for="driver in targetDriverOptions" :key="driver.name" class="w-full rounded-xl border p-3 text-left" :class="targetDriver === driver.name ? 'border-primary bg-primary/5' : 'border-border'" type="button" @click="targetDriver = driver.name">
                    <div class="flex items-center gap-3">
                      <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-muted/50"><IconifyIcon :icon="getDriverIcon(driver.name)" class="h-4 w-4" /></div>
                      <div class="min-w-0 flex-1"><div class="truncate text-sm font-medium">{{ driverLabel(driver.name) }}</div><div class="text-xs text-muted-foreground">{{ driver.is_builtin ? $t('plugin.storage-migration.common.builtinDriver') : driver.plugin_name }}</div></div>
                    </div>
                  </button>
                </template>
              </div>
            </div>

            <div class="rounded-xl border bg-background p-4">
              <div class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{{ $t('plugin.storage-migration.common.flowPreview') }}</div>
              <div class="flex flex-wrap items-center gap-2"><span class="rounded-md bg-primary/10 px-2 py-1 text-sm font-medium">{{ selectedFlowText }}</span><span class="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">{{ getScopeText(migrationScope) }}</span></div>
              <div class="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center">
                <div class="flex items-center gap-2 text-sm text-muted-foreground"><span>{{ $t('plugin.storage-migration.task.concurrency') }}</span><InputNumber v-model:value="concurrency" :min="1" :max="20" size="small" style="width: 88px" /></div>
                <div class="flex flex-wrap items-center gap-2 lg:ml-auto">
                  <Tooltip :title="!permissionState.analyze ? $t('plugin.storage-migration.access.readOnlyHint') : undefined"><span><Button :loading="analyzingImpact" :disabled="!hasSelectedDrivers || !isScopeValid || !permissionState.analyze" @click="onAnalyzeImpact"><template #icon><IconifyIcon icon="lucide:scan-search" /></template>{{ $t('plugin.storage-migration.action.impactAnalysis') }}</Button></span></Tooltip>
                  <Tooltip :title="!permissionState.create ? $t('plugin.storage-migration.access.readOnlyHint') : undefined"><span><Button type="primary" :loading="creating" :disabled="!hasSelectedDrivers || !isScopeValid || availableDrivers.length < 2 || !permissionState.create" @click="onCreateTask"><template #icon><IconifyIcon icon="lucide:play" /></template>{{ $t('plugin.storage-migration.action.start') }}</Button></span></Tooltip>
                </div>
              </div>
            </div>

            <Alert v-if="permissionState.analyze && hasSelectedDrivers && !impactAnalysis" show-icon type="info" :message="$t('plugin.storage-migration.common.analysisSuggested')" />
            <div v-if="impactAnalysis" class="rounded-xl border bg-background p-4">
              <div class="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground"><IconifyIcon icon="lucide:activity" class="h-4 w-4 text-primary" />{{ $t('plugin.storage-migration.impactAnalysis.title') }}</div>
              <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div class="rounded-lg border bg-accent/20 p-3"><div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.impactAnalysis.totalFiles') }}</div><div class="mt-1 text-base font-semibold">{{ impactAnalysis.total_files.toLocaleString() }}</div></div>
                <div class="rounded-lg border bg-accent/20 p-3"><div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.impactAnalysis.totalSize') }}</div><div class="mt-1 text-base font-semibold">{{ formatBytes(impactAnalysis.total_size_bytes) }}</div></div>
                <div class="rounded-lg border bg-accent/20 p-3"><div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.impactAnalysis.privateFiles') }}</div><div class="mt-1 text-base font-semibold">{{ impactAnalysis.private_files.toLocaleString() }}</div></div>
                <div class="rounded-lg border bg-accent/20 p-3"><div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.impactAnalysis.publicFiles') }}</div><div class="mt-1 text-base font-semibold">{{ impactAnalysis.public_files.toLocaleString() }}</div></div>
              </div>
              <Alert v-if="impactAnalysis.total_files === 0" class="mt-3" show-icon type="success" :message="$t('plugin.storage-migration.impactAnalysis.noFiles')" />
              <Alert v-if="!impactAnalysis.source_available || !impactAnalysis.target_available" class="mt-3" show-icon type="error" :message="$t('plugin.storage-migration.error.driverNotAvailable')" />
              <Alert v-if="impactAnalysis.private_files > 0" class="mt-3" show-icon type="warning" :message="$t('plugin.storage-migration.impactAnalysis.privateRisk', { count: impactAnalysis.private_files })" />
              <div v-if="impactAnalysis.scope === 'all' && impactAnalysis.tenant_breakdown.length > 0" class="mt-4 space-y-2">
                <div class="text-sm font-medium text-foreground">{{ $t('plugin.storage-migration.impactAnalysis.tenantBreakdown') }}</div>
                <div v-for="(item, index) in impactAnalysis.tenant_breakdown.slice(0, 5)" :key="`${item.tenant_id ?? 'platform'}-${index}`" class="rounded-lg border bg-accent/10 px-3 py-2 text-sm">
                  <div class="font-medium text-foreground">{{ item.tenant_id === null ? $t('plugin.storage-migration.impactAnalysis.platformScope') : $t('plugin.storage-migration.scope.tenant', { id: item.tenant_id }) }}</div>
                  <div class="text-xs text-muted-foreground">{{ $t('plugin.storage-migration.impactAnalysis.tenantItem', { count: item.file_count.toLocaleString(), size: formatBytes(item.size_bytes) }) }}</div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card :title="$t('plugin.storage-migration.panel.monitorTitle')">
          <div v-if="activeTasks.length > 0" class="space-y-3">
            <div v-for="task in activeTasks" :key="task.id" class="rounded-xl border bg-accent/10 p-3">
              <div class="mb-2 flex items-center justify-between text-xs text-muted-foreground"><span>#{{ task.id }}</span><Badge :status="getStatusColor(task.status)" :text="getStatusText(task.status)" /></div>
              <div class="text-sm font-medium text-foreground">{{ driverLabel(task.source_driver) }} -> {{ driverLabel(task.target_driver) }}</div>
              <div class="mb-2 text-xs text-muted-foreground">{{ getScopeText(task.scope) }}</div>
              <Progress :percent="getProgressPercent(task)" :status="task.status === 'completed' ? 'success' : ['paused', 'failed', 'cancelled'].includes(task.status) ? 'exception' : 'active'" :stroke-color="task.status === 'paused' ? '#faad14' : undefined" size="small" />
              <div class="mt-3 flex items-center justify-between">
                <Button size="small" type="link" @click="openDetail(task.id)">{{ $t('shared.common.detail') }}</Button>
                <Space :size="4">
                  <Button v-if="canPauseTask(task)" size="small" @click="onPause(task.id)"><template #icon><IconifyIcon icon="lucide:pause" class="h-3.5 w-3.5" /></template></Button>
                  <Button v-if="canResumeTask(task)" size="small" type="primary" @click="onResume(task.id)"><template #icon><IconifyIcon icon="lucide:play" class="h-3.5 w-3.5" /></template></Button>
                  <Button v-if="canCancelTask(task)" size="small" danger @click="onCancel(task.id)"><template #icon><IconifyIcon icon="lucide:x" class="h-3.5 w-3.5" /></template></Button>
                </Space>
              </div>
            </div>
          </div>
          <Empty v-else :description="$t('plugin.storage-migration.common.noActiveTasks')" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
        </Card>
      </div>

      <Card :title="$t('plugin.storage-migration.history.title')">
        <Table :data-source="tasks" :loading="loading" :pagination="{ current: currentPage, total: totalTasks, pageSize: 20, showTotal: (total: number) => $t('plugin.storage-migration.history.totalCount', { total }), onChange: onTaskPageChange }" row-key="id" size="middle" :custom-row="(record: MigrationTask) => ({ onClick: () => openDetail(record.id), style: { cursor: 'pointer' } })">
          <Table.Column :title="$t('plugin.storage-migration.common.taskId')" data-index="id" :width="76" />
          <Table.Column :title="$t('plugin.storage-migration.common.flow')" :width="250">
            <template #default="{ record }">{{ driverLabel(record.source_driver) }} -> {{ driverLabel(record.target_driver) }}</template>
          </Table.Column>
          <Table.Column :title="$t('plugin.storage-migration.task.scope')" :width="180">
            <template #default="{ record }">
              <div class="space-y-1">
                <div>{{ getScopeText(record.scope) }}</div>
                <div v-if="hasCleanupResult(record)" class="text-xs text-muted-foreground">{{ record.source_cleanup_completed_at ? $t('plugin.storage-migration.cleanup.completedSummary', { count: record.source_cleanup_deleted_files, errors: record.source_cleanup_error_count }) : $t('plugin.storage-migration.cleanup.startedSummary') }}</div>
              </div>
            </template>
          </Table.Column>
          <Table.Column :title="$t('plugin.storage-migration.task.progress')" :width="220">
            <template #default="{ record }"><div class="flex items-center gap-2"><Progress :percent="getProgressPercent(record)" :status="record.status === 'completed' ? 'success' : ['paused', 'failed', 'cancelled'].includes(record.status) ? 'exception' : 'active'" :stroke-color="record.status === 'paused' ? '#faad14' : undefined" class="mb-0 flex-1" size="small" /><span class="text-xs text-muted-foreground">{{ record.migrated_files }}/{{ record.total_files }}</span></div></template>
          </Table.Column>
          <Table.Column :title="$t('shared.common.status')" data-index="status" :width="120">
            <template #default="{ record }"><Badge :status="getStatusColor(record.status)" :text="getStatusText(record.status)" /></template>
          </Table.Column>
          <Table.Column :title="$t('shared.common.createdAt')" data-index="created_at" :width="170">
            <template #default="{ record }"><span class="text-xs text-muted-foreground">{{ formatTime(record.created_at) }}</span></template>
          </Table.Column>
          <Table.Column :title="$t('shared.common.operation')" :width="220">
            <template #default="{ record }">
              <Space :size="4" @click.stop>
                <Button size="small" type="link" @click="openDetail(record.id)">{{ $t('shared.common.detail') }}</Button>
                <Button v-if="canPauseTask(record)" size="small" @click="onPause(record.id)"><template #icon><IconifyIcon icon="lucide:pause" class="h-3.5 w-3.5" /></template></Button>
                <Button v-if="canResumeTask(record)" size="small" type="primary" @click="onResume(record.id)"><template #icon><IconifyIcon icon="lucide:play" class="h-3.5 w-3.5" /></template></Button>
                <Button v-if="canCancelTask(record)" size="small" danger @click="onCancel(record.id)"><template #icon><IconifyIcon icon="lucide:x" class="h-3.5 w-3.5" /></template></Button>
                <Button v-if="canRetryTask(record)" size="small" type="primary" @click="onRetryFailed(record.id)"><template #icon><IconifyIcon icon="lucide:refresh-cw" class="h-3.5 w-3.5" /></template></Button>
                <Button v-if="canRollbackTask(record)" size="small" danger @click="onRollback(record.id)"><template #icon><IconifyIcon icon="lucide:undo-2" class="h-3.5 w-3.5" /></template></Button>
                <Button v-if="canCleanupTask(record)" size="small" danger @click="onCleanupSource(record.id)"><template #icon><IconifyIcon icon="lucide:trash-2" class="h-3.5 w-3.5" /></template></Button>
              </Space>
            </template>
          </Table.Column>
          <template #emptyText><Empty :description="$t('plugin.storage-migration.history.empty')" /></template>
        </Table>
      </Card>
    </div>
  </Page>
</template>
