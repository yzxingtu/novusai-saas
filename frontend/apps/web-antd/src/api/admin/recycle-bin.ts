import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/recycle-bin';

export interface RecycleBinModuleSummary {
  module: string;
  label: string;
  count: number;
  is_tenant: boolean;
}

export interface RecycleBinModuleMeta {
  label: string;
  is_tenant: boolean;
  columns: string[];
  label_field: string;
  filterable: string[];
}

export interface RecycleBinItem {
  id: number;
  deleted_at: string | null;
  delete_level: string | null;
  tenant_id?: number;
  tenant_name?: string;
  [key: string]: unknown;
}

/** 获取所有可回收模块元数据（列、搜索字段、is_tenant） */
export function getRecycleBinModulesApi() {
  return requestClient.get<Record<string, RecycleBinModuleMeta>>(
    `${BASE_URL}/modules`,
  );
}

/** 获取各模块已删除记录数统计 */
export function getRecycleBinSummaryApi() {
  return requestClient.get<RecycleBinModuleSummary[]>(`${BASE_URL}/summary`);
}

/** 按模块查询已删除记录（支持 filter/sort/page） */
export function getRecycleBinListApi(
  module: string,
  params?: Record<string, unknown>,
) {
  return requestClient.get<{ items: RecycleBinItem[]; total: number }>(
    BASE_URL,
    { params: { module, ...params } },
  );
}

/** 恢复记录 */
export function restoreRecycleBinItemApi(module: string, id: number) {
  return requestClient.post(`${BASE_URL}/${module}/${id}/restore`);
}

/** 永久删除 */
export function permanentDeleteRecycleBinItemApi(module: string, id: number) {
  return requestClient.delete(`${BASE_URL}/${module}/${id}`);
}

/** 手动触发过期清理 */
export function triggerRecycleBinCleanupApi(retentionDays: number = 30) {
  return requestClient.delete(`${BASE_URL}/cleanup`, {
    params: { retention_days: retentionDays },
  });
}
