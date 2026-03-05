/**
 * 平台端插件管理 API
 */
import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/plugins';

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

/** 插件信息 */
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

/** 安装预览 */
export interface InstallPreview {
  plugin_info: Record<string, unknown>;
  install_manifest: Record<string, unknown>;
  dependencies: Record<string, unknown>;
  conflicts: Array<Record<string, string>>;
  capabilities: Array<{ code: string; description: string }>;
  compatibility: Record<string, unknown>;
  warnings: string[];
}

/** 版本历史 */
export interface PluginVersionInfo {
  id: number;
  version: string;
  status: string;
  changelog: null | string;
  installed_at: null | string;
  rolled_back_at: null | string;
}

/** 租户分配 */
export interface PluginTenantAssignmentInfo {
  id: number;
  plugin_id: number;
  tenant_id: number;
  is_active: boolean;
  config: Record<string, unknown>;
  created_at: string;
}

/** AI 功能绑定 */
export interface PluginAIFeatureInfo {
  id: number;
  feature_code: string;
  feature_name: string;
  description: null | string;
  agent_id: null | number;
  is_active: boolean;
}

/** 健康状态 */
export interface PluginHealthInfo {
  status: string;
  error_count: number;
  error_message: null | string;
  enabled_at: null | string;
}

// ── 列表 & 详情 ──

export function getPluginListApi(params?: Record<string, unknown>) {
  return requestClient.get(BASE_URL, { params });
}

export function getPluginDetailApi(id: number, params?: { locale?: string }) {
  return requestClient.get<PluginInfo>(`${BASE_URL}/${id}`, { params });
}

// ── 安装 ──

export function previewPluginInstallApi(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post<InstallPreview>(`${BASE_URL}/preview`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

export function installPluginApi(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post(`${BASE_URL}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

// ── 菜单配置 ──

export interface MenuParentOption {
  value: string;
  label: string;
  code: string;
  icon: null | string;
  path: string;
  children?: MenuParentOption[];
}

export interface MenuParentOptionsResponse {
  admin: MenuParentOption[];
  tenant: MenuParentOption[];
}

export interface MenuOverrideItem {
  name: string;
  parent: string;
  tenant_parent?: string;
}

export function getMenuParentOptionsApi() {
  return requestClient.get<MenuParentOptionsResponse>(
    `${BASE_URL}/menu-parent-options`,
  );
}

export function updatePluginMenuConfigApi(
  id: number,
  menuOverrides: MenuOverrideItem[],
) {
  return requestClient.put(`${BASE_URL}/${id}/menu-config`, {
    menu_overrides: menuOverrides,
  });
}

// ── 启用/禁用/卸载/修复 ──

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

export function disablePluginApi(id: number, force = false) {
  return requestClient.post(`${BASE_URL}/${id}/disable`, null, {
    params: force ? { force: true } : undefined,
    // 当不是强制禁用时，关闭自动 toast，改由 onDisable 处理强制禁用确认弹框
    showCodeMessage: force,
  });
}

export function installPluginDependenciesApi(
  id: number,
  payload: { force?: boolean; npm?: boolean; python?: boolean } = {},
) {
  return requestClient.post(`${BASE_URL}/${id}/dependencies/install`, payload, {
    timeout: 300_000,
  });
}

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

export function repairPluginApi(id: number) {
  return requestClient.post(`${BASE_URL}/${id}/repair`, undefined, {
    timeout: 300_000,
  });
}

export function forceCleanupPluginApi(id: number) {
  return requestClient.delete(`${BASE_URL}/${id}/force-cleanup`);
}

// ── 配置 ──

export function updatePluginConfigApi(
  id: number,
  config: Record<string, unknown>,
) {
  return requestClient.put(`${BASE_URL}/${id}/config`, { config });
}

export function updatePluginCapabilitiesApi(
  id: number,
  capabilities: string[],
) {
  return requestClient.put(`${BASE_URL}/${id}/capabilities`, { capabilities });
}

// ── 图标 ──

export function uploadPluginIconApi(id: number, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post(`${BASE_URL}/${id}/icon`, formData);
}

// ── 版本 ──

export function getPluginVersionsApi(id: number) {
  return requestClient.get<PluginVersionInfo[]>(`${BASE_URL}/${id}/versions`);
}

export function upgradePluginApi(id: number, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post(`${BASE_URL}/${id}/upgrade`, formData);
}

export function rollbackPluginApi(id: number, targetVersion: string) {
  return requestClient.post(`${BASE_URL}/${id}/rollback`, {
    target_version: targetVersion,
  });
}

// ── 租户分配 ──

export function getPluginTenantsApi(id: number) {
  return requestClient.get<PluginTenantAssignmentInfo[]>(
    `${BASE_URL}/${id}/tenants`,
  );
}

export function assignPluginTenantsApi(id: number, tenantIds: number[]) {
  return requestClient.post(`${BASE_URL}/${id}/tenants`, {
    tenant_ids: tenantIds,
  });
}

export function unassignPluginTenantApi(id: number, tenantId: number) {
  return requestClient.delete(`${BASE_URL}/${id}/tenants/${tenantId}`);
}

// ── AI 功能 ──

export function getPluginAIFeaturesApi(id: number) {
  return requestClient.get<PluginAIFeatureInfo[]>(
    `${BASE_URL}/${id}/ai-features`,
  );
}

export function bindPluginAIFeatureApi(
  id: number,
  assignmentId: number,
  agentId: null | number,
) {
  return requestClient.put(
    `${BASE_URL}/${id}/ai-features/${assignmentId}`,
    {},
    {
      params: { agent_id: agentId },
    },
  );
}

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

export function getPluginLicenseApi(id: number) {
  return requestClient.get<PluginLicenseInfo>(`${BASE_URL}/${id}/license`);
}

export function activatePluginLicenseApi(id: number, licenseKey: string) {
  return requestClient.post(`${BASE_URL}/${id}/activate-license`, {
    license_key: licenseKey,
  });
}

export function activatePluginTrialApi(id: number) {
  return requestClient.post<PluginLicenseInfo>(
    `${BASE_URL}/${id}/activate-trial`,
  );
}

export function revokePluginLicenseApi(id: number) {
  return requestClient.delete(`${BASE_URL}/${id}/license`);
}

// ── 健康 ──

export function getPluginHealthApi(id: number) {
  return requestClient.get<PluginHealthInfo>(`${BASE_URL}/${id}/health`);
}

// ── 前端插槽 ──

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
  [key: string]: unknown;
}

export interface PluginSlotsResponse {
  header_widgets: PluginSlotData[];
  dashboard_widgets: PluginSlotData[];
  settings_tabs: PluginSlotData[];
  floating_panels: PluginSlotData[];
  standalone_pages: PluginSlotData[];
  notification_ui: PluginSlotData[];
  plugin_styles?: Record<string, string[]>;
}

export function getPluginSlotsApi() {
  return requestClient.get<PluginSlotsResponse>(`${BASE_URL}/slots`);
}

// ── 备份 ──

export interface PluginBackupInfo {
  name: string;
  version: string;
  path: string;
  has_data: boolean;
  has_files: boolean;
  has_config: boolean;
}

export function listPluginBackupsApi(id: number) {
  return requestClient.get<PluginBackupInfo[]>(`${BASE_URL}/${id}/backups`);
}

export function deletePluginBackupApi(id: number, backupName: string) {
  return requestClient.delete(`${BASE_URL}/${id}/backups/${backupName}`);
}
