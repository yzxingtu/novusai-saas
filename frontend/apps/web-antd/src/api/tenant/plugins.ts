/**
 * 租户端插件管理 API
 * 对接后端 /tenant/plugins/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 平台插件信息（租户可见） */
export interface AvailablePluginInfo {
  id: number;
  name: string;
  display_name: string;
  version: string;
  description: string | null;
  author: string | null;
  plugin_type: string;
  status: string;
  is_system: boolean;
  icon: string | null;
  config_schema: Record<string, unknown> | null;
  default_config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** 租户插件配置 */
export interface TenantPluginInfo {
  id: number;
  tenant_id: number;
  plugin_id: number;
  is_active: boolean;
  config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** 启用插件请求 */
export interface TenantPluginEnableRequest {
  plugin_id: number;
  config?: Record<string, unknown> | null;
}

/** 更新配置请求 */
export interface TenantPluginConfigRequest {
  config: Record<string, unknown>;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/tenant/plugins';

/** 可用插件分页响应 */
interface AvailablePluginPageResponse {
  items: AvailablePluginInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** 获取可用插件列表（平台已启用的） */
export async function getAvailablePluginsApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AvailablePluginPageResponse> {
  return requestClient.get<AvailablePluginPageResponse>(PREFIX, {
    params,
    ...options,
  });
}

/** 获取租户已启用插件列表 */
export async function getEnabledPluginsApi(
  options?: ApiRequestOptions,
): Promise<TenantPluginInfo[]> {
  return requestClient.get<TenantPluginInfo[]>(`${PREFIX}/enabled`, options);
}

/** 启用插件 */
export async function enableTenantPluginApi(
  data: TenantPluginEnableRequest,
  options?: ApiRequestOptions,
): Promise<TenantPluginInfo> {
  return requestClient.post<TenantPluginInfo>(
    `${PREFIX}/enable`,
    data,
    options,
  );
}

/** 禁用插件 */
export async function disableTenantPluginApi(
  pluginId: number,
  options?: ApiRequestOptions,
): Promise<TenantPluginInfo> {
  return requestClient.post<TenantPluginInfo>(
    `${PREFIX}/${pluginId}/disable`,
    {},
    options,
  );
}

/** 更新插件配置 */
export async function updateTenantPluginConfigApi(
  pluginId: number,
  data: TenantPluginConfigRequest,
  options?: ApiRequestOptions,
): Promise<TenantPluginInfo> {
  return requestClient.put<TenantPluginInfo>(
    `${PREFIX}/${pluginId}/config`,
    data,
    options,
  );
}
