/**
 * 存储配置相关共享类型
 *
 * 管理端和租户端共用，避免跨端导入。
 */

/** 存储驱动信息（含插件启用状态） */
export interface StorageDriverInfo {
  name: string;
  display_name: string;
  config_schema: null | Record<string, unknown>;
  is_builtin: boolean;
  is_available: boolean;
  plugin_name?: string;
  plugin_status?: string;
}

/** 租户存储状态 */
export interface TenantStorageStatus {
  effective_mode: string;
  effective_driver: string;
  tenant_storage_mode: string;
  tenant_storage_driver: null | string;
  tenant_storage_root_path: string;
  tenant_storage_base_url: string;
  tenant_storage_options: Record<string, unknown>;
  /** 该租户是否可自主配置存储（由管理员逐租户开启） */
  can_self_config: boolean;
}
