/**
 * Storage Migration Plugin - Type definitions
 */

export interface NovusPluginSharedAPI {
  registerLocale?: (
    locale: string,
    prefix: string,
    messages: Record<string, unknown>,
  ) => void;
  getAccessCodes?: () => string[];
  hasAccessByCodes?: (
    codes: string | string[] | undefined,
    options?: { mode?: 'all' | 'any' },
  ) => boolean;
}

export interface StorageDriverInfo {
  name: string;
  display_name: string;
  config_schema: Record<string, unknown> | null;
  is_builtin: boolean;
  is_available: boolean;
  plugin_name?: string;
  plugin_status?: string;
}

export interface MigrationTask {
  id: number;
  source_driver: string;
  target_driver: string;
  status: string;
  scope: string;
  total_files: number;
  migrated_files: number;
  failed_files: number;
  skipped_files: number;
  total_bytes: number;
  migrated_bytes: number;
  concurrency: number;
  source_config_snapshot: Record<string, unknown> | null;
  target_config_snapshot: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  source_cleanup_started_at: string | null;
  source_cleanup_completed_at: string | null;
  source_cleanup_deleted_files: number;
  source_cleanup_error_count: number;
  created_by: number;
  created_at: string;
  updated_at: string;
  logs?: {
    items: MigrationLog[];
    total: number;
    page: number;
    page_size: number;
  };
}

export interface MigrationLog {
  id: number;
  task_id: number;
  attachment_id: number;
  file_path: string;
  file_size: number;
  status: string;
  error_message: string | null;
  old_driver: string;
  old_base_url: string;
  new_driver: string | null;
  new_base_url: string | null;
  migrated_at: string | null;
  created_at: string;
}

export interface CreateTaskParams {
  source_driver: string;
  target_driver: string;
  scope?: string;
  concurrency?: number;
}

export interface ImpactAnalysis {
  source_driver: string;
  target_driver: string;
  source_available: boolean;
  target_available: boolean;
  total_files: number;
  total_size_bytes: number;
  private_files: number;
  private_size_bytes: number;
  public_files: number;
  public_size_bytes: number;
  tenant_breakdown: Array<{
    tenant_id: number | null;
    file_count: number;
    size_bytes: number;
  }>;
  scope: string;
}
