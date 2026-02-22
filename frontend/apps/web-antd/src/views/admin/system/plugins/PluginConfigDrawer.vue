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
import { toAvatarDisplayUrl } from '#/utils/image';
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

// README 文档
const readmeContent = ref('');
const readmeLoading = ref(false);
const readmeVisible = ref(false);

/** HTML 实体转义（防 XSS） */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** 简易 Markdown → HTML 渲染（无外部依赖，XSS 安全） */
function renderMarkdown(md: string): string {
  // 先提取代码块/行内代码（防止内部内容被二次解析）
  const codeBlocks: string[] = [];
  let safe = md.replace(/```[\s\S]*?```/g, (m) => {
    const content = m.replace(/^```\w*\n?/, '').replace(/\n?```$/, '');
    codeBlocks.push(`<pre class="bg-muted rounded p-2 text-xs mb-3 overflow-x-auto"><code>${escapeHtml(content)}</code></pre>`);
    return `\x00CB${codeBlocks.length - 1}\x00`;
  });
  const inlineCodes: string[] = [];
  safe = safe.replace(/`([^`]+)`/g, (_, code) => {
    inlineCodes.push(`<code>${escapeHtml(code as string)}</code>`);
    return `\x00IC${inlineCodes.length - 1}\x00`;
  });

  // 转义剩余 HTML
  safe = escapeHtml(safe);

  // Markdown → HTML
  safe = safe
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\- (.+)$/gm, '<li>$1</li>')
    .replace(/^\| (.+) \|$/gm, (_, row: string) => {
      const cells = row.split(' | ').map((c: string) => `<td class="px-2 py-1 border border-border">${c.trim()}</td>`).join('');
      return `<tr>${cells}</tr>`;
    })
    .replace(/(<tr>.*<\/tr>\n?)+/g, (match) => `<table class="w-full border-collapse text-xs mb-3">${match}</table>`)
    .replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul class="list-disc pl-5 mb-3">${match}</ul>`)
    .replace(/\n\n/g, '</p><p class="mb-2">')
    .replace(/^(?!<)/, '<p class="mb-2">')
    .replace(/$/, '</p>');

  // 还原代码块和行内代码
  safe = safe.replace(/\x00CB(\d+)\x00/g, (_, i) => codeBlocks[Number(i)] ?? '');
  safe = safe.replace(/\x00IC(\d+)\x00/g, (_, i) => inlineCodes[Number(i)] ?? '');

  return safe;
}

const scopeOptions = computed(() => [
  { value: 'platform_only', label: $t('admin.plugin.scope_options.platform_only') },
  { value: 'all_tenants', label: $t('admin.plugin.scope_options.all_tenants') },
  { value: 'assigned_tenants', label: $t('admin.plugin.scope_options.assigned_tenants') },
  { value: 'tenant_only', label: $t('admin.plugin.scope_options.tenant_only') },
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
    case 'tenant_only': return 'cyan';
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
  readmeVisible.value = false;
  readmeContent.value = '';
  assignedTenants.value = [];
  visible.value = true;
  if (row.scope === 'assigned_tenants') {
    loadAssignedTenants();
  }
}

async function loadReadme() {
  if (!plugin.value) return;
  readmeLoading.value = true;
  try {
    const data = await requestClient.get<{ has_readme: boolean; content: string }>(
      `/admin/plugins/${plugin.value.id}/readme`,
    );
    readmeContent.value = data.content || '';
    readmeVisible.value = true;
  } catch {
    readmeContent.value = '';
    readmeVisible.value = true;
  } finally {
    readmeLoading.value = false;
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
        // 只更新变化的字段，避免替换整个对象引发递归渲染
        if (plugin.value) {
          plugin.value.scope = updated.scope;
        }
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
          <img
            v-if="plugin.icon && (/^\d+$/.test(plugin.icon) || plugin.icon.startsWith('http') || plugin.icon.startsWith('data:') || plugin.icon.startsWith('/'))"
            :src="/^\d+$/.test(plugin.icon) ? toAvatarDisplayUrl(plugin.icon) : plugin.icon"
            :alt="plugin.display_name"
            class="size-8 rounded object-contain"
          />
          <IconifyIcon
            v-else
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

      <!-- 已分配租户（scope=assigned_tenants 或 tenant_only 时显示） -->
      <template v-if="plugin.scope === 'assigned_tenants' || plugin.scope === 'tenant_only'">
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

      <!-- 插件文档 -->
      <div class="mb-6">
        <Button
          type="default"
          block
          :loading="readmeLoading"
          @click="readmeVisible ? (readmeVisible = false) : loadReadme()"
        >
          <IconifyIcon :icon="readmeVisible ? 'lucide:chevron-up' : 'lucide:book-open'" class="mr-1.5 size-4" />
          {{ readmeVisible ? $t('admin.plugin.hideReadme') : $t('admin.plugin.viewReadme') }}
        </Button>
        <div
          v-if="readmeVisible"
          class="mt-3 max-h-[400px] overflow-auto rounded-lg border border-border bg-muted/30 p-4"
        >
          <div v-if="readmeContent" class="prose prose-sm max-w-none dark:prose-invert" v-html="renderMarkdown(readmeContent)" />
          <Empty v-else :description="$t('admin.plugin.noReadme')" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
        </div>
      </div>

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
