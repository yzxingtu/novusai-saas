<script lang="ts" setup>
/**
 * Storage Migration Management Page
 *
 * Admin > Plugins > Storage Migration
 * - Create migration tasks (select source/target driver)
 * - Real-time progress display
 * - Task control (pause/resume/cancel)
 * - Migration history with detail drawer
 */
import type { MigrationTask, StorageDriverInfo } from './types';

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
  message,
  Modal,
  Progress,
  Select,
  SelectOption,
  Space,
  Table,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '@novus/plugin-shared';

import {
  cancelMigrationTaskApi,
  cleanupSourceFilesApi,
  createMigrationTaskApi,
  getStorageDriversApi,
  listMigrationTasksApi,
  pauseMigrationTaskApi,
  resumeMigrationTaskApi,
  retryFailedFilesApi,
  rollbackMigrationTaskApi,
} from './api';
import {
  ACTIVE_STATUSES,
  formatTime,
  getDriverLabel,
  getProgressPercent,
  getStatusColor,
  getStatusText,
  useColumns,
} from './data';
import DetailDrawer from './DetailDrawer.vue';

defineOptions({ name: 'StorageMigrationPage' });

const route = useRoute();

// ── Detail Drawer ─────────────────────────────────────────

const [DetailDrawerComp, detailDrawerApi] = useVbenDrawer({
  connectedComponent: DetailDrawer,
});

function openDetail(taskId: number) {
  detailDrawerApi
    .setData({ taskId, drivers: drivers.value })
    .open();
}

// ── State ─────────────────────────────────────────────────

const loading = ref(false);
const creating = ref(false);
const drivers = ref<StorageDriverInfo[]>([]);
const tasks = ref<MigrationTask[]>([]);
const totalTasks = ref(0);
const currentPage = ref(1);

// Create form
const sourceDriver = ref<string>('');
const targetDriver = ref<string>('');
const concurrency = ref(5);

// Polling
let pollTimer: ReturnType<typeof setInterval> | null = null;

// ── Computed ──────────────────────────────────────────────

const availableDrivers = computed(() =>
  drivers.value.filter((d) => d.is_available),
);

const targetDriverOptions = computed(() =>
  availableDrivers.value.filter((d) => d.name !== sourceDriver.value),
);

watch(sourceDriver, () => {
  if (
    targetDriver.value &&
    !targetDriverOptions.value.some((d) => d.name === targetDriver.value)
  ) {
    targetDriver.value = '';
  }
});

const columns = computed(() => useColumns());

// ── Data Loading ──────────────────────────────────────────

async function loadDrivers() {
  try {
    drivers.value = await getStorageDriversApi();
  } catch {
    // handled by request interceptor
  }
}

async function loadTasks() {
  loading.value = true;
  try {
    const result = await listMigrationTasksApi(currentPage.value);
    tasks.value = result.items ?? [];
    totalTasks.value = result.total ?? 0;
  } catch {
    // handled by request interceptor
  } finally {
    loading.value = false;
  }
}

// ── Polling for active tasks ──────────────────────────────

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    await loadTasks();
  }, 3000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

// ── Actions ───────────────────────────────────────────────

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
        message.success(
          $t('admin.storageMigration.task.created', {
            count: result.total_files,
          }),
        );
        await loadTasks();
        startPolling();
        if (result.task_id) {
          openDetail(result.task_id);
        }
      } catch {
        // handled by request interceptor
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
        message.success(
          $t('admin.storageMigration.action.cleanupDone', {
            count: result.deleted_files,
          }),
        );
        await loadTasks();
      } catch {
        // handled
      }
    },
  });
}

function driverLabel(name: string): string {
  return getDriverLabel(name, drivers.value);
}

function taskProgress(record: Record<string, unknown>): number {
  return getProgressPercent(record as unknown as MigrationTask);
}

// ── Lifecycle ─────────────────────────────────────────────

onMounted(async () => {
  await Promise.all([loadDrivers(), loadTasks()]);

  // Pre-fill from query params (navigated from impact modal)
  const qSource = route.query.source as string | undefined;
  const qTarget = route.query.target as string | undefined;
  if (qSource) sourceDriver.value = qSource;
  if (qTarget) targetDriver.value = qTarget;

  // Start polling if there are active tasks
  const hasActive = (tasks.value ?? []).some((t) =>
    ACTIVE_STATUSES.includes(t.status),
  );
  if (hasActive) {
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
      <!-- Create Migration Task -->
      <Card :title="$t('admin.storageMigration.task.create')">
        <div class="flex flex-wrap items-end gap-4">
          <div class="min-w-[180px]">
            <div class="mb-1 text-sm text-muted-foreground">
              {{ $t('admin.storageMigration.impactAnalysis.sourceDriver') }}
            </div>
            <Select
              v-model:value="sourceDriver"
              :placeholder="$t('shared.storage.selectDriver')"
              class="w-full"
            >
              <SelectOption
                v-for="d in availableDrivers"
                :key="d.name"
                :value="d.name"
              >
                {{ d.display_name || d.name }}
              </SelectOption>
            </Select>
          </div>

          <div class="flex items-center pb-1">
            <IconifyIcon
              icon="lucide:arrow-right"
              class="h-5 w-5 text-muted-foreground"
            />
          </div>

          <div class="min-w-[180px]">
            <div class="mb-1 text-sm text-muted-foreground">
              {{ $t('admin.storageMigration.impactAnalysis.targetDriver') }}
            </div>
            <Select
              v-model:value="targetDriver"
              :placeholder="$t('shared.storage.selectDriver')"
              :disabled="!sourceDriver"
              class="w-full"
            >
              <SelectOption
                v-for="d in targetDriverOptions"
                :key="d.name"
                :value="d.name"
              >
                {{ d.display_name || d.name }}
              </SelectOption>
            </Select>
          </div>

          <div class="min-w-[120px]">
            <div class="mb-1 text-sm text-muted-foreground">
              {{ $t('admin.storageMigration.task.concurrency') }}
            </div>
            <InputNumber v-model:value="concurrency" :min="1" :max="20" />
          </div>

          <Button
            type="primary"
            :loading="creating"
            :disabled="!sourceDriver || !targetDriver"
            @click="onCreateTask"
          >
            <template #icon>
              <IconifyIcon icon="lucide:play" />
            </template>
            {{ $t('admin.storageMigration.action.start') }}
          </Button>
        </div>

        <Alert
          v-if="availableDrivers.length < 2"
          type="warning"
          show-icon
          class="mt-4"
          :message="$t('admin.storageMigration.error.needTwoDrivers')"
        />
      </Card>

      <!-- Task List -->
      <Card :title="$t('admin.storageMigration.history.title')">
        <Table
          :columns="columns"
          :data-source="tasks"
          :loading="loading"
          :pagination="{
            current: currentPage,
            total: totalTasks,
            pageSize: 20,
            onChange: (p: number) => {
              currentPage = p;
              loadTasks();
            },
          }"
          row-key="id"
          size="small"
          :custom-row="
            (record: Record<string, unknown>) => ({
              onClick: () => openDetail(record.id as number),
              style: { cursor: 'pointer' },
            })
          "
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'source_driver'">
              <Tag>{{ driverLabel(record.source_driver) }}</Tag>
            </template>
            <template v-else-if="column.dataIndex === 'target_driver'">
              <Tag color="blue">{{
                driverLabel(record.target_driver)
              }}</Tag>
            </template>
            <template v-else-if="column.key === 'progress'">
              <div class="flex items-center gap-2">
                <Progress
                  :percent="taskProgress(record)"
                  :size="'small'"
                  :status="
                    record.status === 'failed'
                      ? 'exception'
                      : record.status === 'completed'
                        ? 'success'
                        : 'active'
                  "
                  class="mb-0 flex-1"
                />
                <span class="whitespace-nowrap text-xs text-muted-foreground">
                  {{ record.migrated_files }}/{{ record.total_files }}
                </span>
              </div>
            </template>
            <template v-else-if="column.dataIndex === 'status'">
              <Badge
                :status="getStatusColor(record.status)"
                :text="getStatusText(record.status)"
              />
            </template>
            <template v-else-if="column.dataIndex === 'created_at'">
              {{ formatTime(record.created_at) }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <Space :size="4">
                <Tooltip
                  v-if="record.status === 'running'"
                  :title="$t('admin.storageMigration.action.pause')"
                >
                  <Button
                    size="small"
                    @click.stop="onPause(record.id)"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:pause" class="size-3.5" />
                    </template>
                  </Button>
                </Tooltip>
                <Tooltip
                  v-if="record.status === 'paused'"
                  :title="$t('admin.storageMigration.action.resume')"
                >
                  <Button
                    size="small"
                    type="primary"
                    @click.stop="onResume(record.id)"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:play" class="size-3.5" />
                    </template>
                  </Button>
                </Tooltip>
                <Tooltip
                  v-if="['running', 'paused'].includes(record.status)"
                  :title="$t('admin.storageMigration.action.cancel')"
                >
                  <Button
                    size="small"
                    danger
                    @click.stop="onCancel(record.id)"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:x" class="size-3.5" />
                    </template>
                  </Button>
                </Tooltip>
                <Tooltip
                  v-if="
                    record.status === 'completed' ||
                    record.status === 'failed'
                  "
                  :title="$t('admin.storageMigration.action.rollback')"
                >
                  <Button
                    size="small"
                    danger
                    @click.stop="onRollback(record.id)"
                  >
                    <template #icon>
                      <IconifyIcon
                        icon="lucide:undo-2"
                        class="size-3.5"
                      />
                    </template>
                  </Button>
                </Tooltip>
                <Tooltip
                  v-if="
                    record.failed_files > 0 &&
                    ['completed', 'failed'].includes(record.status)
                  "
                  :title="$t('admin.storageMigration.action.retry')"
                >
                  <Button
                    size="small"
                    type="primary"
                    @click.stop="onRetryFailed(record.id)"
                  >
                    <template #icon>
                      <IconifyIcon
                        icon="lucide:refresh-cw"
                        class="size-3.5"
                      />
                    </template>
                  </Button>
                </Tooltip>
                <Tooltip
                  v-if="record.status === 'completed'"
                  :title="$t('admin.storageMigration.action.cleanup')"
                >
                  <Button
                    size="small"
                    danger
                    @click.stop="onCleanupSource(record.id)"
                  >
                    <template #icon>
                      <IconifyIcon
                        icon="lucide:trash-2"
                        class="size-3.5"
                      />
                    </template>
                  </Button>
                </Tooltip>
              </Space>
            </template>
          </template>

          <template #emptyText>
            <Empty :description="$t('admin.storageMigration.history.empty')" />
          </template>
        </Table>
      </Card>
    </div>
  </Page>
</template>
