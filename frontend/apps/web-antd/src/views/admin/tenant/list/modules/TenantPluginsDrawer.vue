<script setup lang="ts">
/**
 * 租户插件管理抽屉
 *
 * 展示租户已分配的插件列表，支持启用/禁用切换
 */
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Drawer,
  Empty,
  message,
  Switch,
  Tag,
} from 'ant-design-vue';

import { requestClient } from '#/utils/request';
import { $t } from '#/locales';

interface TenantPluginItem {
  id: number;
  plugin_id: number;
  plugin_name: string;
  display_name: string;
  plugin_type: string;
  scope: string;
  is_active: boolean;
  icon: string | null;
  version: string;
}

const visible = ref(false);
const loading = ref(false);
const tenantId = ref(0);
const tenantName = ref('');
const plugins = ref<TenantPluginItem[]>([]);
const togglingIds = ref<Set<number>>(new Set());

function getTypeColor(type: string): string {
  switch (type) {
    case 'adapter': return 'blue';
    case 'tool': return 'green';
    case 'hook': return 'orange';
    case 'api': return 'purple';
    case 'skill': return 'magenta';
    case 'composite': return 'cyan';
    default: return 'default';
  }
}

function getScopeTag(scope: string): { color: string; text: string } {
  switch (scope) {
    case 'platform_only': return { color: 'orange', text: $t('admin.plugin.scope_options.platform_only') };
    case 'all_tenants': return { color: 'blue', text: $t('admin.plugin.scope_options.all_tenants') };
    case 'assigned_tenants': return { color: 'purple', text: $t('admin.plugin.scope_options.assigned_tenants') };
    case 'global': return { color: 'green', text: $t('admin.plugin.scope_options.global') };
    default: return { color: 'default', text: scope };
  }
}

async function open(info: { tenantId: number; tenantName: string }) {
  tenantId.value = info.tenantId;
  tenantName.value = info.tenantName;
  visible.value = true;
  await loadPlugins();
}

async function loadPlugins() {
  loading.value = true;
  try {
    const data = await requestClient.get<TenantPluginItem[]>(
      `/admin/tenants/${tenantId.value}/plugins`,
    );
    plugins.value = data;
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}

async function onToggle(item: TenantPluginItem) {
  if (togglingIds.value.has(item.plugin_id)) return;
  togglingIds.value.add(item.plugin_id);
  try {
    const result = await requestClient.post<{ is_active: boolean }>(
      `/admin/tenants/${tenantId.value}/plugins/${item.plugin_id}/toggle`,
    );
    item.is_active = result.is_active;
    message.success(
      result.is_active
        ? $t('admin.plugin.messages.enableSuccess')
        : $t('admin.plugin.messages.disableSuccess'),
    );
  } catch {
    // handled by interceptor
  } finally {
    togglingIds.value.delete(item.plugin_id);
  }
}

defineExpose({ open });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="`${tenantName} — ${$t('admin.plugin.pageTitle')}`"
    width="480"
    :destroy-on-close="true"
  >
    <div v-if="loading" class="flex items-center justify-center py-12">
      <IconifyIcon icon="lucide:loader-2" class="size-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="plugins.length > 0">
      <div class="flex flex-col gap-3">
        <div
          v-for="item in plugins"
          :key="item.plugin_id"
          class="flex items-center justify-between rounded-lg border border-border p-3 transition-colors hover:border-primary/30"
        >
          <div class="flex items-center gap-3">
            <div
              class="flex size-9 shrink-0 items-center justify-center rounded-lg"
              :class="item.is_active ? 'bg-primary/10' : 'bg-muted'"
            >
              <IconifyIcon
                :icon="item.icon || 'lucide:plug'"
                class="size-4"
                :class="item.is_active ? 'text-primary' : 'text-muted-foreground'"
              />
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium text-foreground">
                  {{ item.display_name }}
                </span>
                <span class="text-xs text-muted-foreground">v{{ item.version }}</span>
              </div>
              <div class="mt-0.5 flex items-center gap-1">
                <Tag :color="getTypeColor(item.plugin_type)" class="!m-0" style="font-size: 10px; line-height: 14px; padding: 0 4px;">
                  {{ item.plugin_type }}
                </Tag>
                <Tag :color="getScopeTag(item.scope).color" class="!m-0" style="font-size: 10px; line-height: 14px; padding: 0 4px;">
                  {{ getScopeTag(item.scope).text }}
                </Tag>
              </div>
            </div>
          </div>
          <Switch
            :checked="item.is_active"
            :loading="togglingIds.has(item.plugin_id)"
            size="small"
            @change="() => onToggle(item)"
          />
        </div>
      </div>
    </template>

    <div v-else class="flex items-center justify-center py-12">
      <Empty
        :description="$t('admin.plugin.noPlugins')"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
      />
    </div>

    <template #footer>
      <div class="flex items-center justify-between">
        <span class="text-xs text-muted-foreground">
          {{ $t('admin.plugin.totalPlugins', { count: plugins.length }) }}
        </span>
        <Button @click="visible = false">
          {{ $t('common.close') }}
        </Button>
      </div>
    </template>
  </Drawer>
</template>
