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

interface ApiEnvelope<T = unknown> {
  code: number;
  data: T;
  message: string;
}

function isApiEnvelope(value: unknown): value is ApiEnvelope {
  if (!value || typeof value !== 'object') return false;
  return 'code' in value && 'data' in value && 'message' in value;
}

function unwrapApiData<T>(payload: unknown): T {
  let current: unknown = payload;
  let depth = 0;
  while (isApiEnvelope(current) && depth < 8) {
    current = current.data;
    depth += 1;
  }
  return current as T;
}

/** Get available storage drivers */
export function getStorageDriversApi(): Promise<StorageDriverInfo[]> {
  return requestClient
    .get<unknown>('/admin/configs/storage/drivers')
    .then((res) => unwrapApiData<StorageDriverInfo[]>(res));
}

/** Impact analysis before switching storage */
export function getImpactAnalysisApi(
  sourceDriver: string,
  targetDriver: string,
  scope = 'all',
) {
  return requestClient
    .get<unknown>(
      `${PLUGIN_API_BASE}/impact-analysis`,
      { params: { source_driver: sourceDriver, target_driver: targetDriver, scope } },
    )
    .then((res) => unwrapApiData<ImpactAnalysis>(res));
}

/** Create and start a migration task */
export function createMigrationTaskApi(params: CreateTaskParams) {
  return requestClient
    .post<unknown>(
      `${PLUGIN_API_BASE}/tasks`,
      params,
    )
    .then((res) =>
      unwrapApiData<{
        status: string;
        task_id: number;
        total_bytes: number;
        total_files: number;
      }>(res),
    );
}

/** List migration tasks */
export function listMigrationTasksApi(page = 1, pageSize = 20) {
  return requestClient
    .get<unknown>(
      `${PLUGIN_API_BASE}/tasks`,
      { params: { 'page[number]': page, 'page[size]': pageSize } },
    )
    .then((res) =>
      unwrapApiData<{
        items: MigrationTask[];
        page: number;
        page_size: number;
        total: number;
      }>(res),
    );
}

/** Get task detail */
export function getMigrationTaskApi(
  taskId: number,
  logStatus?: string,
  logPage = 1,
  logPageSize = 50,
) {
  return requestClient
    .get<unknown>(
      `${PLUGIN_API_BASE}/tasks/${taskId}`,
      {
        params: {
          log_status: logStatus,
          'log_page[number]': logPage,
          'log_page[size]': logPageSize,
        },
      },
    )
    .then((res) => unwrapApiData<MigrationTask>(res));
}

/** Pause a running task */
export function pauseMigrationTaskApi(taskId: number) {
  return requestClient
    .post<unknown>(
      `${PLUGIN_API_BASE}/tasks/${taskId}/pause`,
    )
    .then((res) => unwrapApiData<{ status: string; task_id: number }>(res));
}

/** Resume a paused task */
export function resumeMigrationTaskApi(taskId: number) {
  return requestClient
    .post<unknown>(
      `${PLUGIN_API_BASE}/tasks/${taskId}/resume`,
    )
    .then((res) => unwrapApiData<{ status: string; task_id: number }>(res));
}

/** Cancel a task */
export function cancelMigrationTaskApi(taskId: number) {
  return requestClient
    .post<unknown>(
      `${PLUGIN_API_BASE}/tasks/${taskId}/cancel`,
    )
    .then((res) => unwrapApiData<{ status: string; task_id: number }>(res));
}

/** Retry failed files */
export function retryFailedFilesApi(taskId: number) {
  return requestClient
    .post<unknown>(
      `${PLUGIN_API_BASE}/tasks/${taskId}/retry-failed`,
    )
    .then((res) => unwrapApiData<{ status: string; task_id: number }>(res));
}

/** Rollback a completed migration */
export function rollbackMigrationTaskApi(taskId: number) {
  return requestClient
    .post<unknown>(
      `${PLUGIN_API_BASE}/tasks/${taskId}/rollback`,
    )
    .then((res) =>
      unwrapApiData<{
        reverted_files: number;
        status: string;
        task_id: number;
        target_delete_errors?: number;
      }>(res),
    );
}

/** Delete source files after migration */
export function cleanupSourceFilesApi(taskId: number) {
  return requestClient
    .delete<unknown>(
      `${PLUGIN_API_BASE}/tasks/${taskId}/source-files`,
    )
    .then((res) =>
      unwrapApiData<{
        deleted_files: number;
        errors: number;
        task_id: number;
      }>(res),
    );
}
