/**
 * Storage Migration Plugin - API functions
 */
import type {
  CreateTaskParams,
  ImpactAnalysis,
  MigrationTask,
  StorageDriverInfo,
} from './types';

import { requestClient } from '@novus/plugin-shared';

const PLUGIN_API_BASE = '/admin/plugins/storage-migration/api';

/** Get available storage drivers */
export function getStorageDriversApi(): Promise<StorageDriverInfo[]> {
  return requestClient.get('/admin/configs/storage/drivers');
}

/** Impact analysis before switching storage */
export function getImpactAnalysisApi(
  sourceDriver: string,
  targetDriver: string,
  scope = 'all',
) {
  return requestClient.get<ImpactAnalysis>(
    `${PLUGIN_API_BASE}/impact-analysis`,
    { params: { source_driver: sourceDriver, target_driver: targetDriver, scope } },
  );
}

/** Create and start a migration task */
export function createMigrationTaskApi(params: CreateTaskParams) {
  return requestClient.post<{ task_id: number; total_files: number; total_bytes: number; status: string }>(
    `${PLUGIN_API_BASE}/tasks`,
    params,
  );
}

/** List migration tasks */
export function listMigrationTasksApi(page = 1, pageSize = 20) {
  return requestClient.get<{ items: MigrationTask[]; total: number; page: number; page_size: number }>(
    `${PLUGIN_API_BASE}/tasks`,
    { params: { page, page_size: pageSize } },
  );
}

/** Get task detail */
export function getMigrationTaskApi(
  taskId: number,
  logStatus?: string,
  logPage = 1,
  logPageSize = 50,
) {
  return requestClient.get<MigrationTask>(
    `${PLUGIN_API_BASE}/tasks/${taskId}`,
    { params: { log_status: logStatus, log_page: logPage, log_page_size: logPageSize } },
  );
}

/** Pause a running task */
export function pauseMigrationTaskApi(taskId: number) {
  return requestClient.post<{ status: string; task_id: number }>(
    `${PLUGIN_API_BASE}/tasks/${taskId}/pause`,
  );
}

/** Resume a paused task */
export function resumeMigrationTaskApi(taskId: number) {
  return requestClient.post<{ status: string; task_id: number }>(
    `${PLUGIN_API_BASE}/tasks/${taskId}/resume`,
  );
}

/** Cancel a task */
export function cancelMigrationTaskApi(taskId: number) {
  return requestClient.post<{ status: string; task_id: number }>(
    `${PLUGIN_API_BASE}/tasks/${taskId}/cancel`,
  );
}

/** Retry failed files */
export function retryFailedFilesApi(taskId: number) {
  return requestClient.post<{ status: string; task_id: number }>(
    `${PLUGIN_API_BASE}/tasks/${taskId}/retry-failed`,
  );
}

/** Rollback a completed migration */
export function rollbackMigrationTaskApi(taskId: number) {
  return requestClient.post<{ status: string; task_id: number; reverted_files: number }>(
    `${PLUGIN_API_BASE}/tasks/${taskId}/rollback`,
  );
}

/** Delete source files after migration */
export function cleanupSourceFilesApi(taskId: number) {
  return requestClient.delete<{ task_id: number; deleted_files: number; errors: number }>(
    `${PLUGIN_API_BASE}/tasks/${taskId}/source-files`,
  );
}
