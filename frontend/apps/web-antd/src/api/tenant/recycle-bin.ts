/**
 * Tenant recycle bin management API / 企业端回收站管理 API
 * Backend: /tenant/recycle-bin/*
 */
import { requestClient } from '#/utils/request';

const BASE_URL = '/tenant/recycle-bin';

export interface TenantRecycleBinModuleSummary {
  module: string;
  label: string;
  count: number;
}

export interface TenantRecycleBinModuleMeta {
  label: string;
  columns: string[];
  label_field: string;
}

export interface TenantRecycleBinItem {
  id: number;
  deleted_at: null | string;
  delete_level: null | string;
  [key: string]: unknown;
}

export function getTenantRecycleBinModulesApi() {
  return requestClient.get<Record<string, TenantRecycleBinModuleMeta>>(
    `${BASE_URL}/modules`,
  );
}

export function getTenantRecycleBinSummaryApi() {
  return requestClient.get<TenantRecycleBinModuleSummary[]>(
    `${BASE_URL}/summary`,
  );
}

export function getTenantRecycleBinListApi(
  module: string,
  params: Record<string, unknown>,
) {
  return requestClient.get<{
    items: TenantRecycleBinItem[];
    total: number;
  }>(BASE_URL, { params: { ...params, module } });
}

export function restoreTenantRecycleBinItemApi(
  module: string,
  itemId: number,
) {
  return requestClient.post(`${BASE_URL}/${module}/${itemId}/restore`);
}

export function escalateTenantRecycleBinItemApi(
  module: string,
  itemId: number,
) {
  return requestClient.delete(`${BASE_URL}/${module}/${itemId}`);
}
