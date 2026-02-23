/**
 * 平台端插件市场 API
 */
import type { InstallPreview } from '#/api/admin/plugin';

import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/plugins';

/** 市场插件卡片 */
export interface MarketplacePluginItem {
  name: string;
  slug: string;
  display_name: string;
  description: string;
  icon: string;
  version: string;
  author: string;
  tier: string;
  pricing_type: string;
  price: number | null;
  rating: number | null;
  downloads: number;
  tags: string[];
  is_installed: boolean;
  installed_version: string | null;
}

/** 市场插件详情 */
export interface MarketplacePluginDetail extends MarketplacePluginItem {
  readme: string | null;
  changelog: string | null;
  screenshots: string[];
  homepage: string | null;
  repository_url: string | null;
  compatibility_ok: boolean;
  platform_version_required: string | null;
}

/** 更新信息 */
export interface PluginUpdateInfo {
  name: string;
  current_version: string;
  latest_version: string;
  slug: string;
}

/** 市场列表 */
export function getMarketplaceListApi(params?: Record<string, unknown>) {
  return requestClient.get(`${BASE_URL}/marketplace`, { params });
}

/** 市场详情 */
export function getMarketplaceDetailApi(slug: string) {
  return requestClient.get<MarketplacePluginDetail>(`${BASE_URL}/marketplace/${slug}`);
}

/** 市场安装预览 */
export function marketplacePreviewInstallApi(slug: string) {
  return requestClient.post<InstallPreview>(`${BASE_URL}/marketplace/${slug}/install`);
}

/** 市场确认安装 */
export function marketplaceConfirmInstallApi(slug: string, config?: Record<string, unknown>) {
  return requestClient.post(`${BASE_URL}/marketplace/${slug}/confirm-install`, { config: config || {} });
}

/** 检查更新 */
export function checkPluginUpdatesApi() {
  return requestClient.get<PluginUpdateInfo[]>(`${BASE_URL}/updates`);
}
