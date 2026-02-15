<script setup lang="ts">
import { ref, computed } from 'vue';

import { $t } from '#/locales';

import {
  Drawer,
  Descriptions,
  Tag,
  Table,
  Alert,
  Tabs,
  Button,
  Spin,
  message,
} from 'ant-design-vue';

import { IconifyIcon } from '@vben/icons';

import type { CrudRecordDetail, FileManifestItem } from '#/api/admin/crud-records';

import { getCrudRecordDetailApi } from '#/api/admin/crud-records';

const T = 'admin.dev.crudGenerator.records';

// ============================================================
// 状态
// ============================================================

const visible = ref(false);
const loading = ref(false);
const record = ref<CrudRecordDetail | null>(null);
const activeTab = ref('overview');

// ============================================================
// 公开方法
// ============================================================

async function open(recordId: number) {
  visible.value = true;
  loading.value = true;
  activeTab.value = 'overview';
  try {
    const res = await getCrudRecordDetailApi(recordId);
    record.value = (res as unknown as { data: CrudRecordDetail }).data;
  } catch {
    message.error($t(`${T}.loadFailed`));
  } finally {
    loading.value = false;
  }
}

function close() {
  visible.value = false;
  record.value = null;
}

defineExpose({ open, close });

// ============================================================
// 计算属性
// ============================================================

function getTypeColor(type: string): string {
  const map: Record<string, string> = {
    preview: 'blue',
    generate: 'green',
    rollback: 'orange',
    delete: 'red',
  };
  return map[type] || 'default';
}

function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    success: 'success',
    partial_failure: 'warning',
    failed: 'error',
    rolled_back: 'default',
  };
  return map[status] || 'default';
}

function getTypeLabel(type: string): string {
  return $t(`${T}.type.${type}`) || type;
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    success: 'success',
    partial_failure: 'partialFailure',
    failed: 'failed',
    rolled_back: 'rolledBack',
  };
  return $t(`${T}.status.${map[status] || status}`) || status;
}

function getOperationColor(op: string): string {
  const map: Record<string, string> = {
    written: 'green',
    merged: 'blue',
    skipped: 'default',
    error: 'red',
    preview: 'purple',
  };
  return map[op] || 'default';
}

function getOperationLabel(op: string): string {
  return $t(`${T}.fileOp.${op}`) || op;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTime(time: string | null): string {
  if (!time) return '-';
  return new Date(time).toLocaleString();
}

const fileManifestColumns = computed(() => [
  {
    title: $t(`${T}.fileCol.path`),
    dataIndex: 'path',
    ellipsis: true,
  },
  {
    title: $t(`${T}.fileCol.operation`),
    dataIndex: 'operation',
    width: 100,
  },
  {
    title: $t(`${T}.fileCol.size`),
    dataIndex: 'size',
    width: 100,
    align: 'right' as const,
  },
]);

function copyConfig() {
  if (!record.value?.config_snapshot) return;
  navigator.clipboard
    .writeText(JSON.stringify(record.value.config_snapshot, null, 2))
    .then(() => message.success($t(`${T}.configCopied`)));
}
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="$t(`${T}.detail.title`)"
    width="720"
    @close="close"
  >
    <Spin :spinning="loading">
      <template v-if="record">
        <Tabs v-model:activeKey="activeTab">
          <!-- 概览 -->
          <Tabs.TabPane key="overview" :tab="$t(`${T}.detail.overview`)">
            <Descriptions bordered size="small" :column="2">
              <Descriptions.Item :label="$t(`${T}.column.operationType`)">
                <Tag :color="getTypeColor(record.operation_type)">
                  {{ getTypeLabel(record.operation_type) }}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item :label="$t(`${T}.column.status`)">
                <Tag :color="getStatusColor(record.status)">
                  {{ getStatusLabel(record.status) }}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item :label="$t(`${T}.column.moduleName`)">
                <span class="font-mono">{{ record.module_name || '-' }}</span>
              </Descriptions.Item>
              <Descriptions.Item :label="$t(`${T}.column.tableName`)">
                <span class="font-mono">{{ record.table_name || '-' }}</span>
              </Descriptions.Item>
              <Descriptions.Item :label="$t(`${T}.column.fileCount`)">
                {{ record.file_count }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t(`${T}.column.duration`)">
                {{ formatDuration(record.duration_ms) }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t(`${T}.column.operator`)">
                {{ record.operator_name || '-' }}
              </Descriptions.Item>
              <Descriptions.Item :label="$t(`${T}.column.createdAt`)">
                {{ formatTime(record.created_at) }}
              </Descriptions.Item>
            </Descriptions>

            <!-- 错误详情 -->
            <Alert
              v-if="record.error_detail"
              type="error"
              :message="$t(`${T}.detail.errorDetail`)"
              :description="record.error_detail"
              show-icon
              class="mt-4"
            />
          </Tabs.TabPane>

          <!-- 文件清单 -->
          <Tabs.TabPane key="files" :tab="$t(`${T}.detail.fileManifest`)">
            <Table
              v-if="record.file_manifest && record.file_manifest.length > 0"
              :columns="fileManifestColumns"
              :data-source="record.file_manifest"
              :pagination="false"
              size="small"
              row-key="path"
            >
              <template #bodyCell="{ column, record: row }">
                <template v-if="column.dataIndex === 'path'">
                  <span class="font-mono text-xs">{{ (row as FileManifestItem).path }}</span>
                </template>
                <template v-else-if="column.dataIndex === 'operation'">
                  <Tag :color="getOperationColor((row as FileManifestItem).operation)">
                    {{ getOperationLabel((row as FileManifestItem).operation) }}
                  </Tag>
                </template>
                <template v-else-if="column.dataIndex === 'size'">
                  {{ formatSize((row as FileManifestItem).size) }}
                </template>
              </template>
            </Table>
            <div v-else class="py-8 text-center text-muted-foreground">
              {{ $t(`${T}.detail.noFiles`) }}
            </div>
          </Tabs.TabPane>

          <!-- 配置快照 -->
          <Tabs.TabPane key="config" :tab="$t(`${T}.detail.configSnapshot`)">
            <div v-if="record.config_snapshot" class="relative">
              <Button
                size="small"
                class="absolute right-0 top-0 z-10"
                @click="copyConfig"
              >
                <IconifyIcon icon="lucide:copy" class="mr-1" />
                {{ $t(`${T}.detail.copyConfig`) }}
              </Button>
              <pre class="mt-8 max-h-[500px] overflow-auto rounded bg-gray-50 p-3 text-xs dark:bg-gray-900">{{ JSON.stringify(record.config_snapshot, null, 2) }}</pre>
            </div>
            <div v-else class="py-8 text-center text-muted-foreground">
              {{ $t(`${T}.detail.noConfig`) }}
            </div>
          </Tabs.TabPane>
        </Tabs>
      </template>
    </Spin>
  </Drawer>
</template>
