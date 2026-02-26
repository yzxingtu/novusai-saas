<script setup lang="ts">
/**
 * 插件配置抽屉（参考旧版 PluginConfigDrawer）
 *
 * 展示插件详情 + 配置编辑 + 版本历史 + 健康状态
 */
import type { PluginInfo, PluginLicenseInfo, PluginVersionInfo } from '#/api/admin/plugin';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
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
  disablePluginApi,
  enablePluginApi,
  getPluginDetailApi,
  getPluginLicenseApi,
  getPluginTenantsApi,
  getPluginVersionsApi,
  repairPluginApi,
  revokePluginLicenseApi,
  rollbackPluginApi,
  unassignPluginTenantApi,
  uninstallPluginApi,
  updatePluginConfigApi,
  upgradePluginApi,
} from '#/api/admin/plugin';
import type { PluginTenantAssignmentInfo } from '#/api/admin/plugin';
import { getTenantListApi } from '#/api/admin/tenant';
import { scopeNeedsAssignment } from '#/components/business/scope-select';
import { $t } from '#/locales';
import { refreshPluginSlots } from '#/composables/use-plugin-frontend-init';
import { formatDate } from '#/utils/common';

import {
  derivePluginType,
  getStatusColor,
  getStatusText,
  getScopeText,
  getTierColor,
  getTierText,
  getTypeColor,
  getTypeText,
} from '../data';

const emit = defineEmits<{ saved: [] }>();

const visible = ref(false);
const plugin = ref<PluginInfo | null>(null);
const loading = ref(false);
const versions = ref<PluginVersionInfo[]>([]);
const configJson = ref('');
const configValues = ref<Record<string, unknown>>({});
const configSaving = ref(false);
const upgrading = ref(false);

const tenantAssignments = ref<PluginTenantAssignmentInfo[]>([]);
const allTenants = ref<Array<{ id: number; name: string }>>([]);
const tenantLoading = ref(false);
const showTenantSelect = ref(false);
const selectedTenantIds = ref<number[]>([]);

// License
const licenseInfo = ref<PluginLicenseInfo | null>(null);
const licenseLoading = ref(false);
const licenseKeyInput = ref('');
const licenseActivating = ref(false);

const needsTenantAssignment = computed(() => {
  if (!plugin.value) return false;
  const scope = plugin.value.scope || (plugin.value.manifest as Record<string, unknown>)?.scope;
  return scopeNeedsAssignment(String(scope || ''));
});

const assignedTenantIds = computed(() => new Set(tenantAssignments.value.map(a => a.tenant_id)));

const availableTenants = computed(() =>
  allTenants.value.filter(t => !assignedTenantIds.value.has(t.id)),
);

interface ConfigField {
  key: string;
  type: string;
  title: string;
  description: string;
  default: unknown;
  enum?: string[];
  minimum?: number;
  maximum?: number;
}

const configSchemaFields = computed<ConfigField[]>(() => {
  const manifest = plugin.value?.manifest as Record<string, unknown> | undefined;
  const schema = manifest?.config_schema as Record<string, unknown> | undefined;
  if (!schema || !schema.properties) return [];

  const props = schema.properties as Record<string, Record<string, unknown>>;
  const locale = 'zh-CN';

  return Object.entries(props).map(([key, prop]) => {
    const titleRaw = prop.title;
    const descRaw = prop.description;
    const title = typeof titleRaw === 'object' && titleRaw !== null
      ? (titleRaw as Record<string, string>)[locale] || (titleRaw as Record<string, string>).en || key
      : String(titleRaw || key);
    const description = typeof descRaw === 'object' && descRaw !== null
      ? (descRaw as Record<string, string>)[locale] || (descRaw as Record<string, string>).en || ''
      : String(descRaw || '');

    return {
      key,
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

async function open(row: PluginInfo) {
  plugin.value = row;
  visible.value = true;
  configJson.value = JSON.stringify(row.config || {}, null, 2);
  configValues.value = { ...(row.config || {}) };
  loadVersions(row.id);
  loadTenantAssignments(row.id);
  loadLicense(row.id);
}

async function reload() {
  if (!plugin.value) return;
  loading.value = true;
  try {
    const res = await getPluginDetailApi(plugin.value.id) as unknown as { data: PluginInfo };
    plugin.value = res?.data ?? (res as unknown as PluginInfo);
    configJson.value = JSON.stringify(plugin.value.config || {}, null, 2);
  } catch {
    //
  } finally {
    loading.value = false;
  }
}

async function loadVersions(id: number) {
  try {
    const res = await getPluginVersionsApi(id) as unknown as { data: PluginVersionInfo[] };
    versions.value = res?.data ?? (res as unknown as PluginVersionInfo[]) ?? [];
  } catch {
    versions.value = [];
  }
}

async function loadTenantAssignments(id: number) {
  if (!needsTenantAssignment.value) return;
  tenantLoading.value = true;
  try {
    const res = await getPluginTenantsApi(id) as unknown as PluginTenantAssignmentInfo[];
    tenantAssignments.value = Array.isArray(res) ? res : (res as unknown as { data: PluginTenantAssignmentInfo[] })?.data ?? [];
    const tenantRes = await getTenantListApi({ 'page[size]': 200 });
    allTenants.value = (tenantRes?.items ?? []).map((t: { id: number; name?: string; display_name?: string }) => ({
      id: t.id,
      name: t.name || t.display_name || `Tenant #${t.id}`,
    }));
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
    message.success($t('admin.plugin.messages.assignSuccess') || 'Tenants assigned');
    selectedTenantIds.value = [];
    showTenantSelect.value = false;
    await loadTenantAssignments(plugin.value.id);
  } catch {
    message.error('Failed to assign tenants');
  }
}

async function onUnassignTenant(tenantId: number) {
  if (!plugin.value) return;
  try {
    await unassignPluginTenantApi(plugin.value.id, tenantId);
    await loadTenantAssignments(plugin.value.id);
  } catch {
    message.error('Failed to unassign tenant');
  }
}

function getTenantName(tenantId: number): string {
  return allTenants.value.find(t => t.id === tenantId)?.name ?? `Tenant #${tenantId}`;
}

async function onEnable() {
  if (!plugin.value) return;
  await enablePluginApi(plugin.value.id);
  message.success($t('admin.plugin.messages.enableSuccess'));
  await reload();
  emit('saved');
  await refreshPluginSlots('/admin');
}

function onDisable() {
  if (!plugin.value) return;
  Modal.confirm({
    title: $t('admin.plugin.confirm.disable', { name: plugin.value.display_name }),
    async onOk() {
      await disablePluginApi(plugin.value!.id);
      message.success($t('admin.plugin.messages.disableSuccess'));
      await reload();
      emit('saved');
      await refreshPluginSlots('/admin');
    },
  });
}

function onUninstall() {
  if (!plugin.value) return;
  Modal.confirm({
    title: $t('admin.plugin.confirm.uninstall', { name: plugin.value.display_name }),
    okType: 'danger',
    async onOk() {
      await uninstallPluginApi(plugin.value!.id);
      message.success($t('admin.plugin.messages.uninstallSuccess'));
      visible.value = false;
      emit('saved');
    },
  });
}

async function onRepair() {
  if (!plugin.value) return;
  await repairPluginApi(plugin.value.id);
  message.success($t('admin.plugin.messages.repairSuccess'));
  await reload();
  emit('saved');
}

async function onSaveConfig() {
  if (!plugin.value) return;
  configSaving.value = true;
  try {
    let data: Record<string, unknown>;
    if (configSchemaFields.value.length > 0) {
      data = { ...configValues.value };
    } else {
      data = JSON.parse(configJson.value);
    }
    await updatePluginConfigApi(plugin.value.id, data);
    message.success($t('admin.plugin.config.saveSuccess'));
    await reload();
    emit('saved');
  } catch (err) {
    if (err instanceof SyntaxError) {
      message.error('Invalid JSON');
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
  Modal.confirm({
    title: `${$t('admin.plugin.action.rollback')} → v${version}`,
    okType: 'danger',
    async onOk() {
      await rollbackPluginApi(plugin.value!.id, version);
      message.success($t('admin.plugin.messages.rollbackSuccess'));
      await reload();
      await loadVersions(plugin.value!.id);
      emit('saved');
    },
  });
}

const pluginType = computed(() => derivePluginType(plugin.value?.manifest ?? null));

const isPaidPlugin = computed(() => {
  return plugin.value?.pricing_type === 'paid' || plugin.value?.tier === 'pro';
});

async function loadLicense(id: number) {
  licenseLoading.value = true;
  try {
    const res = await getPluginLicenseApi(id) as unknown as { data: PluginLicenseInfo };
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
    await activatePluginLicenseApi(plugin.value.id, licenseKeyInput.value.trim());
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
  if (!plugin.value) return;
  Modal.confirm({
    title: $t('admin.plugin.license.revokeConfirm'),
    okType: 'danger',
    async onOk() {
      await revokePluginLicenseApi(plugin.value!.id);
      message.success($t('admin.plugin.license.revokeSuccess'));
      await loadLicense(plugin.value!.id);
    },
  });
}

function getLicenseStatusColor(status: string): string {
  switch (status) {
    case 'active': return 'success';
    case 'trial': return 'processing';
    case 'expired': return 'error';
    default: return 'default';
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

defineExpose({ open });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="plugin?.display_name || $t('admin.plugin.title')"
    :width="560"
    :destroy-on-close="true"
  >
    <template v-if="plugin">
      <!-- 头部信息 -->
      <div class="mb-6 flex items-start gap-4">
        <div
          class="flex size-14 shrink-0 items-center justify-center rounded-xl"
          :class="plugin.status === 'enabled' ? 'bg-primary/10' : 'bg-muted/30'"
        >
          <img
            v-if="plugin.icon && /\.(png|jpg|jpeg|svg|webp)$/i.test(plugin.icon)"
            :src="plugin.icon.startsWith('http') || plugin.icon.startsWith('/') ? plugin.icon : `/plugin-assets/${plugin.name}/${plugin.icon}`"
            class="size-7 rounded"
            :alt="plugin.display_name"
          />
          <IconifyIcon
            v-else
            :icon="plugin.icon && plugin.icon.includes(':') ? plugin.icon : 'lucide:plug'"
            class="size-7"
            :class="plugin.status === 'enabled' ? 'text-primary' : 'text-muted-foreground'"
          />
        </div>
        <div class="flex-1">
          <div class="flex items-center gap-2">
            <span class="text-lg font-bold text-foreground">{{ plugin.display_name }}</span>
            <Tag :color="getStatusColor(plugin.status)">{{ getStatusText(plugin.status) }}</Tag>
          </div>
          <div class="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
            <span class="font-mono">v{{ plugin.version }}</span>
            <span>·</span>
            <span>{{ plugin.author || 'NovusAI' }}</span>
            <span>·</span>
            <Tag :color="getTypeColor(pluginType)" :bordered="false" class="!text-[10px]">{{ getTypeText(pluginType) }}</Tag>
            <Tag :color="getTierColor(plugin.tier)" :bordered="false" class="!text-[10px]">{{ getTierText(plugin.tier) }}</Tag>
          </div>
          <p v-if="plugin.description" class="mt-2 text-sm text-muted-foreground">{{ plugin.description }}</p>
        </div>
      </div>

      <!-- 操作按钮 -->
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
        <Button v-if="plugin.status === 'error'" @click="onRepair">
          <IconifyIcon icon="lucide:wrench" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.repair') }}
        </Button>
        <Button danger @click="onUninstall">
          <IconifyIcon icon="lucide:trash-2" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.action.uninstall') }}
        </Button>
      </div>

      <!-- 基本信息 -->
      <Descriptions :column="1" size="small" bordered class="mb-6">
        <DescriptionsItem :label="$t('admin.plugin.scope')">{{ getScopeText(plugin.scope) }}</DescriptionsItem>
        <DescriptionsItem :label="$t('admin.plugin.installSource')">{{ plugin.install_source }}</DescriptionsItem>
        <DescriptionsItem :label="$t('admin.plugin.installedAt')">{{ plugin.installed_at ? formatDate(plugin.installed_at) : '-' }}</DescriptionsItem>
        <DescriptionsItem :label="$t('admin.plugin.enabledAt')">{{ plugin.enabled_at ? formatDate(plugin.enabled_at) : '-' }}</DescriptionsItem>
        <DescriptionsItem :label="$t('admin.plugin.errorCount')">
          <span :class="plugin.error_count > 0 ? 'font-medium text-destructive' : ''">{{ plugin.error_count }}</span>
        </DescriptionsItem>
        <DescriptionsItem v-if="plugin.error_message" :label="$t('admin.plugin.health.lastError')">
          <code class="text-xs text-destructive">{{ plugin.error_message }}</code>
        </DescriptionsItem>
      </Descriptions>

      <!-- 能力授权 -->
      <div v-if="plugin.granted_capabilities?.length" class="mb-6">
        <h4 class="mb-2 text-sm font-medium">{{ $t('admin.plugin.capabilitiesLabel') }}</h4>
        <div class="flex flex-wrap gap-1.5">
          <Tag v-for="cap in plugin.granted_capabilities" :key="cap" color="geekblue" :bordered="false" class="text-xs">
            {{ cap }}
          </Tag>
        </div>
      </div>

      <!-- License 管理 -->
      <div v-if="isPaidPlugin" class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">{{ $t('admin.plugin.license.title') }}</h4>
          <Tag v-if="licenseInfo" :color="getLicenseStatusColor(licenseInfo.status)">
            {{ getLicenseStatusText(licenseInfo.status) }}
          </Tag>
        </div>

        <div class="rounded-lg border border-border/60 p-4">
          <!-- 加载中 -->
          <div v-if="licenseLoading" class="text-center text-sm text-muted-foreground">
            {{ $t('common.loading') }}...
          </div>

          <!-- 有效 License 详情 -->
          <template v-else-if="licenseInfo && licenseInfo.is_valid">
            <Descriptions :column="1" size="small" class="mb-3">
              <DescriptionsItem :label="$t('admin.plugin.license.type')">
                {{ licenseInfo.license_type === 'trial' ? $t('admin.plugin.license.type_trial') : $t('admin.plugin.license.type_paid') }}
              </DescriptionsItem>
              <DescriptionsItem v-if="licenseInfo.activated_at" :label="$t('admin.plugin.license.activatedAt')">
                {{ formatDate(licenseInfo.activated_at) }}
              </DescriptionsItem>
              <DescriptionsItem v-if="licenseInfo.expires_at" :label="$t('admin.plugin.license.expiresAt')">
                {{ formatDate(licenseInfo.expires_at) }}
              </DescriptionsItem>
              <DescriptionsItem v-if="licenseInfo.remaining_days != null" :label="$t('admin.plugin.license.remainingDays')">
                <span :class="(licenseInfo.remaining_days ?? 0) <= 7 ? 'font-medium text-warning' : ''">
                  {{ licenseInfo.remaining_days }} {{ $t('admin.plugin.license.days') }}
                </span>
              </DescriptionsItem>
              <DescriptionsItem v-if="licenseInfo.trial_days_remaining != null" :label="$t('admin.plugin.license.remainingDays')">
                <span :class="(licenseInfo.trial_days_remaining ?? 0) <= 3 ? 'font-medium text-warning' : ''">
                  {{ licenseInfo.trial_days_remaining }} {{ $t('admin.plugin.license.days') }}
                </span>
              </DescriptionsItem>
              <DescriptionsItem v-if="licenseInfo.buyer_email" :label="$t('admin.plugin.license.buyer')">
                {{ licenseInfo.buyer_email }}
              </DescriptionsItem>
              <DescriptionsItem v-if="licenseInfo.license_key" :label="$t('admin.plugin.license.key')">
                <code class="text-xs">{{ licenseInfo.license_key }}</code>
              </DescriptionsItem>
            </Descriptions>
            <Button danger size="small" @click="onRevokeLicense">
              <IconifyIcon icon="lucide:shield-off" class="mr-1 size-3.5" />
              {{ $t('admin.plugin.license.revoke') }}
            </Button>
          </template>

          <!-- 无 License / 过期 -->
          <template v-else>
            <p class="mb-3 text-sm text-muted-foreground">
              {{ licenseInfo?.message || $t('admin.plugin.license.noLicense') }}
            </p>

            <!-- 输入 License Key -->
            <div class="mb-3">
              <div class="mb-1.5 text-xs font-medium">{{ $t('admin.plugin.license.inputKey') }}</div>
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

            <!-- 开始试用 -->
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

      <!-- 租户分配（仅 assigned_tenants / admin_and_assigned 显示） -->
      <div v-if="needsTenantAssignment" class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">{{ $t('admin.plugin.tenantAssignment') }}</h4>
          <Button size="small" @click="showTenantSelect = !showTenantSelect">
            <IconifyIcon icon="lucide:plus" class="mr-1 size-3.5" />
            {{ $t('admin.plugin.action.assignTenant') }}
          </Button>
        </div>

        <!-- 租户选择 -->
        <div v-if="showTenantSelect" class="mb-3 flex items-center gap-2">
          <Select
            v-model:value="selectedTenantIds"
            mode="multiple"
            :placeholder="$t('admin.plugin.placeholder.selectTenants')"
            class="flex-1"
            :options="availableTenants.map(t => ({ label: t.name, value: t.id }))"
            :loading="tenantLoading"
          />
          <Button type="primary" size="small" :disabled="selectedTenantIds.length === 0" @click="onAssignTenants">
            {{ $t('common.confirm') }}
          </Button>
        </div>

        <!-- 已分配租户列表 -->
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

      <!-- 配置编辑 -->
      <div class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">{{ $t('admin.plugin.tab.config') }}</h4>
          <Button type="primary" size="small" :loading="configSaving" @click="onSaveConfig">
            {{ $t('admin.plugin.config.save') }}
          </Button>
        </div>

        <!-- 有 config_schema 时渲染动态表单 -->
        <template v-if="configSchemaFields.length > 0">
          <Form layout="vertical" class="rounded-lg border border-border/60 p-4">
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
                :value="(configValues[field.key] as string) ?? (field.default as string)"
                @update:value="configValues[field.key] = $event"
              >
                <SelectOption v-for="opt in field.enum" :key="opt" :value="opt">{{ opt }}</SelectOption>
              </Select>
              <!-- string → Input -->
              <Input
                v-else-if="field.type === 'string'"
                :value="(configValues[field.key] as string) ?? (field.default as string) ?? ''"
                @update:value="configValues[field.key] = $event"
              />
              <!-- integer / number → InputNumber -->
              <InputNumber
                v-else-if="field.type === 'integer' || field.type === 'number'"
                :value="(configValues[field.key] as number) ?? (field.default as number) ?? 0"
                :min="field.minimum"
                :max="field.maximum"
                class="!w-full"
                @update:value="configValues[field.key] = $event"
              />
              <!-- boolean → Switch -->
              <Switch
                v-else-if="field.type === 'boolean'"
                :checked="(configValues[field.key] as boolean) ?? (field.default as boolean) ?? false"
                :title="''"
                @update:checked="configValues[field.key] = $event"
              />
            </FormItem>
          </Form>
        </template>

        <!-- 无 schema 时显示 JSON 编辑器 -->
        <template v-else>
          <Input.TextArea v-model:value="configJson" :rows="6" class="font-mono !text-xs" />
        </template>
      </div>

      <!-- 版本历史 -->
      <div class="mb-6">
        <div class="mb-2 flex items-center justify-between">
          <h4 class="text-sm font-medium">{{ $t('admin.plugin.tab.versions') }}</h4>
          <Upload :show-upload-list="false" :custom-request="onUpgrade as unknown as undefined" accept=".zip">
            <Button size="small" :loading="upgrading">
              <IconifyIcon icon="lucide:arrow-up-circle" class="mr-1 size-3.5" />
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
            { title: $t('admin.plugin.versionLabel'), dataIndex: 'version', key: 'version' },
            { title: $t('admin.plugin.status'), dataIndex: 'status', key: 'status', width: 80 },
            { title: '', key: 'action', width: 80 },
          ]"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <Tag :color="record.status === 'active' ? 'success' : 'default'" class="text-xs">
                {{ record.status === 'active' ? $t('admin.plugin.version.current') : $t('admin.plugin.version.archived') }}
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
