/**
 * Recycle bin management API / 回收站管理 API
 * Backend: /admin/recycle-bin/*
 */
import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/recycle-bin';

/** Recycle bin module summary / 回收站模块摘要 */
export interface RecycleBinModuleSummary {
  module: string;
  label: string;
  count: number;
  is_tenant: boolean;
}

/** Recycle bin module metadata / 回收站模块元数据 */
export interface RecycleBinModuleMeta {
  label: string;
  is_tenant: boolean;
  columns: string[];
  label_field: string;
  filterable: string[];
  /** 后端按当前语言生成的列/筛选项标题，未包含的字段由前端 getColumnLabel 回退 */
  column_labels?: Record<string, string>;
}

/** Recycle bin item / 回收站记录项 */
export interface RecycleBinItem {
  id: number;
  deleted_at: null | string;
  delete_level: null | string;
  tenant_id?: number;
  tenant_name?: string;
  [key: string]: unknown;
}

/** Get all recyclable module metadata (columns, search fields, is_tenant) / 获取所有可回收模块元数据 */
export function getRecycleBinModulesApi() {
  return requestClient.get<Record<string, RecycleBinModuleMeta>>(
    `${BASE_URL}/modules`,
  );
}

/** Get deleted record count statistics per module / 获取各模块已删除记录数统计 */
export function getRecycleBinSummaryApi() {
  return requestClient.get<RecycleBinModuleSummary[]>(`${BASE_URL}/summary`);
}

/** Query deleted records by module (supports filter/sort/page) / 按模块查询已删除记录 */
export function getRecycleBinListApi(
  module: string,
  params?: Record<string, unknown>,
) {
  return requestClient.get<{ items: RecycleBinItem[]; total: number }>(
    BASE_URL,
    { params: { module, ...params } },
  );
}

/** Restore record / 恢复记录 */
export function restoreRecycleBinItemApi(module: string, id: number) {
  return requestClient.post(`${BASE_URL}/${module}/${id}/restore`);
}

/** Permanently delete / 永久删除 */
export function permanentDeleteRecycleBinItemApi(module: string, id: number) {
  return requestClient.delete(`${BASE_URL}/${module}/${id}`);
}

/** Clear all deleted records for a module / 清空指定模块的所有回收站记录 */
export function clearRecycleBinModuleApi(module: string) {
  return requestClient.delete<{ count: number }>(
    `${BASE_URL}/${module}/clear`,
  );
}

/** Manually trigger expired cleanup / 手动触发过期清理 */
export function triggerRecycleBinCleanupApi(retentionDays: number = 30) {
  return requestClient.delete(`${BASE_URL}/cleanup`, {
    params: { retention_days: retentionDays },
  });
}
