import type { ConfigField, TenantOption } from './types';

import type {
  PluginBackupInfo,
  PluginInfo,
  PluginLicenseInfo,
  PluginLifecycleAuditReport,
  PluginTenantAssignmentInfo,
  PluginVersionInfo,
} from '#/api/admin/plugin';

import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

import { preferences } from '@vben/preferences';

import { message, Modal } from 'ant-design-vue';

import {
  activatePluginLicenseApi,
  activatePluginTrialApi,
  assignPluginTenantsApi,
  deletePluginBackupApi,
  getPluginDetailApi,
  getPluginLicenseApi,
  getPluginLifecycleAuditApi,
  getPluginTenantsApi,
  getPluginVersionsApi,
  listPluginBackupsApi,
  revokePluginLicenseApi,
  rollbackPluginApi,
  unassignPluginTenantApi,
  updatePluginConfigApi,
  upgradePluginApi,
} from '#/api/admin/plugin';
import { getTenantListApi } from '#/api/admin/tenant';
import { scopeNeedsAssignment } from '#/components/business/scope-select';
import { refreshAdminMenusAndPluginRoutes as refreshAdminRoutes } from '#/composables/use-plugin-admin-refresh';
import { $t } from '#/locales';
import { resolvePluginMetadataIcon } from '#/utils/plugin-metadata-icon';

import { derivePluginType } from '../../data';
import {
  getPluginRecoveryMeta,
  getPluginRecoveryState,
  hasPluginRecoveryAction,
  hasPluginScheduledTasks,
} from '../../plugin-recovery';
import { usePluginAdminActions } from '../../use-plugin-admin-actions';

interface UsePluginConfigDrawerOptions {
  onSaved: () => Promise<void> | void;
}

interface UploadRequestOptions {
  file: Blob | File | string;
  onError?: (error: Error) => void;
  onSuccess?: (body: unknown) => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isDataEnvelope<T>(value: unknown): value is { data: T } {
  return isRecord(value) && 'data' in value;
}

function normalizeObjectResponse<T extends object>(
  value: T | unknown,
): null | T {
  if (
    isDataEnvelope<T>(value) &&
    value.data &&
    typeof value.data === 'object'
  ) {
    return value.data;
  }
  if (value && typeof value === 'object') {
    return value as T;
  }
  return null;
}

function normalizeArrayResponse<T>(value: unknown): T[] {
  if (isDataEnvelope<T[]>(value) && Array.isArray(value.data)) {
    return value.data;
  }
  if (Array.isArray(value)) {
    return value;
  }
  return [];
}

function toError(value: unknown): Error {
  return value instanceof Error ? value : new Error(String(value));
}

export function usePluginConfigDrawer(options: UsePluginConfigDrawerOptions) {
  const router = useRouter();

  const visible = ref(false);
  const plugin = ref<null | PluginInfo>(null);
  const loading = ref(false);
  const versions = ref<PluginVersionInfo[]>([]);
  const configJson = ref('');
  const configValues = ref<Record<string, unknown>>({});
  const configSaving = ref(false);
  const upgrading = ref(false);
  const pluginAuditLoading = ref(false);
  const pluginAuditPayload = ref<null | PluginLifecycleAuditReport>(null);

  const tenantAssignments = ref<PluginTenantAssignmentInfo[]>([]);
  const allTenants = ref<TenantOption[]>([]);
  const tenantLoading = ref(false);
  const showTenantSelect = ref(false);
  const selectedTenantIds = ref<number[]>([]);

  const licenseInfo = ref<null | PluginLicenseInfo>(null);
  const licenseLoading = ref(false);
  const licenseKeyInput = ref('');
  const licenseActivating = ref(false);

  const backups = ref<PluginBackupInfo[]>([]);
  const backupsLoading = ref(false);

  const currentLocale = computed(() => preferences.app.locale || 'zh-CN');

  const needsTenantAssignment = computed(() => {
    if (!plugin.value) return false;
    const manifest = isRecord(plugin.value.manifest)
      ? plugin.value.manifest
      : undefined;
    const scope =
      plugin.value.scope ||
      manifest?.scope;
    return scopeNeedsAssignment(String(scope || ''));
  });

  const pluginHasAiFeatures = computed(() => {
    const ar = plugin.value?.ai_requirements;
    if (!ar || typeof ar !== 'object') return false;
    const features = (ar as { features?: unknown }).features;
    return Array.isArray(features) && features.length > 0;
  });

  const assignedTenantIds = computed(
    () => new Set(tenantAssignments.value.map((a) => a.tenant_id)),
  );
  const availableTenants = computed(() =>
    allTenants.value.filter((t) => !assignedTenantIds.value.has(t.id)),
  );

  const configSchemaFields = computed<ConfigField[]>(() => {
    const manifest = isRecord(plugin.value?.manifest)
      ? plugin.value.manifest
      : undefined;
    const schema = isRecord(manifest?.config_schema)
      ? manifest.config_schema
      : undefined;
    const properties = schema?.properties;
    if (!isRecord(properties)) return [];
    const locale = currentLocale.value;
    return Object.entries(properties).flatMap(([key, rawProp]) => {
      if (!isRecord(rawProp)) return [];
      const prop = rawProp;
      const titleRaw = prop.title;
      const descRaw = prop.description;
      const title =
        isRecord(titleRaw)
          ? (titleRaw as Record<string, string>)[locale] ||
            (titleRaw as Record<string, string>).en ||
            key
          : String(titleRaw || key);
      const description =
        isRecord(descRaw)
          ? (descRaw as Record<string, string>)[locale] ||
            (descRaw as Record<string, string>).en ||
            ''
          : String(descRaw || '');
      return [{
        key,
        format: typeof prop.format === 'string' ? prop.format : undefined,
        type: String(prop.type || 'string'),
        title,
        description,
        default: prop.default,
        enum: Array.isArray(prop.enum)
          ? prop.enum.filter((item): item is string => typeof item === 'string')
          : undefined,
        minimum: typeof prop.minimum === 'number' ? prop.minimum : undefined,
        maximum: typeof prop.maximum === 'number' ? prop.maximum : undefined,
      }];
    });
  });

  const hasConfigToShow = computed(() => {
    if (configSchemaFields.value.length > 0) return true;
    const cfg = plugin.value?.config;
    return !!cfg && Object.keys(cfg).length > 0;
  });

  const recoveryState = computed(() =>
    plugin.value ? getPluginRecoveryState(plugin.value) : null,
  );
  const recoveryMeta = computed(() =>
    plugin.value ? getPluginRecoveryMeta(plugin.value) : null,
  );
  const pluginType = computed(() =>
    derivePluginType(plugin.value?.manifest ?? null),
  );
  const isPaidPlugin = computed(
    () => plugin.value?.pricing_type === 'paid' || plugin.value?.tier === 'pro',
  );

  const pluginActions = usePluginAdminActions({
    afterMutation: async () => {
      await reload();
      await options.onSaved();
      await refreshAdminMenusAndPluginRoutes();
    },
    afterUninstall: async () => {
      visible.value = false;
      await options.onSaved();
      await refreshAdminMenusAndPluginRoutes();
    },
  });

  async function refreshAdminMenusAndPluginRoutes() {
    await refreshAdminRoutes(router);
  }

  async function open(row: PluginInfo) {
    plugin.value = row;
    visible.value = true;
    configJson.value = JSON.stringify(row.config || {}, null, 2);
    configValues.value = { ...row.config };
    await Promise.allSettled([
      loadDetail(row.id),
      loadVersions(row.id),
      loadTenantAssignments(row.id),
      loadLicense(row.id),
      loadBackups(row.id),
      loadPluginAudit(row.id),
    ]);
  }

  async function loadDetail(id: number) {
    try {
      const response = await getPluginDetailApi(id, {
        locale: currentLocale.value,
      });
      const data = normalizeObjectResponse<PluginInfo>(response);
      if (!data) return;
      plugin.value = data;
      configJson.value = JSON.stringify(data.config || {}, null, 2);
      configValues.value = { ...data.config };
    } catch {
      // noop
    }
  }

  async function reload() {
    if (!plugin.value) return;
    loading.value = true;
    try {
      await loadDetail(plugin.value.id);
      await Promise.allSettled([
        loadVersions(plugin.value.id),
        loadTenantAssignments(plugin.value.id),
        loadLicense(plugin.value.id),
        loadBackups(plugin.value.id),
        loadPluginAudit(plugin.value.id),
      ]);
    } finally {
      loading.value = false;
    }
  }

  async function loadPluginAudit(pluginId: number) {
    pluginAuditLoading.value = true;
    try {
      const payload = await getPluginLifecycleAuditApi({ plugin_id: pluginId });
      pluginAuditPayload.value =
        payload && typeof payload === 'object'
          ? (payload as PluginLifecycleAuditReport)
          : null;
    } catch {
      pluginAuditPayload.value = null;
    } finally {
      pluginAuditLoading.value = false;
    }
  }

  function prettyJson(value: unknown) {
    return JSON.stringify(value ?? {}, null, 2);
  }

  async function loadVersions(id: number) {
    try {
      const response = await getPluginVersionsApi(id);
      versions.value = normalizeArrayResponse<PluginVersionInfo>(response);
    } catch {
      versions.value = [];
    }
  }

  async function loadTenantAssignments(id: number) {
    if (!needsTenantAssignment.value) return;
    tenantLoading.value = true;
    try {
      const response = await getPluginTenantsApi(id);
      tenantAssignments.value =
        normalizeArrayResponse<PluginTenantAssignmentInfo>(response);
      const tenantRes = await getTenantListApi({ 'page[size]': 200 });
      allTenants.value = (tenantRes?.items ?? []).map((t) => {
        const tenant = t as {
          display_name?: string;
          id: number;
          name?: string;
        };
        return {
          id: tenant.id,
          name: tenant.name || tenant.display_name || `Tenant #${tenant.id}`,
        };
      });
    } catch {
      tenantAssignments.value = [];
      allTenants.value = [];
    } finally {
      tenantLoading.value = false;
    }
  }

  async function onAssignTenants() {
    if (!plugin.value || selectedTenantIds.value.length === 0) return;
    try {
      await assignPluginTenantsApi(plugin.value.id, selectedTenantIds.value);
      message.success(
        $t('admin.plugin.messages.assignSuccess') || 'Tenants assigned',
      );
      selectedTenantIds.value = [];
      showTenantSelect.value = false;
      await loadTenantAssignments(plugin.value.id);
    } catch {
      message.error($t('admin.plugin.assignFailed'));
    }
  }

  async function onUnassignTenant(tenantId: number) {
    if (!plugin.value) return;
    try {
      await unassignPluginTenantApi(plugin.value.id, tenantId);
      await loadTenantAssignments(plugin.value.id);
    } catch {
      message.error($t('admin.plugin.unassignFailed'));
    }
  }

  function getTenantName(tenantId: number) {
    return (
      allTenants.value.find((t) => t.id === tenantId)?.name ??
      `Tenant #${tenantId}`
    );
  }

  async function onEnable() {
    if (!plugin.value) return;
    await pluginActions.onEnable(plugin.value);
  }

  function onDisable() {
    if (!plugin.value) return;
    pluginActions.onDisable(plugin.value);
  }

  function onUninstall() {
    if (!plugin.value) return;
    pluginActions.onUninstall(plugin.value);
  }

  function onRepair() {
    if (!plugin.value) return;
    pluginActions.onRepair(plugin.value);
  }

  function hasScheduledTasks() {
    return plugin.value ? hasPluginScheduledTasks(plugin.value) : false;
  }

  function hasRecoveryAction(
    action:
      | 'force_cleanup'
      | 'install_dependencies'
      | 'refresh_schedules'
      | 'repair',
  ) {
    return plugin.value ? hasPluginRecoveryAction(plugin.value, action) : false;
  }

  function onRefreshSchedules() {
    if (!plugin.value) return;
    pluginActions.onRefreshSchedules(plugin.value);
  }

  async function onSaveConfig() {
    if (!plugin.value) return;
    configSaving.value = true;
    try {
      const data =
        configSchemaFields.value.length > 0
          ? { ...configValues.value }
          : JSON.parse(configJson.value);
      await updatePluginConfigApi(plugin.value.id, data);
      message.success($t('admin.plugin.config.saveSuccess'));
      await reload();
      await options.onSaved();
    } catch (error) {
      if (error instanceof SyntaxError) {
        message.error($t('admin.plugin.invalidJson'));
      }
    } finally {
      configSaving.value = false;
    }
  }

  async function onUpgrade(info: { file: File }) {
    if (!plugin.value) return;
    upgrading.value = true;
    try {
      await upgradePluginApi(plugin.value.id, info.file);
      message.success($t('admin.plugin.messages.upgradeSuccess'));
      await reload();
      await loadVersions(plugin.value.id);
      await options.onSaved();
      await refreshAdminMenusAndPluginRoutes();
    } catch {
      message.error($t('admin.plugin.messages.upgradeFailed'));
    } finally {
      upgrading.value = false;
    }
  }

  async function handleUpgradeUploadRequest(options: UploadRequestOptions) {
    const { file, onError, onSuccess } = options;
    if (!(file instanceof File)) {
      onError?.(new Error('Invalid upload file'));
      return;
    }
    try {
      await onUpgrade({ file });
      onSuccess?.({});
    } catch (error) {
      onError?.(toError(error));
    }
  }

  function onRollback(version: string) {
    if (!plugin.value) return;
    const pluginVal = plugin.value;
    Modal.confirm({
      title: `${$t('admin.plugin.action.rollback')} -> v${version}`,
      okType: 'danger',
      onOk: () => {
        rollbackPluginApi(pluginVal.id, version)
          .then(async () => {
            message.success($t('admin.plugin.messages.rollbackSuccess'));
            await loadVersions(pluginVal.id);
            await reload();
            await options.onSaved();
            await refreshAdminMenusAndPluginRoutes();
          })
          .catch(() => {
            message.error($t('admin.plugin.messages.rollbackFailed'));
          });
      },
    });
  }

  async function loadLicense(id: number) {
    licenseLoading.value = true;
    try {
      const response = await getPluginLicenseApi(id);
      licenseInfo.value = normalizeObjectResponse<PluginLicenseInfo>(response);
    } catch {
      licenseInfo.value = null;
    } finally {
      licenseLoading.value = false;
    }
  }

  async function onActivateLicense() {
    if (!plugin.value || !licenseKeyInput.value.trim()) return;
    licenseActivating.value = true;
    try {
      await activatePluginLicenseApi(
        plugin.value.id,
        licenseKeyInput.value.trim(),
      );
      message.success($t('admin.plugin.license.activateSuccess'));
      licenseKeyInput.value = '';
      await loadLicense(plugin.value.id);
      await reload();
      await options.onSaved();
    } catch {
      message.error($t('admin.plugin.license.activateFailed'));
    } finally {
      licenseActivating.value = false;
    }
  }

  async function onActivateTrial() {
    if (!plugin.value) return;
    licenseActivating.value = true;
    try {
      await activatePluginTrialApi(plugin.value.id);
      message.success($t('admin.plugin.license.trialActivated'));
      await loadLicense(plugin.value.id);
      await reload();
      await options.onSaved();
    } catch {
      message.error($t('admin.plugin.license.trialFailed'));
    } finally {
      licenseActivating.value = false;
    }
  }

  function onRevokeLicense() {
    const pluginId = plugin.value?.id;
    if (!pluginId) return;
    Modal.confirm({
      title: $t('admin.plugin.license.revokeConfirm'),
      okType: 'danger',
      async onOk() {
        await revokePluginLicenseApi(pluginId);
        message.success($t('admin.plugin.license.revokeSuccess'));
        await loadLicense(pluginId);
        await reload();
        await options.onSaved();
      },
    });
  }

  function getLicenseStatusColor(status: string): string {
    switch (status) {
      case 'active': {
        return 'success';
      }
      case 'expired': {
        return 'error';
      }
      case 'trial': {
        return 'processing';
      }
      default: {
        return 'default';
      }
    }
  }

  function getLicenseStatusText(status: string): string {
    const map: Record<string, string> = {
      active: $t('admin.plugin.license.status_active'),
      trial: $t('admin.plugin.license.status_trial'),
      expired: $t('admin.plugin.license.status_expired'),
      none: $t('admin.plugin.license.status_none'),
      invalid: $t('admin.plugin.license.status_invalid'),
    };
    return map[status] || status;
  }

  async function loadBackups(pluginId: number) {
    backupsLoading.value = true;
    try {
      const res = await listPluginBackupsApi(pluginId);
      backups.value = Array.isArray(res) ? res : [];
    } catch {
      backups.value = [];
    } finally {
      backupsLoading.value = false;
    }
  }

  async function onDeleteBackup(backupName: string) {
    const pluginId = plugin.value?.id;
    if (!pluginId) return;
    Modal.confirm({
      title: $t('admin.plugin.backup.deleteConfirm'),
      okType: 'danger',
      async onOk() {
        await deletePluginBackupApi(pluginId, backupName);
        message.success($t('admin.plugin.backup.deleteSuccess'));
        await loadBackups(pluginId);
      },
    });
  }

  function goToAgentAssignments() {
    router.push('/admin/ai/agent-assignments');
  }

  function setShowTenantSelect(value: boolean) {
    showTenantSelect.value = value;
  }

  function setSelectedTenantIds(value: number[]) {
    selectedTenantIds.value = value;
  }

  function setConfigJson(value: string) {
    configJson.value = value;
  }

  function setConfigValue(key: string, value: unknown) {
    configValues.value[key] = value;
  }

  function getPluginMetadataIcon(
    pluginName: string,
    icon: null | string | undefined,
  ) {
    return resolvePluginMetadataIcon(pluginName, icon, {
      endpoint: 'admin',
    });
  }

  return {
    visible,
    plugin,
    loading,
    versions,
    configJson,
    configValues,
    configSaving,
    upgrading,
    pluginAuditLoading,
    pluginAuditPayload,
    tenantAssignments,
    allTenants,
    tenantLoading,
    showTenantSelect,
    selectedTenantIds,
    licenseInfo,
    licenseLoading,
    licenseKeyInput,
    licenseActivating,
    needsTenantAssignment,
    pluginHasAiFeatures,
    availableTenants,
    configSchemaFields,
    hasConfigToShow,
    recoveryState,
    recoveryMeta,
    pluginType,
    isPaidPlugin,
    backups,
    backupsLoading,
    pluginActions,
    open,
    reload,
    loadPluginAudit,
    prettyJson,
    onAssignTenants,
    onUnassignTenant,
    getTenantName,
    onEnable,
    onDisable,
    onUninstall,
    onRepair,
    hasScheduledTasks,
    hasRecoveryAction,
    onRefreshSchedules,
    onSaveConfig,
    onUpgrade,
    handleUpgradeUploadRequest,
    onRollback,
    onActivateLicense,
    onActivateTrial,
    onRevokeLicense,
    getLicenseStatusColor,
    getLicenseStatusText,
    loadBackups,
    onDeleteBackup,
    goToAgentAssignments,
    setShowTenantSelect,
    setSelectedTenantIds,
    setConfigJson,
    setConfigValue,
    getPluginMetadataIcon,
  };
}
