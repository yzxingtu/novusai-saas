<script setup lang="ts">
/**
 * 插件配置抽屉（平台管理端）
 *
 * 展示插件详情 + scope 管理 + 租户分配 + JSON Schema 配置表单
 */
import type { PluginInfo } from '#/api/admin/plugins';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  message,
  Modal,
  Select,
  Tag,
  Timeline,
  Typography,
} from 'ant-design-vue';

import { requestClient } from '#/utils/request';
import { updatePluginApi } from '#/api/admin/plugins';
import { SchemaForm } from '#/components';
import { $t } from '#/locales';

import { getPluginTypeColor, getPluginTypeText, getStatusColor, getStatusText } from './data';

const emit = defineEmits<{ saved: [] }>();

const visible = ref(false);
const editing = ref(false);
const saving = ref(false);
const plugin = ref<PluginInfo | null>(null);
const configValues = ref<Record<string, unknown>>({});
const schemaFormRef = ref<InstanceType<typeof SchemaForm>>();

const scopeOptions = computed(() => [
  { value: 'platform_only', label: $t('admin.plugin.scope_options.platform_only') },
  { value: 'all_tenants', label: $t('admin.plugin.scope_options.all_tenants') },
  { value: 'assigned_tenants', label: $t('admin.plugin.scope_options.assigned_tenants') },
  { value: 'global', label: $t('admin.plugin.scope_options.global') },
]);

const scopeSaving = ref(false);
const assignedTenants = ref<Array<{ tenant_id: number; tenant_name: string }>>([]);
const assignedLoading = ref(false);

function getScopeColor(scope: string | undefined): string {
  switch (scope) {
    case 'platform_only': return 'orange';
    case 'all_tenants': return 'blue';
    case 'assigned_tenants': return 'purple';
    case 'global': return 'green';
    default: return 'default';
  }
}

function getScopeText(scope: string | undefined): string {
  if (!scope) return '-';
  const opt = scopeOptions.value.find((o) => o.value === scope);
  return opt?.label ?? scope;
}

function open(row: PluginInfo) {
  plugin.value = row;
  configValues.value = { ...(row.default_config ?? {}) };
  editing.value = false;
  assignedTenants.value = [];
  visible.value = true;
  if (row.scope === 'assigned_tenants') {
    loadAssignedTenants();
  }
}

function close() {
  visible.value = false;
  plugin.value = null;
  editing.value = false;
}

async function loadAssignedTenants() {
  if (!plugin.value) return;
  assignedLoading.value = true;
  try {
    const data = await requestClient.get<Array<{ tenant_id: number; tenant_name: string }>>(
      `/admin/plugins/${plugin.value.id}/assigned-tenants`,
    );
    assignedTenants.value = data;
  } catch {
    // handled by interceptor
  } finally {
    assignedLoading.value = false;
  }
}

async function onScopeChange(newScope: string) {
  if (!plugin.value) return;
  const oldScope = plugin.value.scope;
  if (newScope === oldScope) return;

  Modal.confirm({
    title: $t('admin.plugin.messages.confirmScopeChange'),
    onOk: async () => {
      scopeSaving.value = true;
      try {
        const updated = await updatePluginApi(plugin.value!.id, { scope: newScope } as Record<string, unknown>);
        plugin.value = updated;
        message.success($t('common.saveSuccess'));
        emit('saved');
        if (newScope === 'assigned_tenants') {
          await loadAssignedTenants();
        }
      } catch {
        // handled by interceptor
      } finally {
        scopeSaving.value = false;
      }
    },
  });
}

async function onSave() {
  if (!plugin.value || !schemaFormRef.value) return;
  try {
    await schemaFormRef.value.validate();
    saving.value = true;
    const values = schemaFormRef.value.getValues();
    const updated = await updatePluginApi(plugin.value.id, { default_config: values });
    plugin.value = updated;
    configValues.value = { ...(updated.default_config ?? {}) };
    message.success($t('common.saveSuccess'));
    editing.value = false;
    emit('saved');
  } catch {
    // validation or API error handled by interceptor
  } finally {
    saving.value = false;
  }
}

function onCancelEdit() {
  if (plugin.value) {
    configValues.value = { ...(plugin.value.default_config ?? {}) };
  }
  editing.value = false;
}

defineExpose({ open, close });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="$t('admin.plugin.detail')"
    width="560"
    :destroy-on-close="true"
  >
    <template v-if="plugin">
      <!-- 头部信息 -->
      <div class="mb-6 flex items-center gap-3">
        <div class="flex size-12 items-center justify-center rounded-lg bg-primary/10">
          <IconifyIcon
            :icon="plugin.icon || 'lucide:plug'"
            class="size-6 text-primary"
          />
        </div>
        <div>
          <div class="text-lg font-semibold text-foreground">
            {{ plugin.display_name }}
          </div>
          <div class="text-sm text-muted-foreground">
            {{ plugin.name }} · v{{ plugin.version }}
          </div>
        </div>
      </div>

      <!-- 基本信息 -->
      <Descriptions :column="2" size="small" bordered class="mb-6">
        <Descriptions.Item :label="$t('admin.plugin.pluginType')">
          <Tag :color="getPluginTypeColor(plugin.plugin_type)">
            {{ getPluginTypeText(plugin.plugin_type) }}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.plugin.status')">
          <Tag :color="getStatusColor(plugin.status)">
            {{ getStatusText(plugin.status) }}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.plugin.scope')" :span="2">
          <div class="flex items-center gap-2">
            <Select
              v-access:code="['plugin:update']"
              :value="plugin.scope"
              :options="scopeOptions"
              :loading="scopeSaving"
              size="small"
              class="w-40"
              @change="(val: unknown) => onScopeChange(String(val))"
            />
            <Tag :color="getScopeColor(plugin.scope)" class="!m-0">
              {{ getScopeText(plugin.scope) }}
            </Tag>
          </div>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.plugin.author')" :span="2">
          {{ plugin.author || '-' }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.plugin.description')" :span="2">
          {{ plugin.description || '-' }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.plugin.entryPoint')" :span="2">
          <Typography.Text code>{{ plugin.entry_point }}</Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item
          v-if="plugin.homepage"
          :label="$t('admin.plugin.homepage')"
          :span="2"
        >
          <a :href="plugin.homepage" target="_blank" rel="noopener">
            {{ plugin.homepage }}
          </a>
        </Descriptions.Item>
        <Descriptions.Item
          v-if="plugin.required_permissions?.length"
          :label="$t('admin.plugin.permissions')"
          :span="2"
        >
          <Tag
            v-for="perm in plugin.required_permissions"
            :key="perm"
            class="mb-1"
          >
            {{ perm }}
          </Tag>
        </Descriptions.Item>
      </Descriptions>

      <!-- 已分配租户（scope=assigned_tenants 时显示） -->
      <template v-if="plugin.scope === 'assigned_tenants'">
        <div class="mb-3 flex items-center justify-between">
          <span class="text-base font-medium text-foreground">
            {{ $t('admin.plugin.assignedTenants') }}
          </span>
          <span class="text-xs text-muted-foreground">
            {{ $t('admin.plugin.assignedCount', { count: assignedTenants.length }) }}
          </span>
        </div>
        <div
          v-if="assignedLoading"
          class="mb-6 flex items-center justify-center py-4"
        >
          <IconifyIcon icon="lucide:loader-2" class="size-5 animate-spin text-muted-foreground" />
        </div>
        <div v-else-if="assignedTenants.length > 0" class="mb-6">
          <div class="flex flex-wrap gap-2">
            <Tag
              v-for="t in assignedTenants"
              :key="t.tenant_id"
              color="purple"
            >
              {{ t.tenant_name || `#${t.tenant_id}` }}
            </Tag>
          </div>
        </div>
        <div v-else class="mb-6 text-center text-sm text-muted-foreground">
          {{ $t('admin.plugin.noAssignedTenants') }}
        </div>
      </template>

      <!-- 市场信息 -->
      <template
        v-if="plugin.category || plugin.tags?.length || plugin.source_url || plugin.license"
      >
        <div class="mb-3 text-base font-medium text-foreground">
          {{ $t('admin.plugin.marketplace') }}
        </div>
        <Descriptions :column="2" size="small" bordered class="mb-6">
          <Descriptions.Item
            v-if="plugin.category"
            :label="$t('admin.plugin.category')"
          >
            <Tag>{{ plugin.category }}</Tag>
          </Descriptions.Item>
          <Descriptions.Item
            v-if="plugin.license"
            :label="$t('admin.plugin.license')"
          >
            {{ plugin.license }}
          </Descriptions.Item>
          <Descriptions.Item
            v-if="plugin.tags?.length"
            :label="$t('admin.plugin.tags')"
            :span="2"
          >
            <Tag v-for="tag in plugin.tags" :key="tag" class="mb-1">
              {{ tag }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item
            v-if="plugin.source_url"
            :label="$t('admin.plugin.sourceUrl')"
            :span="2"
          >
            <a :href="plugin.source_url" target="_blank" rel="noopener">
              {{ plugin.source_url }}
            </a>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.plugin.downloadsCount')">
            {{ plugin.downloads_count ?? 0 }}
          </Descriptions.Item>
          <Descriptions.Item
            v-if="plugin.rating != null"
            :label="$t('admin.plugin.rating')"
          >
            {{ plugin.rating.toFixed(1) }} / 5.0
          </Descriptions.Item>
        </Descriptions>
      </template>

      <!-- 版本历史 -->
      <template
        v-if="plugin.version_history && plugin.version_history.length > 0"
      >
        <div class="mb-3 text-base font-medium text-foreground">
          {{ $t('admin.plugin.versionHistory') }}
        </div>
        <Timeline class="mb-6">
          <Timeline.Item
            v-for="(entry, idx) in [...plugin.version_history].reverse()"
            :key="idx"
            :color="idx === 0 ? 'green' : 'gray'"
          >
            <div class="text-sm">
              <span class="font-medium">
                v{{ entry.from }} → v{{ entry.to }}
              </span>
              <span
                v-if="entry.upgraded_at"
                class="ml-2 text-xs text-muted-foreground"
              >
                {{ new Date(entry.upgraded_at as string).toLocaleString() }}
              </span>
            </div>
          </Timeline.Item>
        </Timeline>
      </template>

      <!-- 配置表单（如果有 config_schema） -->
      <template v-if="plugin.config_schema?.properties">
        <div class="mb-3 flex items-center justify-between">
          <span class="text-base font-medium text-foreground">
            {{ $t('admin.plugin.configure') }}
          </span>
          <Button
            v-if="!editing"
            v-access:code="['plugin:update']"
            type="link"
            size="small"
            @click="editing = true"
          >
            <IconifyIcon icon="lucide:pencil" class="mr-1 size-3.5" />
            {{ $t('common.edit') }}
          </Button>
        </div>
        <SchemaForm
          ref="schemaFormRef"
          :schema="plugin.config_schema"
          v-model="configValues"
          :disabled="!editing"
        />
        <div v-if="editing" class="mt-4 flex justify-end gap-2">
          <Button @click="onCancelEdit">
            {{ $t('common.cancel') }}
          </Button>
          <Button type="primary" :loading="saving" @click="onSave">
            {{ $t('common.save') }}
          </Button>
        </div>
      </template>
      <template v-else-if="!plugin.version_history?.length">
        <Empty
          :description="$t('common.noData')"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
        />
      </template>
    </template>
  </Drawer>
</template>
