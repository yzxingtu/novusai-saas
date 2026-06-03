/**
 * Storage Migration - helpers, column definitions, status mappings / 辅助、列定义、状态映射
 */
import type { MigrationTask, StorageDriverInfo } from './types';

import { $t } from '@novus/plugin-shared';

// ============ Formatters / 格式化 ============

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(1)} ${units[i]}`;
}

export function formatTime(iso: string | null): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString();
}

// ============ Status / 状态 ============

export type BadgeStatus =
  | 'default'
  | 'error'
  | 'processing'
  | 'success'
  | 'warning';

const STATUS_COLOR_MAP: Record<string, BadgeStatus> = {
  pending: 'default',
  running: 'processing',
  paused: 'warning',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
  rolling_back: 'processing',
};

export function getStatusColor(status: string): BadgeStatus {
  return STATUS_COLOR_MAP[status] ?? 'default';
}

export function getStatusText(status: string): string {
  return $t(`plugin.storage-migration.task.status.${status}`);
}

export function getScopeText(scope: null | string | undefined): string {
  const normalized = String(scope || 'all').trim();
  if (!normalized || normalized === 'all') {
    return $t('plugin.storage-migration.scope.all');
  }
  if (normalized.startsWith('tenant:')) {
    const tenantId = normalized.split(':', 2)[1] || '-';
    return $t('plugin.storage-migration.scope.tenant', { id: tenantId });
  }
  return normalized;
}

// ============ Drivers / 存储驱动 ============

function translateDriverDisplayName(
  displayName: null | string | undefined,
  fallback: string,
): string {
  const raw = typeof displayName === 'string' ? displayName.trim() : '';
  if (!raw) return fallback;
  if (!raw.startsWith('storage.driver.')) return raw;

  const i18nKey = `shared.${raw}`;
  const translated = $t(i18nKey);
  return translated === i18nKey ? fallback : translated;
}

export function getDriverLabel(
  name: string,
  drivers: StorageDriverInfo[],
): string {
  const driver = drivers.find((d) => d.name === name);
  return translateDriverDisplayName(driver?.display_name, name);
}

// ============ Progress / 进度 ============

export function getProgressPercent(task: MigrationTask): number {
  if (task.total_files === 0) return 0;
  return Math.round(
    ((task.migrated_files + task.failed_files + task.skipped_files) /
      task.total_files) *
      100,
  );
}

export const ACTIVE_STATUSES = ['running', 'paused', 'rolling_back'];

export function hasCleanupResult(task: MigrationTask): boolean {
  return Boolean(
    task.source_cleanup_started_at ||
      task.source_cleanup_completed_at ||
      task.source_cleanup_deleted_files > 0 ||
      task.source_cleanup_error_count > 0,
  );
}

// ============ Table Columns / 表格列 ============

export function useColumns() {
  return [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 60,
    },
    {
      title: $t('plugin.storage-migration.impactAnalysis.sourceDriver'),
      dataIndex: 'source_driver',
      width: 120,
    },
    {
      title: $t('plugin.storage-migration.impactAnalysis.targetDriver'),
      dataIndex: 'target_driver',
      width: 120,
    },
    {
      title: $t('plugin.storage-migration.task.progress'),
      key: 'progress',
      width: 200,
    },
    {
      title: $t('shared.common.status'),
      dataIndex: 'status',
      width: 100,
    },
    {
      title: $t('shared.common.createdAt'),
      dataIndex: 'created_at',
      width: 160,
    },
    {
      title: $t('shared.common.operation'),
      key: 'actions',
      width: 200,
    },
  ];
}
