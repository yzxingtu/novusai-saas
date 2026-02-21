/**
 * 平台管理端插件管理 API
 * 对接后端 /admin/plugins/* 接口
 */
import type { BackendMenuItemRaw } from '../shared/menu-transformer';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 插件信息 */
export interface PluginInfo {
  id: number;
  name: string;
  display_name: string;
  version: string;
  description: string | null;
  author: string | null;
  plugin_type: string;
  status: string;
  scope: string;
  entry_point: string;
  manifest: Record<string, unknown> | null;
  is_system: boolean;
  required_permissions: string[] | null;
  dependencies: Record<string, string> | null;
  conflicts: string[] | null;
  platform_version: string | null;
  config_schema: Record<string, unknown> | null;
  default_config: Record<string, unknown> | null;
  version_history: Array<Record<string, unknown>> | null;
  icon: string | null;
  homepage: string | null;
  readme: string | null;
  downloads_count: number;
  rating: number | null;
  tags: string[] | null;
  category: string | null;
  screenshots: string[] | null;
  source_url: string | null;
  license: string | null;
  created_at: string;
  updated_at: string;
}

/** 安装插件请求 */
export interface PluginInstallRequest {
  entry_point: string;
  is_system?: boolean;
}

/** 插件列表分页响应 */
interface PluginPageResponse {
  items: PluginInfo[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/admin/plugins';

/** 获取插件列表 */
export async function getPluginListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PluginPageResponse> {
  return requestClient.get<PluginPageResponse>(PREFIX, { params, ...options });
}

/** 获取插件详情 */
export async function getPluginDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<PluginInfo> {
  return requestClient.get<PluginInfo>(`${PREFIX}/${id}`, options);
}

/** 安装插件 */
export async function installPluginApi(
  data: PluginInstallRequest,
  options?: ApiRequestOptions,
): Promise<PluginInfo> {
  return requestClient.post<PluginInfo>(`${PREFIX}/install`, data, options);
}

/** 卸载插件 */
export async function uninstallPluginApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** 启用插件 */
export async function enablePluginApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<PluginInfo> {
  return requestClient.post<PluginInfo>(`${PREFIX}/${id}/enable`, {}, options);
}

/** 禁用插件 */
export async function disablePluginApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<PluginInfo> {
  return requestClient.post<PluginInfo>(`${PREFIX}/${id}/disable`, {}, options);
}

/** 升级插件 */
export async function upgradePluginApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<PluginInfo> {
  return requestClient.post<PluginInfo>(`${PREFIX}/${id}/upgrade`, {}, options);
}

/** 插件健康检查 */
export async function healthCheckPluginApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.get<Record<string, unknown>>(`${PREFIX}/${id}/health`, options);
}

/** 更新插件信息（含默认配置） */
export async function updatePluginApi(
  id: number,
  data: Partial<Pick<PluginInfo, 'category' | 'default_config' | 'description' | 'display_name' | 'license' | 'source_url' | 'tags'>>,
  options?: ApiRequestOptions,
): Promise<PluginInfo> {
  return requestClient.put<PluginInfo>(`${PREFIX}/${id}`, data, options);
}

/** 插件前端配置项 */
export interface PluginFrontendConfig {
  plugin_name: string;
  plugin_version: string;
  scope: string;
  endpoint: 'admin' | 'tenant';
  menus: BackendMenuItemRaw[];
  routes: Record<string, unknown>[];
  locales: Record<string, Record<string, unknown>>;
}

/** 获取已启用插件的前端配置（路由+菜单） */
export async function getPluginFrontendConfigApi(
  options?: ApiRequestOptions,
): Promise<PluginFrontendConfig[]> {
  return requestClient.get<PluginFrontendConfig[]>(
    `${PREFIX}/frontend-config`,
    options,
  );
}

/** 上传冲突响应 */
export interface UploadConflictResponse {
  conflict: boolean;
  plugin_name: string;
  existing_version: string | null;
  new_version: string;
  message: string;
}

/** 上传插件包安装（.zip / .nap） */
export async function uploadPluginApi(
  file: File,
  overwrite?: boolean,
  options?: ApiRequestOptions,
): Promise<PluginInfo | UploadConflictResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const params = overwrite ? '?overwrite=true' : '';
  return requestClient.post<PluginInfo | UploadConflictResponse>(
    `${PREFIX}/upload${params}`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      ...options,
    },
  );
}
