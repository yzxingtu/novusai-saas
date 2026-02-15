/**
 * CRUD 代码生成记录 API
 * 对接后端 /admin/dev/crud/records 接口
 */
import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 文件清单项 */
export interface FileManifestItem {
  path: string;
  size: number;
  operation: 'error' | 'merged' | 'preview' | 'skipped' | 'written';
}

/** 生成记录列表项 */
export interface CrudRecordInfo {
  id: number;
  operator_id: number | null;
  operator_name: string | null;
  operation_type: string;
  module_name: string | null;
  table_name: string | null;
  file_count: number;
  status: string;
  duration_ms: number | null;
  parent_record_id: number | null;
  created_at: string | null;
  updated_at: string | null;
}

/** 生成记录详情 */
export interface CrudRecordDetail extends CrudRecordInfo {
  config_snapshot: Record<string, unknown> | null;
  file_manifest: FileManifestItem[] | null;
  error_detail: string | null;
  metadata: Record<string, unknown> | null;
}

/** 统计信息 */
export interface CrudRecordStatistics {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  avg_duration_ms: number;
}

// ============================================================
// API 函数
// ============================================================

/** 分页查询生成记录 */
export function getCrudRecordListApi(params?: Record<string, unknown>) {
  return requestClient.get('/admin/dev/crud/records', { params });
}

/** 获取记录详情 */
export function getCrudRecordDetailApi(id: number) {
  return requestClient.get<CrudRecordDetail>(
    `/admin/dev/crud/records/${id}`,
  );
}

/** 获取记录配置快照 */
export function getCrudRecordConfigApi(id: number) {
  return requestClient.get<Record<string, unknown>>(
    `/admin/dev/crud/records/${id}/config`,
  );
}

/** 获取统计信息 */
export function getCrudRecordStatisticsApi() {
  return requestClient.get<CrudRecordStatistics>(
    '/admin/dev/crud/records/statistics',
  );
}

/** 删除记录 */
export function deleteCrudRecordApi(id: number) {
  return requestClient.delete(`/admin/dev/crud/records/${id}`);
}

/** 删除文件预览结果 */
export interface DeleteFilesPreview {
  mode: string;
  dry_run: boolean;
  files: Array<{ path: string; exists: boolean; operation?: string }>;
  total: number;
  existing?: number;
  record_id?: number;
  module_name?: string;
  table_name?: string;
}

/** 删除文件结果 */
export interface DeleteFilesResult {
  mode: string;
  dry_run: boolean;
  total_deleted?: number;
  total_files?: number;
  restored?: string[];
  deleted?: string[];
  skipped?: string[];
  conflicts?: Array<{ path: string; reason: string }>;
  errors?: Array<{ path: string; error: string }>;
}

/** 批量删除生成文件（dry_run 预览或实际删除） */
export function deleteGeneratedFilesApi(body: {
  mode: 'entity' | 'record';
  record_id?: number;
  module_name?: string;
  table_name?: string;
  config?: Record<string, unknown>;
  dry_run?: boolean;
}) {
  return requestClient.post<DeleteFilesPreview | DeleteFilesResult>(
    '/admin/dev/crud/records/delete-files',
    body,
  );
}

/** 回滚生成记录（从备份恢复） */
export function rollbackGenerationApi(body: {
  record_id: number;
  file_paths?: string[];
  force?: boolean;
}) {
  return requestClient.post<DeleteFilesResult>(
    '/admin/dev/crud/records/rollback',
    body,
  );
}
