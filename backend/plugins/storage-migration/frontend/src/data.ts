/**
 * Storage Migration - helpers, column definitions, status mappings
 */
import type { MigrationTask, StorageDriverInfo } from './types';

import { $t } from '@novus/plugin-shared';

// ============ Formatters ============

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

// ============ Status ============

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
  return $t(`admin.storageMigration.task.status.${status}`);
}

// ============ Drivers ============

export function getDriverLabel(
  name: string,
  drivers: StorageDriverInfo[],
): string {
  const driver = drivers.find((d) => d.name === name);
  return driver?.display_name || name;
}

// ============ Progress ============

export function getProgressPercent(task: MigrationTask): number {
  if (task.total_files === 0) return 0;
  return Math.round(
    ((task.migrated_files + task.failed_files + task.skipped_files) /
      task.total_files) *
      100,
  );
}

export const ACTIVE_STATUSES = ['running', 'paused', 'rolling_back'];

// ============ Table Columns ============

export function useColumns() {
  return [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 60,
    },
    {
      title: $t('admin.storageMigration.impactAnalysis.sourceDriver'),
      dataIndex: 'source_driver',
      width: 120,
    },
    {
      title: $t('admin.storageMigration.impactAnalysis.targetDriver'),
      dataIndex: 'target_driver',
      width: 120,
    },
    {
      title: $t('admin.storageMigration.task.progress'),
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
