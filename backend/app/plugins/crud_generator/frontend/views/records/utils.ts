/**
 * Records — 共享工具函数
 *
 * 提取自 index.vue 和 record-detail-drawer.vue 的重复函数。
 */

import { $t } from '#/locales';

const T = 'admin.dev.crudGenerator.records';

const TYPE_COLOR_MAP: Record<string, string> = {
  preview: 'blue',
  generate: 'green',
  rollback: 'orange',
  delete: 'red',
};

const STATUS_COLOR_MAP: Record<string, string> = {
  success: 'success',
  partial_failure: 'warning',
  failed: 'error',
  rolled_back: 'default',
};

const STATUS_KEY_MAP: Record<string, string> = {
  success: 'success',
  partial_failure: 'partialFailure',
  failed: 'failed',
  rolled_back: 'rolledBack',
};

export function getTypeColor(type: string): string {
  return TYPE_COLOR_MAP[type] || 'default';
}

export function getStatusColor(status: string): string {
  return STATUS_COLOR_MAP[status] || 'default';
}

export function getTypeLabel(type: string): string {
  return $t(`${T}.type.${type}`) || type;
}

export function getStatusLabel(status: string): string {
  return $t(`${T}.status.${STATUS_KEY_MAP[status] || status}`) || status;
}

export function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatTime(time: string | null): string {
  if (!time) return '-';
  return new Date(time).toLocaleString();
}

export function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
