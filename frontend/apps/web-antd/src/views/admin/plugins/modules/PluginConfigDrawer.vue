<script setup lang="ts">
/**
 * Plugin config drawer (based on legacy PluginConfigDrawer)
 * 插件配置抽屉（参考旧版 PluginConfigDrawer）
 *
 * Shows plugin details + config editing + version history + health status
 * 展示插件详情 + 配置编辑 + 版本历史 + 健康状态
 */
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

import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';

import {
  Alert,
  Button,
  Collapse,
  CollapsePanel,
  Descriptions,
  DescriptionsItem,
  Drawer,
  Form,
  FormItem,
  Input,
  InputNumber,
  message,
  Modal,
  Select,
  SelectOption,
  Switch,
  Table,
  Tag,
  Upload,
} from 'ant-design-vue';

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
import { ConfigImagePicker } from '#/components/business/config-image-picker';
import { MarkdownRender } from '#/components/business/markdown-render';
import { scopeNeedsAssignment } from '#/components/business/scope-select';
import { refreshAdminMenusAndPluginRoutes as _refreshAdminRoutes } from '#/composables/use-plugin-admin-refresh';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { resolvePluginMetadataIcon } from '#/utils/plugin-metadata-icon';
import { getScopeText } from '#/utils/scope-helpers';

import {
  derivePluginType,
  getStatusColor,
  getStatusText,
  getTierColor,
  getTierText,
  getTypeColor,
  getTypeText,
} from '../data';
import {
  getPluginRecoveryMeta,
  getPluginRecoveryState,
  hasPluginRecoveryAction,
  hasPluginScheduledTasks,
} from '../plugin-recovery';
import { usePluginAdminActions } from '../use-plugin-admin-actions';

const emit = defineEmits<{ saved: [] }>();

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
const allTenants = ref<Array<{ id: number; name: string }>>([]);
const tenantLoading = ref(false);
const showTenantSelect = ref(false);
const selectedTenantIds = ref<number[]>([]);

// License / 许可证
const licenseInfo = ref<null | PluginLicenseInfo>(null);
const licenseLoading = ref(false);
const licenseKeyInput = ref('');
const licenseActivating = ref(false);

const needsTenantAssignment = computed(() => {
  if (!plugin.value) return false;
  const scope =
    plugin.value.scope ||
    (plugin.value.manifest as Record<string, unknown>)?.scope;
  return scopeNeedsAssignment(String(scope || ''));
});

/** 插件声明了 AI 功能（需在「AI 功能分配」统一绑定）/ Plugin declares AI features */
const pluginHasAiFeatures = computed(() => {
  const ar = plugin.value?.ai_requirements;
  if (!ar || typeof ar !== 'object') return false;
  const features = (ar as { features?: unknown }).features;
  return Array.isArray(features) && features.length > 0;
});

function goToAgentAssignments() {
  router.push('/admin/ai/agent-assignments');
}

const assignedTenantIds = computed(
  () => new Set(tenantAssignments.value.map((a) => a.tenant_id)),
);

const availableTenants = computed(() =>
  allTenants.value.filter((t) => !assignedTenantIds.value.has(t.id)),
);

async function refreshAdminMenusAndPluginRoutes() {
  await _refreshAdminRoutes(router);
}

const pluginActions = usePluginAdminActions({
  afterMutation: async () => {
    await reload();
    emit('saved');
    await refreshAdminMenusAndPluginRoutes();
  },
  afterUninstall: async () => {
    visible.value = false;
    emit('saved');
    await refreshAdminMenusAndPluginRoutes();
  },
});

interface ConfigField {
  key: string;
  format?: string;
  type: string;
  title: string;
  description: string;
  default: unknown;
  enum?: string[];
  minimum?: number;
  maximum?: number;
}

const currentLocale = computed(() => preferences.app.locale || 'zh-CN');

const configSchemaFields = computed<ConfigField[]>(() => {
  const manifest = plugin.value?.manifest as
    | Record<string, unknown>
    | undefined;
  const schema = manifest?.config_schema as Record<string, unknown> | undefined;
  if (!schema || !schema.properties) return [];

  const props = schema.properties as Record<string, Record<string, unknown>>;
  const locale = currentLocale.value;

  return Object.entries(props).map(([key, prop]) => {
    const titleRaw = prop.title;
    const descRaw = prop.description;
    const title =
      typeof titleRaw === 'object' && titleRaw !== null
        ? (titleRaw as Record<string, string>)[locale] ||
          (titleRaw as Record<string, string>).en ||
          key
        : String(titleRaw || key);
    const description =
      typeof descRaw === 'object' && descRaw !== null
        ? (descRaw as Record<string, string>)[locale] ||
          (descRaw as Record<string, string>).en ||
          ''
        : String(descRaw || '');

    return {
      key,
      format: typeof prop.format === 'string' ? prop.format : undefined,
      type: String(prop.type || 'string'),
      title,
      description,
      default: prop.default,
      enum: prop.enum as string[] | undefined,
      minimum: prop.minimum as number | undefined,
      maximum: prop.maximum as number | undefined,
    };
  });
});

const hasConfigToShow = computed(() => {
  if (configSchemaFields.value.length > 0) return true;
  const cfg = plugin.value?.config;
  return !!cfg && Object.keys(cfg).length > 0;
});

const recoveryState = computed(() => {
  return plugin.value ? getPluginRecoveryState(plugin.value) : null;
});

const recoveryMeta = computed(() => {
  return plugin.value ? getPluginRecoveryMeta(plugin.value) : null;
});

async function open(row: PluginInfo) {
  plugin.value = row;
  visible.value = true;
  configJson.value = JSON.stringify(row.config || {}, null, 2);
  configValues.value = { ...row.config };
  loadDetail(row.id);
  loadVersions(row.id);
  loadTenantAssignments(row.id);
  loadLicense(row.id);
  loadBackups(row.id);
  loadPluginAudit(row.id);
}

async function loadDetail(id: number) {
  try {
    const res = (await getPluginDetailApi(id, {
      locale: currentLocale.value,
    })) as unknown as { data: PluginInfo };
    const data = res?.data ?? (res as unknown as PluginInfo);
    plugin.value = data;
    configJson.value = JSON.stringify(data.config || {}, null, 2);
    configValues.value = { ...data.config };
  } catch {
    //
  }
}

async function reload() {
  if (!plugin.value) return;
  loading.value = true;
  try {
    await loadDetail(plugin.value.id);
    await loadPluginAudit(plugin.value.id);
  } catch {
    //
  } finally {
    loading.value = false;
  }
}

async function loadPluginAudit(pluginId: number) {
  pluginAuditLoading.value = true;
  try {
    pluginAuditPayload.value = await getPluginLifecycleAuditApi({
      plugin_id: pluginId,
    });
  } catch {
    pluginAuditPayload.value = null;
  } finally {
    pluginAuditLoading.value = false;
  }
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

async function loadVersions(id: number) {
  try {
    const res = (await getPluginVersionsApi(id)) as unknown as {
      data: PluginVersionInfo[];
    };
    versions.value = res?.data ?? (res as unknown as PluginVersionInfo[]) ?? [];
  } catch {
    versions.value = [];
  }
}

async function loadTenantAssignments(id: number) {
  if (!needsTenantAssignment.value) return;
  tenantLoading.value = true;
  try {
    const res = (await getPluginTenantsApi(
      id,
    )) as unknown as PluginTenantAssignmentInfo[];
    tenantAssignments.value = Array.isArray(res)
      ? res
      : ((res as unknown as { data: PluginTenantAssignmentInfo[] })?.data ??
        []);
    const tenantRes = await getTenantListApi({ 'page[size]': 200 });
    allTenants.value = (tenantRes?.items ?? []).map(
      (t: { display_name?: string; id: number; name?: string }) => ({
        id: t.id,
        name: t.name || t.display_name || `Tenant #${t.id}`,
      }),
    );
  } catch {
    tenantAssignments.value = [];
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

function getTenantName(tenantId: number): string {
  return (
    allTenants.value.find((t) => t.id === tenantId)?.name ??
    `Tenant #${tenantId}`
  );
}

async function onEnable() {
  if (!plugin.value) return;
  pluginActions.onEnable(plugin.value);
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
    const data: Record<string, unknown> =
      configSchemaFields.value.length > 0
        ? { ...configValues.value }
        : JSON.parse(configJson.value);
    await updatePluginConfigApi(plugin.value.id, data);
    message.success($t('admin.plugin.config.saveSuccess'));
    await reload();
    emit('saved');
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
    await upgradePluginApi(plugin.value.id, info.file as File);
    message.success($t('admin.plugin.messages.upgradeSuccess'));
    await reload();
    await loadVersions(plugin.value.id);
    emit('saved');
  } catch {
    //
  } finally {
    upgrading.value = false;
  }
}

function onRollback(version: string) {
  if (!plugin.value) return;
  const pluginVal = plugin.value;
  Modal.confirm({
    title: `${$t('admin.plugin.action.rollback')} → v${version}`,
    okType: 'danger',
    onOk() {
      // Don't return Promise, let Modal close immediately / 不 return Promise，让 Modal 立即关闭
      rollbackPluginApi(pluginVal.id, version)
        .then(async () => {
          message.success($t('admin.plugin.messages.rollbackSuccess'));
          await reload();
          await loadVersions(pluginVal.id);
          emit('saved');
        })
        .catch(() => {
          message.error($t('admin.plugin.messages.rollbackFailed'));
        });
    },
  });
}

const pluginType = computed(() =>
  derivePluginType(plugin.value?.manifest ?? null),
);

const isPaidPlugin = computed(() => {
  return plugin.value?.pricing_type === 'paid' || plugin.value?.tier === 'pro';
});

async function loadLicense(id: number) {
  licenseLoading.value = true;
  try {
    const res = (await getPluginLicenseApi(id)) as unknown as {
      data: PluginLicenseInfo;
    };
    licenseInfo.value = res?.data ?? (res as unknown as PluginLicenseInfo);
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

// ── Backups / 备份 ──
const backups = ref<PluginBackupInfo[]>([]);
const backupsLoading = ref(false);

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

defineExpose({ open });

function getPluginMetadataIcon(
  pluginName: string,
  icon: null | string | undefined,
) {
  return resolvePluginMetadataIcon(pluginName, icon, {
    endpoint: 'admin',
  });
}
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="plugin?.display_name || $t('admin.plugin.title')"
    :width="560"
    :destroy-on-close="true"
  >
    <template v-if="plugin">
      <!-- Header info / 头部信息 -->
      <div class="mb-6 flex items-start gap-4">
        <div
          class="flex size-14 shrink-0 items-center justify-center rounded-xl"
          :class="plugin.status === 'enabled' ? 'bg-primary/10' : 'bg-muted/30'"
        >
          <img
            v-if="
              getPluginMetadataIcon(plugin.name, plugin.icon).kind === 'image'
            "
            :src="getPluginMetadataIcon(plugin.name, plugin.icon).src"
            class="size-7 rounded"
            :alt="plugin.display_name"
          />
          <IconifyIcon
            v-else
            :icon="getPluginMetadataIcon(plugin.name, plugin.icon).icon"
            class="size-7"
            :class="
              plugin.status === 'enabled'
                ? 'text-primary'
                : 'text-muted-foreground'
            "
          />
        </div>
        <div class="flex-1">
          <div class="flex items-center gap-2">
            <span class="text-lg font-bold text-foreground">{{
              plugin.display_name
            }}</span>
            <Tag :color="getStatusColor(plugin.status)">
              {{ getStatusText(plugin.status) }}
            </Tag>
          </div>
          <div
            class="mt-1 flex items-center gap-2 text-xs text-muted-foreground"
          >
            <span class="font-mono">v{{ plugin.version }}</span>
            <span>·</span>
            <span>{{ plugin.author || 'NovusAI' }}</span>
            <span>·</span>
            <Tag
              :color="getTypeColor(pluginType)"
              :bordered="false"
              class="!text-[10px]"
            >
              {{ getTypeText(pluginType) }}
            </Tag>
            <Tag
              :color="getTierColor(plugin.tier)"
              :bordered="false"
              class="!text-[10px]"
            >
              {{ getTierText(plugin.tier) }}
            </Tag>
          </div>
          <p
            v-if="plugin.description"
            class="mt-2 text-sm text-muted-foreground"
          >
            {{ plugin.description }}
          </p>
        </div>
      </div>

      <!-- Action buttons / 操作按钮 -->
      <div class="mb-6 flex flex-wrap gap-2">
        <Button
          v-if="plugin.status === 'installed' || plugin.status === 'disabled'"
          type="primary"
          @click="onEnable"
        >
          <IconifyIcon icon="lucide:play" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.enable') }}
        </Button>
        <Button v-if="plugin.status === 'enabled'" @click="onDisable">
          <IconifyIcon icon="lucide:pause" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.disable') }}
        </Button>
        <Button @click="pluginActions.onInstallDependencies(plugin)">
          <IconifyIcon icon="lucide:package-plus" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.installDependencies') }}
        </Button>
        <Button
          :disabled="plugin.status === 'enabled'"
          @click="pluginActions.onUninstallDependencies(plugin)"
        >
          <IconifyIcon icon="lucide:package-minus" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.uninstallDependencies') }}
        </Button>
        <Button v-if="hasRecoveryAction('repair')" @click="onRepair">
          <IconifyIcon icon="lucide:wrench" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.repair') }}
        </Button>
        <Button
          v-if="hasRecoveryAction('force_cleanup')"
          danger
          @click="pluginActions.onForceCleanup(plugin)"
        >
          <IconifyIcon icon="lucide:eraser" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.forceCleanup') }}
        </Button>
        <Button v-if="hasScheduledTasks()" @click="onRefreshSchedules">
          <IconifyIcon icon="lucide:refresh-cw" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.refreshSchedules') }}
        </Button>
        <Button danger @click="onUninstall">
          <IconifyIcon icon="lucide:trash-2" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.uninstall') }}
        </Button>
      </div>

      <Alert
        v-if="recoveryState?.needs_attention && recoveryMeta"
        :message="$t('admin.plugin.recovery.title')"
        :type="recoveryMeta.alertType"
        show-icon
        class="mb-6"
      >
        <template #description>
          <div class="space-y-3">
            <p class="mb-0 text-sm">
              {{ $t(recoveryMeta.descriptionKey) }}
            </p>
            <div class="flex flex-wrap gap-2">
              <Button
                v-if="hasRecoveryAction('install_dependencies')"
                size="small"
                @click="pluginActions.onInstallDependencies(plugin)"
              >
                {{ $t('admin.plugin.action.installDependencies') }}
              </Button>
              <Button
                v-if="hasRecoveryAction('refresh_schedules')"
                size="small"
                @click="onRefreshSchedules"
              >
                {{ $t('admin.plugin.action.refreshSchedules') }}
              </Button>
              <Button
                v-if="hasRecoveryAction('repair')"
                size="small"
                @click="onRepair"
              >
                {{ $t('admin.plugin.action.repair') }}
              </Button>
              <Button
                v-if="hasRecoveryAction('force_cleanup')"
                size="small"
                danger
                @click="pluginActions.onForceCleanup(plugin)"
              >
                {{ $t('admin.plugin.action.forceCleanup') }}
              </Button>
            </div>
          </div>
        </template>
      </Alert>

      <!-- Basic info / 基本信息 -->
      <Descriptions :column="1" size="small" bordered class="mb-6">
        <DescriptionsItem :label="$t('admin.plugin.scope')">
          {{ getScopeText(plugin.scope) }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.plugin.installSource')">
          {{ plugin.install_source }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.plugin.installedAt')">
          {{ plugin.installed_at ? formatDate(plugin.installed_at) : '-' }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.plugin.enabledAt')">
          {{ plugin.enabled_at ? formatDate(plugin.enabled_at) : '-' }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('admin.plugin.errorCount')">
          <span
            :class="
              plugin.error_count > 0 ? 'font-medium text-destructive' : ''
            "
            >{{ plugin.error_count }}</span
          >
        </DescriptionsItem>
        <DescriptionsItem
          v-if="plugin.error_message"
          :label="$t('admin.plugin.health.lastError')"
        >
          <code class="text-xs text-destructive">{{
            plugin.error_message
          }}</code>
        </DescriptionsItem>
      </Descriptions>

      <!-- AI 功能：统一在「AI 功能分配」绑定 / AI features: bind only via Feature Assignment -->
      <Alert v-if="pluginHasAiFeatures" type="info" show-icon class="mb-6">
        <template #message>
          {{ $t('admin.plugin.aiAssignment.hintTitle') }}
        </template>
        <template #description>
          <div class="space-y-2">
            <p class="mb-0 text-sm">
              {{ $t('admin.plugin.aiAssignment.hintDesc') }}
            </p>
            <Button size="small" type="primary" @click="goToAgentAssignments">
              {{ $t('admin.plugin.aiAssignment.goButton') }}
            </Button>
          </div>
        </template>
      </Alert>

      <!-- README document (collapsible) / README 文档（可折叠） -->
      <div v-if="plugin.readme" class="mb-6">
        <Collapse :bordered="false" class="!bg-transparent">
          <CollapsePanel
            key="readme"
            class="!rounded-lg !border !border-border/60"
          >
            <template #header>
              <div class="flex items-center gap-1.5">
                <IconifyIcon
                  icon="lucide:book-open"
                  class="size-4 text-muted-foreground"
                />
                <span class="text-sm font-medium">{{
                  $t('admin.plugin.readme')
                }}</span>
              </div>
            </template>
            <div class="max-h-[400px] overflow-y-auto">
              <MarkdownRender :content="plugin.readme" />
            </div>
          </CollapsePanel>
        </Collapse>
      </div>

      <!-- Granted capabilities / 能力授权 -->
      <div v-if="plugin.granted_capabilities?.length" class="mb-6">
        <h4 class="mb-2 text-sm font-medium">
          {{ $t('admin.plugin.capabilitiesLabel') }}
        </h4>
        <div class="flex flex-wrap gap-1.5">
          <Tag
            v-for="cap in plugin.granted_capabilities"
            :key="cap"
            color="geekblue"
            :bordered="false"
            class="text-xs"
          >
            {{ cap }}
          </Tag>
        </div>
      </div>

      <div class="mb-6 rounded-lg border border-border/60 p-4">
        <div class="mb-2 flex items-center justify-between gap-2">
          <h4 class="text-sm font-medium">Lifecycle Audit</h4>
          <Button
            size="small"
            :loading="pluginAuditLoading"
            @click="loadPluginAudit(plugin.id)"
          >
            <IconifyIcon icon="lucide:refresh-cw" class="mr-1.5 size-3.5" />
            Refresh
          </Button>
        </div>
        <div v-if="pluginAuditLoading" class="text-xs text-muted-foreground">
          Loading lifecycle audit...
        </div>
        <template v-else-if="pluginAuditPayload">
          <div class="mb-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            <div
              class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
            >
              <div class="text-[11px] text-muted-foreground">Runtime Kind</div>
              <div class="mt-1 text-sm font-medium text-foreground">
                {{ String(pluginAuditPayload.runtime_kind || '-') }}
              </div>
            </div>
            <div
              class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
            >
              <div class="text-[11px] text-muted-foreground">
                Degraded Reason
              </div>
              <div class="mt-1 text-sm font-medium text-foreground">
                {{ String(pluginAuditPayload.degraded_reason || '-') }}
              </div>
            </div>
          </div>
          <pre
            class="max-h-56 overflow-auto rounded-lg border border-border/60 bg-accent/30 p-3 font-mono text-xs leading-5"
            >{{ prettyJson(pluginAuditPayload) }}</pre
          >
        </template>
        <div v-else class="text-xs text-muted-foreground">
          Lifecycle audit data is unavailable.
        </div>
      </div>

      <!-- License management / License 管理 -->
      <div v-if="isPaidPlugin" class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">
            {{ $t('admin.plugin.license.title') }}
          </h4>
          <Tag
            v-if="licenseInfo"
            :color="getLicenseStatusColor(licenseInfo.status)"
          >
            {{ getLicenseStatusText(licenseInfo.status) }}
          </Tag>
        </div>

        <div class="rounded-lg border border-border/60 p-4">
          <!-- Loading / 加载中 -->
          <div
            v-if="licenseLoading"
            class="text-center text-sm text-muted-foreground"
          >
            {{ $t('common.loading') }}...
          </div>

          <!-- Valid License details / 有效 License 详情 -->
          <template v-else-if="licenseInfo && licenseInfo.is_valid">
            <Descriptions :column="1" size="small" class="mb-3">
              <DescriptionsItem :label="$t('admin.plugin.license.type')">
                {{
                  licenseInfo.license_type === 'trial'
                    ? $t('admin.plugin.license.type_trial')
                    : $t('admin.plugin.license.type_paid')
                }}
              </DescriptionsItem>
              <DescriptionsItem
                v-if="licenseInfo.activated_at"
                :label="$t('admin.plugin.license.activatedAt')"
              >
                {{ formatDate(licenseInfo.activated_at) }}
              </DescriptionsItem>
              <DescriptionsItem
                v-if="licenseInfo.expires_at"
                :label="$t('admin.plugin.license.expiresAt')"
              >
                {{ formatDate(licenseInfo.expires_at) }}
              </DescriptionsItem>
              <DescriptionsItem
                v-if="licenseInfo.remaining_days != null"
                :label="$t('admin.plugin.license.remainingDays')"
              >
                <span
                  :class="
                    (licenseInfo.remaining_days ?? 0) <= 7
                      ? 'font-medium text-warning'
                      : ''
                  "
                >
                  {{ licenseInfo.remaining_days }}
                  {{ $t('admin.plugin.license.days') }}
                </span>
              </DescriptionsItem>
              <DescriptionsItem
                v-if="licenseInfo.trial_days_remaining != null"
                :label="$t('admin.plugin.license.remainingDays')"
              >
                <span
                  :class="
                    (licenseInfo.trial_days_remaining ?? 0) <= 3
                      ? 'font-medium text-warning'
                      : ''
                  "
                >
                  {{ licenseInfo.trial_days_remaining }}
                  {{ $t('admin.plugin.license.days') }}
                </span>
              </DescriptionsItem>
              <DescriptionsItem
                v-if="licenseInfo.buyer_email"
                :label="$t('admin.plugin.license.buyer')"
              >
                {{ licenseInfo.buyer_email }}
              </DescriptionsItem>
              <DescriptionsItem
                v-if="licenseInfo.license_key"
                :label="$t('admin.plugin.license.key')"
              >
                <code class="text-xs">{{ licenseInfo.license_key }}</code>
              </DescriptionsItem>
            </Descriptions>
            <Button danger size="small" @click="onRevokeLicense">
              <IconifyIcon icon="lucide:shield-off" class="mr-1 size-3.5" />
              {{ $t('admin.plugin.license.revoke') }}
            </Button>
          </template>

          <!-- No License / expired / 无 License / 过期 -->
          <template v-else>
            <p class="mb-3 text-sm text-muted-foreground">
              {{ licenseInfo?.message || $t('admin.plugin.license.noLicense') }}
            </p>

            <!-- Input License Key / 输入 License Key -->
            <div class="mb-3">
              <div class="mb-1.5 text-xs font-medium">
                {{ $t('admin.plugin.license.inputKey') }}
              </div>
              <div class="flex gap-2">
                <Input
                  v-model:value="licenseKeyInput"
                  :placeholder="$t('admin.plugin.license.keyPlaceholder')"
                  class="flex-1"
                  allow-clear
                />
                <Button
                  type="primary"
                  size="small"
                  :loading="licenseActivating"
                  :disabled="!licenseKeyInput.trim()"
                  @click="onActivateLicense"
                >
                  {{ $t('admin.plugin.license.activate') }}
                </Button>
              </div>
            </div>

            <!-- Start trial / 开始试用 -->
            <Button
              v-if="!licenseInfo || licenseInfo.status === 'none'"
              size="small"
              :loading="licenseActivating"
              @click="onActivateTrial"
            >
              <IconifyIcon icon="lucide:clock" class="mr-1 size-3.5" />
              {{ $t('admin.plugin.license.startTrial') }}
            </Button>
          </template>
        </div>
      </div>

      <!-- Tenant assignment (selected_tenants / admin_and_selected_tenants) / 企业分配 -->
      <div v-if="needsTenantAssignment" class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">
            {{ $t('admin.plugin.tenantAssignment') }}
          </h4>
          <Button size="small" @click="showTenantSelect = !showTenantSelect">
            <IconifyIcon icon="lucide:plus" class="mr-1 size-3.5" />
            {{ $t('admin.plugin.action.assignTenant') }}
          </Button>
        </div>

        <!-- Tenant selection / 企业选择 -->
        <div v-if="showTenantSelect" class="mb-3 flex items-center gap-2">
          <Select
            v-model:value="selectedTenantIds"
            mode="multiple"
            :placeholder="$t('admin.plugin.placeholder.selectTenants')"
            class="flex-1"
            :options="
              availableTenants.map((t) => ({ label: t.name, value: t.id }))
            "
            :loading="tenantLoading"
          />
          <Button
            type="primary"
            size="small"
            :disabled="selectedTenantIds.length === 0"
            @click="onAssignTenants"
          >
            {{ $t('common.confirm') }}
          </Button>
        </div>

        <!-- Assigned tenants list / 已分配企业列表 -->
        <div v-if="tenantAssignments.length > 0" class="flex flex-wrap gap-1.5">
          <Tag
            v-for="assignment in tenantAssignments"
            :key="assignment.id"
            closable
            color="cyan"
            :bordered="false"
            class="text-xs"
            @close="onUnassignTenant(assignment.tenant_id)"
          >
            {{ getTenantName(assignment.tenant_id) }}
          </Tag>
        </div>
        <div v-else class="text-xs text-muted-foreground">
          {{ $t('admin.plugin.tenantAssignmentEmpty') }}
        </div>
      </div>

      <!-- Config editing (only shown when config_schema or existing config present) / 配置编辑（仅在有 config_schema 或已有配置时显示） -->
      <div v-if="hasConfigToShow" class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">
            {{ $t('admin.plugin.tab.config') }}
          </h4>
          <Button
            type="primary"
            size="small"
            :loading="configSaving"
            @click="onSaveConfig"
          >
            {{ $t('admin.plugin.config.save') }}
          </Button>
        </div>

        <!-- Render dynamic form when config_schema exists / 有 config_schema 时渲染动态表单 -->
        <template v-if="configSchemaFields.length > 0">
          <Form
            layout="vertical"
            class="rounded-lg border border-border/60 p-4"
          >
            <FormItem
              v-for="field in configSchemaFields"
              :key="field.key"
              :help="field.description || undefined"
              class="!mb-3"
            >
              <template #label>
                <span>{{ field.title }}</span>
              </template>
              <!-- string with enum → Select -->
              <Select
                v-if="field.type === 'string' && field.enum"
                :value="
                  (configValues[field.key] as string) ??
                  (field.default as string)
                "
                @update:value="configValues[field.key] = $event"
              >
                <SelectOption v-for="opt in field.enum" :key="opt" :value="opt">
                  {{ opt }}
                </SelectOption>
              </Select>
              <ConfigImagePicker
                v-else-if="
                  field.type === 'image' ||
                  (field.type === 'string' && field.format === 'image')
                "
                :model-value="
                  (configValues[field.key] as string) ??
                  (field.default as string) ??
                  ''
                "
                @update:model-value="configValues[field.key] = $event"
              />
              <!-- string → Input -->
              <Input
                v-else-if="field.type === 'string'"
                :value="
                  (configValues[field.key] as string) ??
                  (field.default as string) ??
                  ''
                "
                @update:value="configValues[field.key] = $event"
              />
              <!-- integer / number → InputNumber -->
              <InputNumber
                v-else-if="field.type === 'integer' || field.type === 'number'"
                :value="
                  (configValues[field.key] as number) ??
                  (field.default as number) ??
                  0
                "
                :min="field.minimum"
                :max="field.maximum"
                class="!w-full"
                @update:value="configValues[field.key] = $event"
              />
              <!-- boolean → Switch -->
              <Switch
                v-else-if="field.type === 'boolean'"
                :checked="
                  (configValues[field.key] as boolean) ??
                  (field.default as boolean) ??
                  false
                "
                title=""
                @update:checked="configValues[field.key] = $event"
              />
            </FormItem>
          </Form>
        </template>

        <!-- Show JSON editor when no schema but has existing config / 无 schema 但有已存配置时显示 JSON 编辑器 -->
        <template v-else>
          <Input.TextArea
            v-model:value="configJson"
            :rows="6"
            class="font-mono !text-xs"
          />
        </template>
      </div>

      <!-- Backup records / 备份记录 -->
      <div class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">
            {{ $t('admin.plugin.backup.title') }}
          </h4>
          <Button
            size="small"
            :loading="backupsLoading"
            @click="plugin && loadBackups(plugin.id)"
          >
            <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-3.5" />
            {{ $t('common.refresh') }}
          </Button>
        </div>
        <div
          v-if="backups.length === 0"
          class="rounded-lg border border-border/40 p-4 text-center text-xs text-muted-foreground"
        >
          {{ $t('admin.plugin.backup.empty') }}
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="b in backups"
            :key="b.name"
            class="flex items-center justify-between rounded-lg border border-border/40 px-3 py-2"
          >
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="text-xs font-medium text-foreground"
                  >v{{ b.version }}</span
                >
                <Tag
                  v-if="b.has_data"
                  color="blue"
                  class="!m-0 !px-1 !text-[10px] !leading-4"
                >
                  {{ $t('admin.plugin.backup.tag.data') }}
                </Tag>
                <Tag
                  v-if="b.has_files"
                  color="cyan"
                  class="!m-0 !px-1 !text-[10px] !leading-4"
                >
                  {{ $t('admin.plugin.backup.tag.files') }}
                </Tag>
                <Tag
                  v-if="b.has_config"
                  color="purple"
                  class="!m-0 !px-1 !text-[10px] !leading-4"
                >
                  {{ $t('admin.plugin.backup.tag.config') }}
                </Tag>
              </div>
              <div class="mt-0.5 font-mono text-[10px] text-muted-foreground">
                {{ b.name }}
              </div>
            </div>
            <Button
              type="link"
              size="small"
              danger
              @click="onDeleteBackup(b.name)"
            >
              {{ $t('common.delete') }}
            </Button>
          </div>
        </div>
      </div>

      <!-- Version history / 版本历史 -->
      <div class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">
            {{ $t('admin.plugin.tab.versions') }}
          </h4>
          <Upload
            :show-upload-list="false"
            :custom-request="onUpgrade as unknown as undefined"
            accept=".zip"
          >
            <Button size="small" :loading="upgrading">
              <IconifyIcon
                icon="lucide:arrow-up-circle"
                class="mr-1 size-3.5"
              />
              {{ $t('admin.plugin.action.upgrade') }}
            </Button>
          </Upload>
        </div>
        <Table
          :data-source="versions"
          :pagination="false"
          size="small"
          row-key="id"
          :columns="[
            {
              title: $t('admin.plugin.versionLabel'),
              dataIndex: 'version',
              key: 'version',
            },
            {
              title: $t('admin.plugin.status'),
              dataIndex: 'status',
              key: 'status',
              width: 80,
            },
            { title: '', key: 'action', width: 80 },
          ]"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <Tag
                :color="record.status === 'active' ? 'success' : 'default'"
                class="text-xs"
              >
                {{
                  record.status === 'active'
                    ? $t('admin.plugin.version.current')
                    : $t('admin.plugin.version.archived')
                }}
              </Tag>
            </template>
            <template v-else-if="column.key === 'action'">
              <Button
                v-if="record.status !== 'active'"
                type="link"
                size="small"
                @click="onRollback(record.version)"
              >
                {{ $t('admin.plugin.action.rollback') }}
              </Button>
            </template>
          </template>
        </Table>
      </div>
    </template>
  </Drawer>
</template>
