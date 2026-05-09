/**
 * Platform plugin management API / 平台端插件管理 API
 */
import type { PluginSlotData, PluginSlotsResponse } from '#/api/shared/plugin';

import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/plugins';

/** Plugin dependency status / 插件依赖状态 */
export interface PluginDependencyStatus {
  overall: 'installed' | 'missing';
  python: {
    declared: number;
    details: Array<{
      installed: boolean;
      installed_version: null | string;
      message: string;
      package: string;
      requirement: string;
      satisfied: boolean;
      state: 'missing' | 'ready';
    }>;
    installed: number;
    missing: string[];
    state: 'installed' | 'missing';
  };
  plugins: {
    declared: number;
    details: Array<{
      enabled: boolean;
      installed: boolean;
      installed_version: null | string;
      message: string;
      plugin: string;
      source: string;
      state: 'disabled' | 'missing' | 'ready' | 'unknown' | 'version_mismatch';
      version: string;
    }>;
    installed: number;
    missing: string[];
    state: 'installed' | 'missing';
  };
}

export type PluginRecoveryAction =
  | 'force_cleanup'
  | 'install_dependencies'
  | 'refresh_schedules'
  | 'repair';

export type PluginRecoveryReason =
  | 'missing_dependencies'
  | 'missing_from_disk'
  | 'none'
  | 'runtime_error'
  | 'schedule_refresh_failed';

export type PluginRecoverySeverity = 'error' | 'healthy' | 'warning';

export interface PluginRecoveryState {
  has_scheduled_tasks: boolean;
  needs_attention: boolean;
  primary_action: null | PluginRecoveryAction;
  reason: PluginRecoveryReason;
  secondary_actions: PluginRecoveryAction[];
  severity: PluginRecoverySeverity;
}

export type PluginCompatibilityEdition = 'saas' | 'single_management';

export type PluginCompatibilitySurface =
  | 'admin'
  | 'global'
  | 'platform'
  | 'tenant'
  | 'user';

export type PluginTenantExposureMode =
  | 'all_tenants'
  | 'none'
  | 'scope_default'
  | 'selected_tenants';

export interface PluginCompatibilityProfile {
  current_edition?: string;
  declared_editions?: string[];
  editions?: string[];
  is_saas_compatible?: boolean;
  is_single_management_compatible?: boolean;
  notes?: string[];
  surfaces?: string[];
  tenant_assignment_required?: boolean;
  tenant_exposure?: string;
  tenant_runtime_denial_reason?: null | string;
  tenant_runtime_scope?: null | string;
}

export interface ResolvedPluginCompatibilityProfile {
  editions: PluginCompatibilityEdition[];
  saasCompatible: boolean;
  singleManagementCompatible: boolean;
  surfaces: PluginCompatibilitySurface[];
  tenantAssignmentRequired: boolean;
  tenantExposureMode: PluginTenantExposureMode;
}

export interface PluginCompatibilitySource {
  compatibility_profile?: null | PluginCompatibilityProfile;
  manifest?: null | Record<string, unknown>;
  plugin_info?: null | Record<string, unknown>;
  scope?: null | string;
}

const DEFAULT_COMPATIBILITY_PROFILE: ResolvedPluginCompatibilityProfile = {
  editions: ['saas'],
  saasCompatible: true,
  singleManagementCompatible: false,
  surfaces: [],
  tenantAssignmentRequired: false,
  tenantExposureMode: 'scope_default',
};

const TENANT_EXPOSURE_LABEL_KEYS: Record<PluginTenantExposureMode, string> = {
  all_tenants: 'admin.plugin.compatibility.tenantExposure.allTenants',
  none: 'admin.plugin.compatibility.tenantExposure.none',
  scope_default: 'admin.plugin.compatibility.tenantExposure.scopeDefault',
  selected_tenants: 'admin.plugin.compatibility.tenantExposure.selectedTenants',
};

const TENANT_EXPOSURE_COLORS: Record<PluginTenantExposureMode, string> = {
  all_tenants: 'success',
  none: 'default',
  scope_default: 'default',
  selected_tenants: 'cyan',
};

const CANONICAL_COMPATIBILITY_EDITIONS: readonly PluginCompatibilityEdition[] =
  ['saas', 'single_management'];

const CANONICAL_COMPATIBILITY_SURFACES: readonly PluginCompatibilitySurface[] =
  ['admin', 'global', 'platform', 'tenant', 'user'];

const CANONICAL_TENANT_EXPOSURE_MODES = new Set<PluginTenantExposureMode>([
  'all_tenants',
  'none',
  'scope_default',
  'selected_tenants',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getBoolean(
  source: null | Record<string, unknown> | undefined,
  keys: string[],
): boolean | undefined {
  for (const key of keys) {
    const value = source?.[key];
    if (typeof value === 'boolean') {
      return value;
    }
  }
  return undefined;
}

function getCanonicalStringList<T extends string>(
  source: null | Record<string, unknown> | undefined,
  key: string,
  allowed: readonly T[],
): T[] {
  const values = source?.[key];
  if (!Array.isArray(values)) {
    return [];
  }
  return [
    ...new Set(
      values.filter((value): value is T => allowed.includes(value as T)),
    ),
  ];
}

function normalizeTenantExposureMode(value: unknown): PluginTenantExposureMode {
  return typeof value === 'string' &&
    CANONICAL_TENANT_EXPOSURE_MODES.has(value as PluginTenantExposureMode)
    ? (value as PluginTenantExposureMode)
    : DEFAULT_COMPATIBILITY_PROFILE.tenantExposureMode;
}

function getCompatibilityProfileRecord(
  source: null | PluginCompatibilitySource | undefined,
): null | Record<string, unknown> {
  if (!source || !isRecord(source)) {
    return null;
  }
  const profile = source.compatibility_profile;
  return isRecord(profile) ? profile : null;
}

export function resolvePluginCompatibilityProfile(
  source: null | PluginCompatibilitySource | undefined,
): ResolvedPluginCompatibilityProfile {
  const profile = getCompatibilityProfileRecord(source);
  const editions = getCanonicalStringList(
    profile,
    'editions',
    CANONICAL_COMPATIBILITY_EDITIONS,
  );
  const resolvedEditions =
    editions.length > 0 ? editions : DEFAULT_COMPATIBILITY_PROFILE.editions;
  const surfaces = getCanonicalStringList(
    profile,
    'surfaces',
    CANONICAL_COMPATIBILITY_SURFACES,
  );
  const tenantExposureMode = normalizeTenantExposureMode(
    profile?.tenant_exposure,
  );
  const explicitAssignmentRequired = getBoolean(profile, [
    'tenant_assignment_required',
  ]);
  const assignmentModeRequiresTenants =
    tenantExposureMode === 'selected_tenants';
  const tenantAssignmentRequired =
    explicitAssignmentRequired === true || assignmentModeRequiresTenants;

  return {
    editions: [...resolvedEditions],
    saasCompatible: resolvedEditions.includes('saas'),
    singleManagementCompatible: resolvedEditions.includes('single_management'),
    surfaces,
    tenantAssignmentRequired,
    tenantExposureMode,
  };
}

export function pluginRequiresTenantAssignment(
  source: null | PluginCompatibilitySource | undefined,
): boolean {
  return resolvePluginCompatibilityProfile(source).tenantAssignmentRequired;
}

export function getPluginTenantExposureLabelKey(
  mode: PluginTenantExposureMode,
): string {
  return TENANT_EXPOSURE_LABEL_KEYS[mode];
}

export function getPluginTenantExposureColor(
  mode: PluginTenantExposureMode,
): string {
  return TENANT_EXPOSURE_COLORS[mode];
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
  compatibility_profile?: null | PluginCompatibilityProfile;
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
  recovery_state?: PluginRecoveryState;
}

export type InstallManifestCountKey =
  | 'adapters'
  | 'api_routes'
  | 'dashboard_widgets'
  | 'events'
  | 'floating_panels'
  | 'frontend_pages'
  | 'header_widgets'
  | 'hooks'
  | 'notification_ui'
  | 'notifications'
  | 'page_menus'
  | 'permissions'
  | 'settings_tabs'
  | 'skills'
  | 'storage_drivers'
  | 'tasks'
  | 'webhooks';

export type InstallManifestDetailKey = `${InstallManifestCountKey}_details`;

export type InstallManifestSummary = Partial<
  Record<InstallManifestCountKey, number>
> &
  Partial<Record<InstallManifestDetailKey, string[]>>;

export interface PreviewPythonDependencyState {
  installed: boolean;
  installed_version: null | string;
  message: string;
  package: string;
  requirement: string;
  satisfied: boolean;
  state: 'missing' | 'ready';
}

export interface PreviewPluginDependencyState {
  enabled: boolean;
  installed: boolean;
  installed_version: null | string;
  message: string;
  plugin: string;
  source: string;
  state: 'disabled' | 'missing' | 'ready' | 'unknown' | 'version_mismatch';
  version: string;
}

/** Install preview / 安装预览 */
export interface InstallPreview {
  plugin_info: Record<string, unknown>;
  install_manifest: InstallManifestSummary;
  dependencies: {
    plugins: PreviewPluginDependencyState[];
    python: PreviewPythonDependencyState[];
  };
  conflicts: Array<Record<string, string>>;
  capabilities: Array<{ code: string; description: string }>;
  compatibility_profile?: null | PluginCompatibilityProfile;
  warnings: string[];
  preview_token: string;
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

export interface PluginLifecycleAuditStageResult {
  stage: string;
  status: 'available' | 'degraded' | 'not_implemented' | 'unavailable';
  reason?: null | string;
  metadata: Record<string, unknown>;
}

export interface PluginLifecycleRecentFailure {
  source: string;
  code: string;
  message: string;
  occurred_at?: null | string;
  metadata: Record<string, unknown>;
}

export interface PluginLifecycleExposedCapability {
  name: string;
  kind: string;
  status: 'available' | 'degraded' | 'not_implemented' | 'unavailable';
  reason?: null | string;
  metadata: Record<string, unknown>;
  source?: null | string;
}

export interface PluginLifecycleAuditReport {
  runtime_kind: 'plugin';
  target: Record<string, unknown>;
  stage_results: PluginLifecycleAuditStageResult[];
  degraded_reason?: null | string;
  recovery_actions: string[];
  exposed_capabilities: PluginLifecycleExposedCapability[];
  recent_failures: PluginLifecycleRecentFailure[];
}

export interface PluginScheduleRefreshResult {
  mode: string;
  plugin_id: number;
  plugin_name: string;
  task_count: number;
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
export function installPluginApi(file: File, previewToken: string) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('preview_token', previewToken);
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
  payload: { python?: boolean } = {},
) {
  return requestClient.post(`${BASE_URL}/${id}/dependencies/install`, payload, {
    timeout: 300_000,
  });
}

/** Uninstall plugin dependencies / 卸载插件依赖 */
export function uninstallPluginDependenciesApi(
  id: number,
  payload: { python?: boolean } = {},
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

/** Refresh plugin schedules / 刷新插件调度 */
export function refreshPluginSchedulesApi(id: number) {
  return requestClient.post<PluginScheduleRefreshResult>(
    `${BASE_URL}/${id}/refresh-schedules`,
    undefined,
    {
      timeout: 120_000,
    },
  );
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

/** Get plugin lifecycle audit / 获取插件生命周期审计 */
export function getPluginLifecycleAuditApi(params?: {
  plugin_id?: number;
  tenant_id?: number;
}) {
  return requestClient.get<PluginLifecycleAuditReport>(
    `${BASE_URL}/runtime/audit`,
    {
      params,
    },
  );
}

// ── Frontend slots / 前端插槽 ──

/** Get plugin slots / 获取插件插槽 */
export function getPluginSlotsApi() {
  return requestClient.get<PluginSlotsResponse>(`${BASE_URL}/slots`);
}

export type { PluginSlotData, PluginSlotsResponse };

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
