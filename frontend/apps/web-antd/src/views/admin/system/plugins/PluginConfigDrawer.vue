<script setup lang="ts">
/**
 * 插件配置抽屉（平台管理端）
 *
 * 展示插件详情 + JSON Schema 配置表单（可编辑并保存默认配置）
 */
import type { PluginInfo } from '#/api/admin/plugins';

import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  message,
  Tag,
  Timeline,
  Typography,
} from 'ant-design-vue';

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

function open(row: PluginInfo) {
  plugin.value = row;
  configValues.value = { ...(row.default_config ?? {}) };
  editing.value = false;
  visible.value = true;
}

function close() {
  visible.value = false;
  plugin.value = null;
  editing.value = false;
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
