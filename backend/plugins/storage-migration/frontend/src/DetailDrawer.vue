<script lang="ts" setup>
/**
 * Storage Migration Task Detail Drawer
 *
 * Shows task progress, metadata, error messages, and failed file logs.
 */
import type { MigrationLog, MigrationTask, StorageDriverInfo } from './types';

import { computed, onUnmounted, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import {
  Alert,
  Badge,
  Descriptions,
  DescriptionsItem,
  Divider,
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

const logs = computed<MigrationLog[]>(() => {
  return task.value?.logs?.items ?? [];
});

const logsTotal = computed(() => task.value?.logs?.total ?? 0);

async function loadDetail(taskId: number) {
  loading.value = true;
  try {
    task.value = await getMigrationTaskApi(taskId);
  } catch {
    // handled by request interceptor
  } finally {
    loading.value = false;
  }
}

// Polling for active tasks
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
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function driverLabel(name: string): string {
  return getDriverLabel(name, drivers.value);
}

onUnmounted(() => {
  stopPolling();
});

defineExpose({ loadDetail });
</script>

<template>
  <Drawer
    :title="
      task
        ? `${$t('admin.storageMigration.task.title')} #${task.id}`
        : $t('admin.storageMigration.task.title')
    "
    class="w-[600px]"
  >
    <Spin :spinning="loading">
      <template v-if="task">
        <div class="space-y-4">
          <!-- Progress -->
          <div v-if="ACTIVE_STATUSES.includes(task.status)">
            <Progress
              :percent="getProgressPercent(task)"
              :status="task.status === 'paused' ? 'exception' : 'active'"
              :stroke-color="
                task.status === 'paused' ? '#faad14' : undefined
              "
            />
          </div>

          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem :label="$t('shared.common.status')">
              <Badge
                :status="getStatusColor(task.status)"
                :text="getStatusText(task.status)"
              />
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.storageMigration.task.concurrency')"
            >
              {{ task.concurrency }}
            </DescriptionsItem>
            <DescriptionsItem
              :label="
                $t('admin.storageMigration.impactAnalysis.sourceDriver')
              "
            >
              <Tag>{{ driverLabel(task.source_driver) }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem
              :label="
                $t('admin.storageMigration.impactAnalysis.targetDriver')
              "
            >
              <Tag color="blue">{{ driverLabel(task.target_driver) }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.storageMigration.task.migratedFiles')"
            >
              <span class="text-green-600">{{ task.migrated_files }}</span>
              / {{ task.total_files }}
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.storageMigration.task.failedFiles')"
            >
              <span :class="task.failed_files > 0 ? 'text-red-500' : ''">
                {{ task.failed_files }}
              </span>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.storageMigration.task.migratedBytes')"
            >
              {{ formatBytes(task.migrated_bytes) }} /
              {{ formatBytes(task.total_bytes) }}
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.storageMigration.task.startedAt')"
            >
              {{ formatTime(task.started_at) }}
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.storageMigration.task.completedAt')"
            >
              {{ formatTime(task.completed_at) }}
            </DescriptionsItem>
          </Descriptions>

          <!-- Error message -->
          <Alert
            v-if="task.error_message"
            type="error"
            show-icon
            :message="task.error_message"
          />

          <!-- Migration logs -->
          <div v-if="logs.length > 0">
            <Divider>
              {{ $t('admin.storageMigration.log.title') }}
              ({{ logsTotal }})
            </Divider>
            <Table
              :data-source="logs"
              :pagination="false"
              size="small"
              row-key="id"
            >
              <Table.Column
                :title="$t('admin.storageMigration.log.filePath')"
                data-index="file_path"
                :ellipsis="true"
              />
              <Table.Column
                :title="$t('admin.storageMigration.log.fileSize')"
                data-index="file_size"
              >
                <template #default="{ record }">
                  {{ formatBytes(record.file_size) }}
                </template>
              </Table.Column>
              <Table.Column
                :title="$t('shared.common.status')"
                data-index="status"
              >
                <template #default="{ record }">
                  <Tag
                    :color="
                      record.status === 'success'
                        ? 'green'
                        : record.status === 'failed'
                          ? 'red'
                          : 'default'
                    "
                  >
                    {{ record.status }}
                  </Tag>
                </template>
              </Table.Column>
              <Table.Column
                :title="$t('admin.storageMigration.log.error')"
                data-index="error_message"
                :ellipsis="true"
              />
            </Table>
          </div>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
