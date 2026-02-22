/**
 * 平台管理端插件市场 API
 * 对接后端 /admin/marketplace/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 插件安装状态 */
export type InstallStatus = 'installed' | 'not_installed' | 'update_available';

/** 插件仓库地址（双节点） */
export interface PluginRepo {
  github: string | null;
  gitee: string | null;
}

/** 插件分类定义 */
export interface RegistryCategory {
  code: string;
  name: string;
  icon: string;
  sort_order: number;
}

/** 市场插件信息 */
export interface MarketplacePlugin {
  name: string;
  slug: string;
  display_name: string;
  version: string;
  description: string | null;
  author: string | null;
  plugin_type: string;
  category: string | null;
  tags: string[] | null;
  repo: PluginRepo;
  official: boolean;
  icon: string | null;
  screenshots: string[] | null;
  readme: string | null;
  min_platform_version: string | null;
  license: string | null;
  changelog_url: string | null;
  checksum_sha256: string | null;
  file_size_bytes: number | null;
  install_status: InstallStatus;
  installed_version: string | null;
  local_plugin_id: number | null;
}

/** 市场插件列表响应 */
export interface MarketplaceListResponse {
  items: MarketplacePlugin[];
  total: number;
  categories: RegistryCategory[];
  mirror: string;
}

/** 市场插件详情响应 */
export interface MarketplaceDetailResponse extends MarketplacePlugin {
  readme: string | null;
  repo_url: string | null;
}

/** 安装请求 */
export interface MarketplaceInstallRequest {
  version?: string;
}

/** 插件更新信息 */
export interface PluginUpdateInfo {
  name: string;
  slug: string;
  display_name: string;
  current_version: string;
  latest_version: string;
  changelog_url: string | null;
  local_plugin_id: number;
}

/** 更新检查响应 */
export interface UpdateCheckResponse {
  updates: PluginUpdateInfo[];
  total: number;
}

/** 刷新缓存响应 */
export interface RegistryRefreshResponse {
  refreshed: boolean;
  plugin_count: number;
  mirror: string;
  updated_at: string | null;
}

// ============================================================
// 查询参数
// ============================================================

export interface MarketplaceListParams {
  'filter[keyword]'?: string;
  'filter[category]'?: string;
  'filter[official]'?: boolean;
  'filter[install_status]'?: InstallStatus;
  'filter[plugin_type]'?: string;
  sort?: string;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/admin/marketplace';

/** 获取市场插件列表 */
export async function getMarketplaceListApi(
  params?: MarketplaceListParams,
  options?: ApiRequestOptions,
): Promise<MarketplaceListResponse> {
  return requestClient.get<MarketplaceListResponse>(PREFIX, {
    params,
    ...options,
  });
}

/** 获取市场插件详情 */
export async function getMarketplaceDetailApi(
  slug: string,
  options?: ApiRequestOptions,
): Promise<MarketplaceDetailResponse> {
  return requestClient.get<MarketplaceDetailResponse>(
    `${PREFIX}/${slug}`,
    options,
  );
}

/** 从市场一键安装插件 */
export async function installFromMarketplaceApi(
  slug: string,
  data?: MarketplaceInstallRequest,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.post(`${PREFIX}/${slug}/install`, data ?? {}, options);
}

/** 从市场一键更新插件 */
export async function updateFromMarketplaceApi(
  slug: string,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.post(`${PREFIX}/${slug}/update`, {}, options);
}

/** 检查已安装插件的可用更新 */
export async function checkMarketplaceUpdatesApi(
  options?: ApiRequestOptions,
): Promise<UpdateCheckResponse> {
  return requestClient.get<UpdateCheckResponse>(
    `${PREFIX}/check-updates`,
    options,
  );
}

/** 强制刷新市场注册中心缓存 */
export async function refreshMarketplaceCacheApi(
  options?: ApiRequestOptions,
): Promise<RegistryRefreshResponse> {
  return requestClient.post<RegistryRefreshResponse>(
    `${PREFIX}/refresh`,
    {},
    options,
  );
}
