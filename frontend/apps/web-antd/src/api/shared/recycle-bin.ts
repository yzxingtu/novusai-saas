/**
 * Shared recycle-bin API types / 回收站共享类型
 */

export interface RecycleBinModuleSummary {
  module: string;
  label: string;
  count: number;
  is_tenant: boolean;
}

export interface RecycleBinModuleMeta {
  label: string;
  is_tenant: boolean;
  tenant_field?: null | string;
  columns: string[];
  label_field: string;
  filterable: string[];
  sortable?: string[];
  column_labels?: Record<string, string>;
}

export interface RecycleBinItem {
  id: number;
  deleted_at: null | string;
  delete_level: null | string;
  recycle_stage?: null | string;
  promoted_to_global_at?: null | string;
  tenant_id?: null | number;
  tenant_name?: null | string;
  [key: string]: unknown;
}

export interface TriggerRecycleBinCleanupParams {
  moduleRetentionDays?: number;
  globalRetentionDays?: number;
}
