/**
 * CRUD Generator API
 * 对接后端 /admin/dev/crud/* 接口
 */
import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 预览文件项 */
export interface PreviewFileItem {
  content?: string;
  exists: boolean;
  is_i18n: boolean;
  operation: 'conflict' | 'create' | 'merge';
  path: string;
  size: number;
}

/** 预览响应 */
export interface PreviewResponse {
  conflicts: Array<Record<string, unknown>>;
  ddl_preview?: string;
  files: PreviewFileItem[];
  total_conflict: number;
  total_new: number;
  warnings: string[];
}

// ============================================================
// API 接口
// ============================================================

/** 预览生成代码（不写入磁盘） */
export function previewCrudGenerateApi(config: object) {
  return requestClient.post<PreviewResponse>('/admin/dev/crud/preview', {
    config,
    include_content: true,
  });
}

/** 生成结果 */
export interface GenerateResult {
  confirmed: boolean;
  written: string[];
  skipped: string[];
  errors: string[];
  warnings: string[];
  total_new?: number;
  total_conflict?: number;
}

/** 生成代码并写入磁盘 */
export function generateCrudApi(
  config: object,
  options?: {
    confirmed?: boolean;
    conflictAction?: string;
    forcePaths?: string[];
  },
) {
  return requestClient.post<GenerateResult>('/admin/dev/crud/generate', {
    config,
    confirmed: options?.confirmed ?? false,
    conflict_action: options?.conflictAction ?? 'skip',
    force_paths: options?.forcePaths ?? [],
  });
}

/** DDL SQL 预览 */
export function previewCrudDdlApi(config: object) {
  return requestClient.post<{ sql: string }>('/admin/dev/crud/ddl', config);
}
