<script lang="ts" setup>
import type { MigrationLog, MigrationTask, StorageDriverInfo } from './types';

import { computed, onUnmounted, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import {
  Alert,
  Badge,
  Button,
  Descriptions,
  DescriptionsItem,
  Empty,
  Progress,
  Space,
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
  getScopeText,
  getStatusColor,
  getStatusText,
} from './data';

interface DrawerData {
  taskId: number;
  drivers: StorageDriverInfo[];
}

const LOG_PAGE_SIZE = 20;

const task = ref<MigrationTask | null>(null);
const loading = ref(false);
const drivers = ref<StorageDriverInfo[]>([]);
const logStatus = ref<'all' | 'failed' | 'skipped' | 'success'>('all');
const logPage = ref(1);

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: async (isOpen) => {
    if (!isOpen) {
      task.value = null;
      return;
    }
    const data = drawerApi.getData<DrawerData>();
    if (!data) {
      return;
    }
    drivers.value = data.drivers;
    logStatus.value = 'all';
    logPage.value = 1;
    await loadDetail(data.taskId);
  },
});

const logs = computed<MigrationLog[]>(() => task.value?.logs?.items ?? []);
const logsTotal = computed(() => task.value?.logs?.total ?? 0);

function driverLabel(name: string): string {
  return getDriverLabel(name, drivers.value);
}

function progressStatus(status: string): 'active' | 'exception' | 'success' {
  if (status === 'completed') return 'success';
  if (status === 'paused' || status === 'failed' || status === 'cancelled') {
    return 'exception';
  }
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
  const key = `plugin.storage-migration.log.status.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

function cleanupSummary(currentTask: MigrationTask): string {
  if (currentTask.source_cleanup_completed_at) {
    return $t('plugin.storage-migration.cleanup.completedSummary', {
      count: currentTask.source_cleanup_deleted_files,
      errors: currentTask.source_cleanup_error_count,
    });
  }
  if (currentTask.source_cleanup_started_at) {
    return $t('plugin.storage-migration.cleanup.startedSummary');
  }
  return $t('plugin.storage-migration.cleanup.notStartedSummary');
}

async function loadDetail(taskId: number) {
  loading.value = true;
  try {
    task.value = await getMigrationTaskApi(
      taskId,
      logStatus.value === 'all' ? undefined : logStatus.value,
      logPage.value,
      LOG_PAGE_SIZE,
    );
  } catch {
    // handled by request interceptor / 错误由请求拦截器处理
  } finally {
    loading.value = false;
  }
}

function onLogPageChange(page: number) {
  logPage.value = page;
}

function setLogStatusFilter(next: 'all' | 'failed' | 'success') {
  logStatus.value = next;
  logPage.value = 1;
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

watch(
  () => task.value?.status,
  (status) => {
    if (status && ACTIVE_STATUSES.includes(status)) {
      if (!pollTimer && task.value) {
        pollTimer = setInterval(() => void loadDetail(task.value!.id), 3000);
      }
      return;
    }
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  },
);

watch([logStatus, logPage], async () => {
  if (!task.value) return;
  await loadDetail(task.value.id);
});

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer);
  }
});
</script>

<template>
  <Drawer
    :title="
      task
        ? `${$t('plugin.storage-migration.task.title')} #${task.id}`
        : $t('plugin.storage-migration.task.title')
    "
    class="w-[760px]"
  >
    <Spin :spinning="loading">
      <template v-if="task">
        <div class="space-y-4">
          <div class="rounded-xl border bg-accent/20 p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
              <Badge
                :status="getStatusColor(task.status)"
                :text="getStatusText(task.status)"
              />
              <div class="text-right text-xs text-muted-foreground">
                <div>{{ driverLabel(task.source_driver) }} -> {{ driverLabel(task.target_driver) }}</div>
                <div>{{ getScopeText(task.scope) }}</div>
              </div>
            </div>
            <Progress
              :percent="getProgressPercent(task)"
              :status="progressStatus(task.status)"
              :stroke-color="progressColor(task.status)"
            />
          </div>

          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem :label="$t('plugin.storage-migration.task.scope')">
              {{ getScopeText(task.scope) }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storage-migration.task.concurrency')">
              {{ task.concurrency }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storage-migration.task.migratedFiles')">
              <span class="text-green-600">{{ task.migrated_files }}</span> /
              {{ task.total_files }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storage-migration.task.failedFiles')">
              <span :class="task.failed_files > 0 ? 'text-red-500' : ''">{{ task.failed_files }}</span>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storage-migration.task.migratedBytes')">
              {{ formatBytes(task.migrated_bytes) }} / {{ formatBytes(task.total_bytes) }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storage-migration.cleanup.title')">
              {{ cleanupSummary(task) }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storage-migration.task.startedAt')">
              {{ formatTime(task.started_at) }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storage-migration.task.completedAt')">
              {{ formatTime(task.completed_at) }}
            </DescriptionsItem>
          </Descriptions>

          <Alert
            v-if="task.error_message"
            type="error"
            show-icon
            :message="task.error_message"
          />
          <Alert
            v-if="task.source_cleanup_completed_at"
            type="success"
            show-icon
            :message="
              $t('plugin.storage-migration.cleanup.completedSummary', {
                count: task.source_cleanup_deleted_files,
                errors: task.source_cleanup_error_count,
              })
            "
          />

          <div class="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <h4 class="text-sm font-medium text-foreground">
                {{ $t('plugin.storage-migration.log.title') }}
              </h4>
              <Space :size="8">
                <Button
                  size="small"
                  :type="logStatus === 'all' ? 'primary' : 'default'"
                  @click="setLogStatusFilter('all')"
                >
                  {{ $t('plugin.storage-migration.log.filter.all') }}
                </Button>
                <Button
                  size="small"
                  :type="logStatus === 'failed' ? 'primary' : 'default'"
                  @click="setLogStatusFilter('failed')"
                >
                  {{ $t('plugin.storage-migration.log.filter.failed') }}
                </Button>
                <Button
                  size="small"
                  :type="logStatus === 'success' ? 'primary' : 'default'"
                  @click="setLogStatusFilter('success')"
                >
                  {{ $t('plugin.storage-migration.log.filter.success') }}
                </Button>
              </Space>
            </div>

            <Table
              v-if="logs.length > 0"
              :data-source="logs"
              :pagination="{
                current: logPage,
                total: logsTotal,
                pageSize: LOG_PAGE_SIZE,
                onChange: onLogPageChange,
              }"
              size="small"
              row-key="id"
            >
              <Table.Column
                :title="$t('plugin.storage-migration.log.filePath')"
                data-index="file_path"
                :ellipsis="true"
              />
              <Table.Column
                :title="$t('plugin.storage-migration.log.fileSize')"
                data-index="file_size"
                :width="120"
              >
                <template #default="{ record }">{{ formatBytes(record.file_size) }}</template>
              </Table.Column>
              <Table.Column
                :title="$t('shared.common.status')"
                data-index="status"
                :width="110"
              >
                <template #default="{ record }">
                  <Tag :color="getLogStatusColor(record.status)">
                    {{ getLogStatusText(record.status) }}
                  </Tag>
                </template>
              </Table.Column>
              <Table.Column
                :title="$t('plugin.storage-migration.log.error')"
                data-index="error_message"
                :ellipsis="true"
              />
            </Table>

            <Empty
              v-else
              :description="$t('plugin.storage-migration.log.empty')"
              :image="Empty.PRESENTED_IMAGE_SIMPLE"
            />
          </div>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
