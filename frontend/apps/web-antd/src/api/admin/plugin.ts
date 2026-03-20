/**
 * Platform plugin management API / 平台端插件管理 API
 */
import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/plugins';

/** Plugin dependency status / 插件依赖状态 */
export interface PluginDependencyStatus {
  overall: 'installed' | 'missing';
  production_mode: boolean;
  python: {
    declared: number;
    installed: number;
    missing: string[];
    state: 'installed' | 'missing';
  };
  npm: {
    declared: number;
    installed: number;
    missing: string[];
    state: 'installed' | 'missing' | 'not_required';
  };
}

/** Plugin info / 插件信息 */
export interface PluginInfo {
  id: number;
  name: string;
  display_name: string;
  version: string;
  description: null | string;
  author: null | string;
  icon: null | string;
  icon_color: null | string;
  homepage: null | string;
  repository_url: null | string;
  license_text: null | string;
  tags: string[];
  scope: string;
  status: string;
  tier: string;
  install_source: string;
  marketplace_slug: null | string;
  manifest: Record<string, unknown>;
  config: Record<string, unknown>;
  ai_requirements: null | Record<string, unknown>;
  pricing_type: string;
  pricing_info: null | Record<string, unknown>;
  error_message: null | string;
  error_count: number;
  installed_packages: string[];
  granted_capabilities: string[];
  installed_at: null | string;
  enabled_at: null | string;
  created_at: string;
  updated_at: string;
  readme?: null | string;
  dependency_status?: PluginDependencyStatus;
}

/** Install preview / 安装预览 */
export interface InstallPreview {
  plugin_info: Record<string, unknown>;
  install_manifest: Record<string, unknown>;
  dependencies: Record<string, unknown>;
  conflicts: Array<Record<string, string>>;
  capabilities: Array<{ code: string; description: string }>;
  compatibility: Record<string, unknown>;
  warnings: string[];
}

/** Version history / 版本历史 */
export interface PluginVersionInfo {
  id: number;
  version: string;
  status: string;
  changelog: null | string;
  installed_at: null | string;
  rolled_back_at: null | string;
}

/** Tenant assignment / 企业分配 */
export interface PluginTenantAssignmentInfo {
  id: number;
  plugin_id: number;
  tenant_id: number;
  is_active: boolean;
  config: Record<string, unknown>;
  created_at: string;
}

/** AI feature binding / AI 功能绑定 */
export interface PluginAIFeatureInfo {
  id: number;
  feature_code: string;
  feature_name: string;
  description: null | string;
  agent_id: null | number;
  is_active: boolean;
}

/** Health status / 健康状态 */
export interface PluginHealthInfo {
  status: string;
  error_count: number;
  error_message: null | string;
  enabled_at: null | string;
}

// ── List & Detail / 列表 & 详情 ──

/** Get plugin list / 获取插件列表 */
export function getPluginListApi(params?: Record<string, unknown>) {
  return requestClient.get(BASE_URL, { params });
}

/** Get plugin detail / 获取插件详情 */
export function getPluginDetailApi(id: number, params?: { locale?: string }) {
  return requestClient.get<PluginInfo>(`${BASE_URL}/${id}`, { params });
}

// ── Install / 安装 ──

/** Preview plugin install / 预览插件安装 */
export function previewPluginInstallApi(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post<InstallPreview>(`${BASE_URL}/preview`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

/** Install plugin / 安装插件 */
export function installPluginApi(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post(`${BASE_URL}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

// ── Menu config / 菜单配置 ──

/** Menu parent option / 菜单父级选项 */
export interface MenuParentOption {
  value: string;
  label: string;
  code: string;
  icon: null | string;
  path: string;
  children?: MenuParentOption[];
}

/** Menu parent options response / 菜单父级选项响应 */
export interface MenuParentOptionsResponse {
  admin: MenuParentOption[];
  tenant: MenuParentOption[];
}

/** Menu override item / 菜单覆盖项 */
export interface MenuOverrideItem {
  name: string;
  parent: string;
  tenant_parent?: string;
}

/** Get menu parent options / 获取菜单父级选项 */
export function getMenuParentOptionsApi() {
  return requestClient.get<MenuParentOptionsResponse>(
    `${BASE_URL}/menu-parent-options`,
  );
}

/** Update plugin menu config / 更新插件菜单配置 */
export function updatePluginMenuConfigApi(
  id: number,
  menuOverrides: MenuOverrideItem[],
) {
  return requestClient.put(`${BASE_URL}/${id}/menu-config`, {
    menu_overrides: menuOverrides,
  });
}

// ── Enable/Disable/Uninstall/Repair / 启用/禁用/卸载/修复 ──

/** Enable plugin / 启用插件 */
export function enablePluginApi(
  id: number,
  menuOverrides?: MenuOverrideItem[],
) {
  return requestClient.post(
    `${BASE_URL}/${id}/enable`,
    menuOverrides?.length ? { menu_overrides: menuOverrides } : undefined,
    { timeout: 300_000 },
  );
}

/** Disable plugin / 禁用插件 */
export function disablePluginApi(id: number, force = false) {
  return requestClient.post(`${BASE_URL}/${id}/disable`, null, {
    params: force ? { force: true } : undefined,
    // When not force-disabling, disable auto toast, let onDisable handle force-disable confirm dialog / 当不是强制禁用时，关闭自动 toast
    showCodeMessage: force,
  });
}

/** Install plugin dependencies / 安装插件依赖 */
export function installPluginDependenciesApi(
  id: number,
  payload: { force?: boolean; npm?: boolean; python?: boolean } = {},
) {
  return requestClient.post(`${BASE_URL}/${id}/dependencies/install`, payload, {
    timeout: 300_000,
  });
}

/** Uninstall plugin dependencies / 卸载插件依赖 */
export function uninstallPluginDependenciesApi(
  id: number,
  payload: { force?: boolean; npm?: boolean; python?: boolean } = {},
) {
  return requestClient.post(
    `${BASE_URL}/${id}/dependencies/uninstall`,
    payload,
    {
      timeout: 300_000,
    },
  );
}

/** Uninstall plugin / 卸载插件 */
export function uninstallPluginApi(
  id: number,
  confirmDataDelete = false,
  cleanupDependencies = false,
) {
  return requestClient.delete(`${BASE_URL}/${id}`, {
    params: {
      cleanup_dependencies: cleanupDependencies,
      confirm_data_delete: confirmDataDelete,
    },
    timeout: 300_000,
  });
}

/** Repair plugin / 修复插件 */
export function repairPluginApi(id: number) {
  return requestClient.post(`${BASE_URL}/${id}/repair`, undefined, {
    timeout: 300_000,
  });
}

/** Force cleanup plugin / 强制清理插件 */
export function forceCleanupPluginApi(id: number) {
  return requestClient.delete(`${BASE_URL}/${id}/force-cleanup`);
}

// ── Config / 配置 ──

/** Update plugin config / 更新插件配置 */
export function updatePluginConfigApi(
  id: number,
  config: Record<string, unknown>,
) {
  return requestClient.put(`${BASE_URL}/${id}/config`, { config });
}

/** Update plugin capabilities / 更新插件能力 */
export function updatePluginCapabilitiesApi(
  id: number,
  capabilities: string[],
) {
  return requestClient.put(`${BASE_URL}/${id}/capabilities`, { capabilities });
}

// ── Icon / 图标 ──

/** Upload plugin icon / 上传插件图标 */
export function uploadPluginIconApi(id: number, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post(`${BASE_URL}/${id}/icon`, formData);
}

// ── Version / 版本 ──

/** Get plugin versions / 获取插件版本列表 */
export function getPluginVersionsApi(id: number) {
  return requestClient.get<PluginVersionInfo[]>(`${BASE_URL}/${id}/versions`);
}

/** Upgrade plugin / 升级插件 */
export function upgradePluginApi(id: number, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post(`${BASE_URL}/${id}/upgrade`, formData);
}

/** Rollback plugin / 回滚插件 */
export function rollbackPluginApi(id: number, targetVersion: string) {
  return requestClient.post(`${BASE_URL}/${id}/rollback`, {
    target_version: targetVersion,
  });
}

// ── Tenant assignment / 企业分配 ──

/** Get plugin tenants / 获取插件企业分配 */
export function getPluginTenantsApi(id: number) {
  return requestClient.get<PluginTenantAssignmentInfo[]>(
    `${BASE_URL}/${id}/tenants`,
  );
}

/** Assign plugin to tenants / 分配插件到企业 */
export function assignPluginTenantsApi(id: number, tenantIds: number[]) {
  return requestClient.post(`${BASE_URL}/${id}/tenants`, {
    tenant_ids: tenantIds,
  });
}

/** Unassign plugin from tenant / 取消分配插件 */
export function unassignPluginTenantApi(id: number, tenantId: number) {
  return requestClient.delete(`${BASE_URL}/${id}/tenants/${tenantId}`);
}

// ── AI features / AI 功能 ──

/** Get plugin AI features / 获取插件 AI 功能 */
export function getPluginAIFeaturesApi(id: number) {
  return requestClient.get<PluginAIFeatureInfo[]>(
    `${BASE_URL}/${id}/ai-features`,
  );
}

// 插件 AI 绑定统一到「AI 功能分配」页；后端已移除 PUT /ai-features/:id

// ── License ──

export interface PluginLicenseInfo {
  status: 'active' | 'expired' | 'invalid' | 'none' | 'trial';
  license_type: null | string;
  is_valid: boolean;
  message?: string;
  license_key?: string;
  buyer_email?: string;
  activated_at?: null | string;
  expires_at?: null | string;
  remaining_days?: null | number;
  trial_days_remaining?: number;
}

/** Get plugin license / 获取插件许可证 */
export function getPluginLicenseApi(id: number) {
  return requestClient.get<PluginLicenseInfo>(`${BASE_URL}/${id}/license`);
}

/** Activate plugin license / 激活插件许可证 */
export function activatePluginLicenseApi(id: number, licenseKey: string) {
  return requestClient.post(`${BASE_URL}/${id}/activate-license`, {
    license_key: licenseKey,
  });
}

/** Activate plugin trial / 激活插件试用 */
export function activatePluginTrialApi(id: number) {
  return requestClient.post<PluginLicenseInfo>(
    `${BASE_URL}/${id}/activate-trial`,
  );
}

/** Revoke plugin license / 撤销插件许可证 */
export function revokePluginLicenseApi(id: number) {
  return requestClient.delete(`${BASE_URL}/${id}/license`);
}

// ── Health / 健康 ──

/** Get plugin health / 获取插件健康状态 */
export function getPluginHealthApi(id: number) {
  return requestClient.get<PluginHealthInfo>(`${BASE_URL}/${id}/health`);
}

// ── Frontend slots / 前端插槽 ──

/** Plugin slot data / 插件插槽数据 */
export interface PluginSlotData {
  slot_type: string;
  plugin_name: string;
  name: string;
  component?: string;
  title?: Record<string, string> | string;
  sort_order?: number;
  scope?: string;
  path?: string;
  grid?: Record<string, number>;
  icon?: string;
  position?: string;
  event?: string;
  ai?: { mode?: string; page_context_key?: string };
  [key: string]: unknown;
}

/** Plugin slots response / 插件插槽响应 */
export interface PluginSlotsResponse {
  header_widgets: PluginSlotData[];
  dashboard_widgets: PluginSlotData[];
  settings_tabs: PluginSlotData[];
  floating_panels: PluginSlotData[];
  standalone_pages: PluginSlotData[];
  notification_ui: PluginSlotData[];
  plugin_styles?: Record<string, string[]>;
}

/** Get plugin slots / 获取插件插槽 */
export function getPluginSlotsApi() {
  return requestClient.get<PluginSlotsResponse>(`${BASE_URL}/slots`);
}

// ── Backup / 备份 ──

/** Plugin backup info / 插件备份信息 */
export interface PluginBackupInfo {
  name: string;
  version: string;
  path: string;
  has_data: boolean;
  has_files: boolean;
  has_config: boolean;
}

/** List plugin backups / 获取插件备份列表 */
export function listPluginBackupsApi(id: number) {
  return requestClient.get<PluginBackupInfo[]>(`${BASE_URL}/${id}/backups`);
}

/** Delete plugin backup / 删除插件备份 */
export function deletePluginBackupApi(id: number, backupName: string) {
  return requestClient.delete(`${BASE_URL}/${id}/backups/${backupName}`);
}
