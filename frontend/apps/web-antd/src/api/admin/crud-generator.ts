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
  ddl_preview: string;
  files: PreviewFileItem[];
  total_conflict: number;
  total_new: number;
  warnings: string[];
}

// ============================================================
// API 接口
// ============================================================

/** 预览生成代码（不写入磁盘） */
export function previewCrudGenerateApi(
  config: Record<string, unknown>,
): Promise<{ data: PreviewResponse }> {
  return requestClient.post('/admin/dev/crud/preview', {
    config,
    include_content: true,
  });
}

/** DDL SQL 预览 */
export function previewCrudDdlApi(
  config: Record<string, unknown>,
): Promise<{ data: { sql: string } }> {
  return requestClient.post('/admin/dev/crud/ddl', config);
}
