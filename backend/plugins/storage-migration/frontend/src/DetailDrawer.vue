<script lang="ts" setup>
import type { MigrationLog, MigrationTask, StorageDriverInfo } from './types';

import { computed, onUnmounted, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import {
  Alert,
  Badge,
  Descriptions,
  DescriptionsItem,
  Empty,
  Progress,
  Spin,
  Table,
  Tag,
} from 'ant-design-vue';

import { $t } from '@novus/plugin-shared';

import { getMigrationTaskApi } from './api';
import {
  ACTIVE_STATUSES,
  formatBytes,
  formatTime,
  getDriverLabel,
  getProgressPercent,
  getStatusColor,
  getStatusText,
} from './data';

interface DrawerData {
  taskId: number;
  drivers: StorageDriverInfo[];
}

const task = ref<MigrationTask | null>(null);
const loading = ref(false);
const drivers = ref<StorageDriverInfo[]>([]);

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: async (isOpen) => {
    if (!isOpen) {
      task.value = null;
      return;
    }
    const data = drawerApi.getData<DrawerData>();
    if (data) {
      drivers.value = data.drivers;
      await loadDetail(data.taskId);
    }
  },
});

const logs = computed<MigrationLog[]>(() => task.value?.logs?.items ?? []);
const logsTotal = computed(() => task.value?.logs?.total ?? 0);

function driverLabel(name: string): string {
  return getDriverLabel(name, drivers.value);
}

function progressStatus(status: string): 'active' | 'exception' | 'success' {
  if (status === 'completed') return 'success';
  if (status === 'paused' || status === 'failed' || status === 'cancelled') return 'exception';
  return 'active';
}

function progressColor(status: string): string | undefined {
  return status === 'paused' ? '#faad14' : undefined;
}

function getLogStatusColor(status: string): string {
  if (status === 'success') return 'green';
  if (status === 'failed') return 'red';
  if (status === 'skipped') return 'gold';
  return 'default';
}

function getLogStatusText(status: string): string {
  const key = `admin.storageMigration.log.status.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

async function loadDetail(taskId: number) {
  loading.value = true;
  try {
    task.value = await getMigrationTaskApi(taskId);
  } catch {
    // handled by interceptor / 已由拦截器处理
  } finally {
    loading.value = false;
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

watch(
  () => task.value?.status,
  (status) => {
    if (status && ACTIVE_STATUSES.includes(status)) {
      startPolling();
    } else {
      stopPolling();
    }
  },
);

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    if (task.value) {
      await loadDetail(task.value.id);
    }
  }, 3000);
}

function stopPolling() {
  if (!pollTimer) return;
  clearInterval(pollTimer);
  pollTimer = null;
}

onUnmounted(() => {
  stopPolling();
});

defineExpose({ loadDetail });
</script>

<template>
  <Drawer
    :title="task ? `${$t('admin.storageMigration.task.title')} #${task.id}` : $t('admin.storageMigration.task.title')"
    class="w-[680px]"
  >
    <Spin :spinning="loading">
      <template v-if="task">
        <div class="space-y-4">
          <div class="rounded-xl border bg-accent/20 p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
              <Badge :status="getStatusColor(task.status)" :text="getStatusText(task.status)" />
              <span class="text-xs text-muted-foreground">
                {{ driverLabel(task.source_driver) }} -> {{ driverLabel(task.target_driver) }}
              </span>
            </div>
            <Progress
              :percent="getProgressPercent(task)"
              :status="progressStatus(task.status)"
              :stroke-color="progressColor(task.status)"
            />
          </div>

          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem :label="$t('admin.storageMigration.impactAnalysis.sourceDriver')">
              <Tag>{{ driverLabel(task.source_driver) }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('admin.storageMigration.impactAnalysis.targetDriver')">
              <Tag color="blue">{{ driverLabel(task.target_driver) }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('admin.storageMigration.task.concurrency')">{{ task.concurrency }}</DescriptionsItem>
            <DescriptionsItem :label="$t('admin.storageMigration.task.migratedFiles')">
              <span class="text-green-600">{{ task.migrated_files }}</span> / {{ task.total_files }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('admin.storageMigration.task.failedFiles')">
              <span :class="task.failed_files > 0 ? 'text-red-500' : ''">{{ task.failed_files }}</span>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('admin.storageMigration.task.migratedBytes')">
              {{ formatBytes(task.migrated_bytes) }} / {{ formatBytes(task.total_bytes) }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('admin.storageMigration.task.startedAt')">{{ formatTime(task.started_at) }}</DescriptionsItem>
            <DescriptionsItem :label="$t('admin.storageMigration.task.completedAt')">{{ formatTime(task.completed_at) }}</DescriptionsItem>
          </Descriptions>

          <Alert v-if="task.error_message" type="error" show-icon :message="task.error_message" />

          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <h4 class="text-sm font-medium text-foreground">{{ $t('admin.storageMigration.log.title') }}</h4>
              <span class="text-xs text-muted-foreground">{{ logsTotal }}</span>
            </div>

            <Table v-if="logs.length > 0" :data-source="logs" :pagination="false" size="small" row-key="id">
              <Table.Column :title="$t('admin.storageMigration.log.filePath')" data-index="file_path" :ellipsis="true" />
              <Table.Column :title="$t('admin.storageMigration.log.fileSize')" data-index="file_size" :width="120">
                <template #default="{ record }">{{ formatBytes(record.file_size) }}</template>
              </Table.Column>
              <Table.Column :title="$t('shared.common.status')" data-index="status" :width="100">
                <template #default="{ record }">
                  <Tag :color="getLogStatusColor(record.status)">{{ getLogStatusText(record.status) }}</Tag>
                </template>
              </Table.Column>
              <Table.Column :title="$t('admin.storageMigration.log.error')" data-index="error_message" :ellipsis="true" />
            </Table>

            <Empty
              v-else
              :description="$t('admin.storageMigration.log.empty')"
              :image="Empty.PRESENTED_IMAGE_SIMPLE"
            />
          </div>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
