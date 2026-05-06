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
  | 'api'
  | 'global'
  | 'platform'
  | 'runtime'
  | 'tenant'
  | 'user';

export type PluginTenantExposureMode =
  | 'all_tenants'
  | 'none'
  | 'partial_tenants'
  | 'platform_only'
  | 'platform_or_user'
  | 'scope_inherited'
  | 'selected_tenants'
  | 'specified_tenants'
  | 'user_side';

export interface PluginTenantExposureProfile {
  assigned_tenant_ids?: number[];
  default_enabled?: boolean;
  mode?: string;
  requires_explicit_assignment?: boolean;
  tenant_assignment_required?: boolean;
  tenant_ids?: number[];
}

export interface PluginCompatibilityProfile {
  declared_editions?: string[] | string | Record<string, boolean>;
  edition_support?: Record<string, boolean>;
  editions?: string[] | string | Record<string, boolean>;
  is_saas_compatible?: boolean;
  is_single_management_compatible?: boolean;
  notes?: string[];
  requires_tenant_assignment?: boolean;
  saas_compatible?: boolean;
  single_compatible?: boolean;
  single_management_compatible?: boolean;
  supported_editions?: string[] | string | Record<string, boolean>;
  supported_surfaces?: string[] | string | Record<string, boolean>;
  surfaces?: string[] | string | Record<string, boolean>;
  tenant_assignment_required?: boolean;
  tenant_exposure?: PluginTenantExposureProfile | string;
  tenant_exposure_mode?: string;
}

export interface PluginLegacyCompatibility {
  conflicts?: string[];
  conflicts_count?: number;
  platform_version?: string;
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
  compatibility?: null | PluginCompatibilityProfile | PluginLegacyCompatibility;
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
  tenantExposureMode: 'scope_inherited',
};

const TENANT_EXPOSURE_LABEL_KEYS: Record<PluginTenantExposureMode, string> = {
  all_tenants: 'admin.plugin.compatibility.tenantExposure.allTenants',
  none: 'admin.plugin.compatibility.tenantExposure.none',
  partial_tenants: 'admin.plugin.compatibility.tenantExposure.partialTenants',
  platform_only: 'admin.plugin.compatibility.tenantExposure.platformOnly',
  platform_or_user: 'admin.plugin.compatibility.tenantExposure.platformOrUser',
  scope_inherited: 'admin.plugin.compatibility.tenantExposure.scopeInherited',
  selected_tenants: 'admin.plugin.compatibility.tenantExposure.selectedTenants',
  specified_tenants:
    'admin.plugin.compatibility.tenantExposure.specifiedTenants',
  user_side: 'admin.plugin.compatibility.tenantExposure.userSide',
};

const TENANT_EXPOSURE_COLORS: Record<PluginTenantExposureMode, string> = {
  all_tenants: 'success',
  none: 'default',
  partial_tenants: 'orange',
  platform_only: 'blue',
  platform_or_user: 'geekblue',
  scope_inherited: 'default',
  selected_tenants: 'cyan',
  specified_tenants: 'purple',
  user_side: 'processing',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getRecord(
  source: null | Record<string, unknown> | undefined,
  key: string,
): null | Record<string, unknown> {
  const value = source?.[key];
  return isRecord(value) ? value : null;
}

function getString(
  source: null | Record<string, unknown> | undefined,
  keys: string[],
): string | undefined {
  for (const key of keys) {
    const value = source?.[key];
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  return undefined;
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

function normalizeStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter(
      (item): item is string => typeof item === 'string' && item.length > 0,
    );
  }
  if (typeof value === 'string' && value.trim()) {
    return [value];
  }
  if (isRecord(value)) {
    return Object.entries(value).flatMap(([key, enabled]) =>
      enabled === true ? [key] : [],
    );
  }
  return [];
}

function getStringList(
  source: null | Record<string, unknown> | undefined,
  keys: string[],
): string[] {
  for (const key of keys) {
    const values = normalizeStringList(source?.[key]);
    if (values.length > 0) {
      return values;
    }
  }
  return [];
}

function normalizeEdition(value: string): null | PluginCompatibilityEdition {
  const normalized = value.trim().toLowerCase().replaceAll('-', '_');
  if (normalized === 'saas') {
    return 'saas';
  }
  if (
    normalized === 'single' ||
    normalized === 'single_management' ||
    normalized === 'single_management_admin'
  ) {
    return 'single_management';
  }
  return null;
}

function normalizeSurface(value: string): null | PluginCompatibilitySurface {
  const normalized = value.trim().toLowerCase().replaceAll('-', '_');
  if (
    normalized === 'admin' ||
    normalized === 'api' ||
    normalized === 'global' ||
    normalized === 'platform' ||
    normalized === 'runtime' ||
    normalized === 'tenant' ||
    normalized === 'user'
  ) {
    return normalized;
  }
  return null;
}

function normalizeTenantExposureMode(
  value: null | string | undefined,
  fallback: PluginTenantExposureMode,
): PluginTenantExposureMode {
  const normalized = (value || '').trim().toLowerCase().replaceAll('-', '_');
  switch (normalized) {
    case 'all':
    case 'all_tenants': {
      return 'all_tenants';
    }
    case 'explicit':
    case 'explicit_assignment':
    case 'selected':
    case 'selected_tenants':
    case 'tenant_assignment': {
      return 'selected_tenants';
    }
    case 'partial':
    case 'partial_tenants': {
      return 'partial_tenants';
    }
    case 'specified':
    case 'specified_tenants': {
      return 'specified_tenants';
    }
    case 'admin':
    case 'admin_only':
    case 'platform':
    case 'platform_only': {
      return 'platform_only';
    }
    case 'platform_and_user':
    case 'platform_or_user':
    case 'platform_user': {
      return 'platform_or_user';
    }
    case 'user':
    case 'user_only':
    case 'user_side': {
      return 'user_side';
    }
    case 'none': {
      return 'none';
    }
    case 'scope_inherited': {
      return 'scope_inherited';
    }
    case 'scope_default': {
      return fallback;
    }
    default: {
      return fallback;
    }
  }
}

function deriveTenantExposureModeFromScope(
  scope: null | string | undefined,
): PluginTenantExposureMode {
  switch (scope) {
    case 'all_tenants': {
      return 'all_tenants';
    }
    case 'global_shared': {
      return 'all_tenants';
    }
    case 'admin_and_selected_tenants': {
      return 'partial_tenants';
    }
    case 'selected_tenants': {
      return 'selected_tenants';
    }
    case 'admin_only':
    case 'platform': {
      return 'platform_only';
    }
    default: {
      return 'scope_inherited';
    }
  }
}

function getCompatibilityProfileRecord(
  source: null | PluginCompatibilitySource | undefined,
): null | Record<string, unknown> {
  if (!source || !isRecord(source)) {
    return null;
  }
  const pluginInfo = getRecord(source, 'plugin_info');
  const manifest =
    getRecord(source, 'manifest') ?? getRecord(pluginInfo, 'manifest');
  return (
    getRecord(source, 'compatibility_profile') ??
    getRecord(pluginInfo, 'compatibility_profile') ??
    getRecord(manifest, 'compatibility_profile') ??
    getRecord(source, 'compatibility') ??
    getRecord(pluginInfo, 'compatibility') ??
    getRecord(manifest, 'compatibility')
  );
}

function getCompatibilityScope(
  source: null | PluginCompatibilitySource | undefined,
): null | string | undefined {
  if (!source || !isRecord(source)) {
    return undefined;
  }
  const pluginInfo = getRecord(source, 'plugin_info');
  const manifest =
    getRecord(source, 'manifest') ?? getRecord(pluginInfo, 'manifest');
  return (
    (typeof source.scope === 'string' ? source.scope : undefined) ??
    getString(pluginInfo, ['scope']) ??
    getString(manifest, ['scope'])
  );
}

export function resolvePluginCompatibilityProfile(
  source: null | PluginCompatibilitySource | undefined,
): ResolvedPluginCompatibilityProfile {
  const profile = getCompatibilityProfileRecord(source);
  const tenantExposureValue = profile?.tenant_exposure;
  const tenantExposure = isRecord(tenantExposureValue)
    ? tenantExposureValue
    : null;
  const scope = getCompatibilityScope(source);
  const editionValues = getStringList(profile, [
    'declared_editions',
    'editions',
    'supported_editions',
  ]);
  const editionSupport = getRecord(profile, 'edition_support');
  const allEditionValues = [
    ...editionValues,
    ...normalizeStringList(editionSupport),
  ];
  const editions = Array.from(
    new Set(
      allEditionValues
        .map((value) => normalizeEdition(value))
        .filter((value): value is PluginCompatibilityEdition => value !== null),
    ),
  );
  const saasCompatible =
    getBoolean(profile, ['is_saas_compatible', 'saas_compatible']) ??
    (editions.length > 0
      ? editions.includes('saas')
      : DEFAULT_COMPATIBILITY_PROFILE.saasCompatible);
  const singleManagementCompatible =
    getBoolean(profile, [
      'is_single_management_compatible',
      'single_management_compatible',
      'single_compatible',
    ]) ??
    (editions.length > 0
      ? editions.includes('single_management')
      : DEFAULT_COMPATIBILITY_PROFILE.singleManagementCompatible);
  const surfaces = Array.from(
    new Set(
      getStringList(profile, ['surfaces', 'supported_surfaces'])
        .map((value) => normalizeSurface(value))
        .filter((value): value is PluginCompatibilitySurface => value !== null),
    ),
  );
  const fallbackExposureMode = deriveTenantExposureModeFromScope(scope);
  const tenantExposureText =
    typeof tenantExposureValue === 'string' ? tenantExposureValue : undefined;
  const tenantExposureMode = normalizeTenantExposureMode(
    tenantExposureText ??
      getString(tenantExposure, ['mode']) ??
      getString(profile, ['tenant_exposure_mode']),
    fallbackExposureMode,
  );
  const explicitAssignmentRequired =
    getBoolean(tenantExposure, [
      'requires_explicit_assignment',
      'tenant_assignment_required',
    ]) ??
    getBoolean(profile, [
      'requires_tenant_assignment',
      'tenant_assignment_required',
    ]);
  const assignmentModeRequiresTenants =
    tenantExposureMode === 'partial_tenants' ||
    tenantExposureMode === 'selected_tenants' ||
    tenantExposureMode === 'specified_tenants';
  const tenantAssignmentRequired =
    explicitAssignmentRequired ?? assignmentModeRequiresTenants;

  return {
    editions: editions.length > 0 ? editions : ['saas'],
    saasCompatible,
    singleManagementCompatible,
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
  compatibility?: null | PluginCompatibilityProfile | PluginLegacyCompatibility;
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
  compatibility?: PluginCompatibilityProfile | PluginLegacyCompatibility;
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
