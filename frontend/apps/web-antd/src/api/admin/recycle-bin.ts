/**
 * Recycle bin management API / 回收站管理 API
 * Backend: /admin/recycle-bin/*
 */
import type {
  RecycleBinItem,
  RecycleBinModuleMeta,
  RecycleBinModuleSummary,
  TriggerRecycleBinCleanupParams,
} from '#/api/shared/recycle-bin';

import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/recycle-bin';

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
export function triggerRecycleBinCleanupApi(
  params: number | TriggerRecycleBinCleanupParams = {},
) {
  const requestParams =
    typeof params === 'number'
      ? { retention_days: params }
      : {
          ...(params.retentionDays !== undefined
            ? { retention_days: params.retentionDays }
            : {}),
          ...(params.moduleRetentionDays !== undefined
            ? { module_retention_days: params.moduleRetentionDays }
            : {}),
          ...(params.globalRetentionDays !== undefined
            ? { global_retention_days: params.globalRetentionDays }
            : {}),
        };

  return requestClient.delete(`${BASE_URL}/cleanup`, {
    params: requestParams,
  });
}
