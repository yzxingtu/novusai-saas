<script setup lang="ts">
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Collapse,
  CollapsePanel,
  Descriptions,
  DescriptionsItem,
  Form,
  FormItem,
  Input,
  InputNumber,
  Select,
  SelectOption,
  Switch,
  Table,
  Tag,
  Upload,
} from 'ant-design-vue';

import { ConfigImagePicker } from '#/components/business/config-image-picker';
import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { getScopeText } from '#/utils/scope-helpers';

import {
  getStatusColor,
  getStatusText,
  getTierColor,
  getTierText,
  getTypeColor,
  getTypeText,
} from '../../data';
import PluginLifecycleAuditPanel from './PluginLifecycleAuditPanel.vue';
import { usePluginConfigDrawerContext } from './context';

const {
  plugin,
  versions,
  configJson,
  configValues,
  configSaving,
  upgrading,
  pluginAuditLoading,
  pluginAuditPayload,
  tenantAssignments,
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
  getPluginMetadataIcon,
} = usePluginConfigDrawerContext();
</script>

<template>
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
        <div class="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
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
        <p v-if="plugin.description" class="mt-2 text-sm text-muted-foreground">
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
          :class="plugin.error_count > 0 ? 'font-medium text-destructive' : ''"
          >{{ plugin.error_count }}</span
        >
      </DescriptionsItem>
      <DescriptionsItem
        v-if="plugin.error_message"
        :label="$t('admin.plugin.health.lastError')"
      >
        <code class="text-xs text-destructive">{{ plugin.error_message }}</code>
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
              <span class="text-sm font-medium">
                {{ $t('admin.plugin.readme') }}
              </span>
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

    <PluginLifecycleAuditPanel
      :plugin-id="plugin.id"
      :loading="pluginAuditLoading"
      :payload="pluginAuditPayload"
      :on-refresh="loadPluginAudit"
      :pretty-json="prettyJson"
    />

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
            <!-- string with enum -> Select -->
            <Select
              v-if="field.type === 'string' && field.enum"
              :value="
                (configValues[field.key] as string) ?? (field.default as string)
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
            <!-- string -> Input -->
            <Input
              v-else-if="field.type === 'string'"
              :value="
                (configValues[field.key] as string) ??
                (field.default as string) ??
                ''
              "
              @update:value="configValues[field.key] = $event"
            />
            <!-- integer / number -> InputNumber -->
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
            <!-- boolean -> Switch -->
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
          :custom-request="handleUpgradeUploadRequest"
          accept=".zip"
        >
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
</template>
