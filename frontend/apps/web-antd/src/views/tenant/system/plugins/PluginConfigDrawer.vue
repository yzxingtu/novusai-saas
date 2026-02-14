<script setup lang="ts">
/**
 * 插件配置抽屉（租户端）
 *
 * 展示插件详情 + JSON Schema 配置表单（可编辑并保存）
 */
import type { AvailablePluginInfo } from '#/api/tenant/plugins';

import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  message,
  Tag,
} from 'ant-design-vue';

import { updateTenantPluginConfigApi } from '#/api/tenant/plugins';
import { SchemaForm } from '#/components';
import { $t } from '#/locales';

import { getPluginTypeColor, getPluginTypeText } from './data';

const emit = defineEmits<{ saved: [] }>();

const visible = ref(false);
const saving = ref(false);
const plugin = ref<AvailablePluginInfo | null>(null);
const configValues = ref<Record<string, unknown>>({});
const schemaFormRef = ref<InstanceType<typeof SchemaForm>>();

function open(row: AvailablePluginInfo, currentConfig?: Record<string, unknown> | null) {
  plugin.value = row;
  configValues.value = { ...(currentConfig ?? row.default_config ?? {}) };
  visible.value = true;
}

function close() {
  visible.value = false;
  plugin.value = null;
}

async function onSave() {
  if (!plugin.value || !schemaFormRef.value) return;
  try {
    await schemaFormRef.value.validate();
    saving.value = true;
    const values = schemaFormRef.value.getValues();
    await updateTenantPluginConfigApi(plugin.value.id, { config: values });
    message.success($t('tenant.plugin.messages.configureSuccess'));
    emit('saved');
    close();
  } catch {
    // validation or API error handled by interceptor
  } finally {
    saving.value = false;
  }
}

defineExpose({ open, close });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="$t('tenant.plugin.configure')"
    width="520"
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
          <div class="flex items-center gap-2 text-sm text-muted-foreground">
            <span>v{{ plugin.version }}</span>
            <Tag :color="getPluginTypeColor(plugin.plugin_type)" size="small">
              {{ getPluginTypeText(plugin.plugin_type) }}
            </Tag>
          </div>
        </div>
      </div>

      <!-- 描述 -->
      <Descriptions v-if="plugin.description" :column="1" size="small" class="mb-4">
        <Descriptions.Item :label="$t('tenant.plugin.description')">
          {{ plugin.description }}
        </Descriptions.Item>
      </Descriptions>

      <!-- 配置表单 -->
      <template v-if="plugin.config_schema?.properties">
        <div class="mb-3 text-base font-medium text-foreground">
          {{ $t('tenant.plugin.configure') }}
        </div>
        <SchemaForm
          ref="schemaFormRef"
          :schema="plugin.config_schema"
          v-model="configValues"
        />
        <div class="mt-4 flex justify-end">
          <Button
            type="primary"
            :loading="saving"
            @click="onSave"
          >
            {{ $t('common.save') }}
          </Button>
        </div>
      </template>
      <Empty
        v-else
        :description="$t('common.noData')"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
      />
    </template>
  </Drawer>
</template>
