<script lang="ts" setup>
/**
 * 租户插件管理页面 — 卡片式布局
 *
 * 展示平台已启用的插件列表，支持租户级启用/禁用 + 搜索/筛选
 */
import type { AvailablePluginInfo, TenantPluginInfo } from '#/api/tenant/plugins';

defineOptions({ name: 'TenantPluginList' });

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  Input,
  message,
  Modal,
  Segmented,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  disableTenantPluginApi,
  enableTenantPluginApi,
  getAvailablePluginsApi,
  getEnabledPluginsApi,
} from '#/api/tenant/plugins';
import { $t } from '#/locales';

import { getPluginTypeColor, getPluginTypeText } from './data';
import PluginConfigDrawer from './PluginConfigDrawer.vue';

const configDrawerRef = ref<InstanceType<typeof PluginConfigDrawer>>();
const loading = ref(false);
const availablePlugins = ref<AvailablePluginInfo[]>([]);
const enabledPluginIds = ref<Set<number>>(new Set());
const enabledMap = ref<Map<number, TenantPluginInfo>>(new Map());
const searchKeyword = ref('');
const filterStatus = ref('all');
const filterType = ref('all');

const statusFilters = computed(() => [
  { value: 'all', label: $t('tenant.plugin.filterAll') },
  { value: 'enabled', label: $t('tenant.plugin.filterEnabled') },
  { value: 'not_enabled', label: $t('tenant.plugin.filterNotEnabled') },
]);

const typeFilters = computed(() => {
  const types = new Set(availablePlugins.value.map((p) => p.plugin_type));
  const options = [
    { value: 'all', label: $t('tenant.plugin.filterAll') },
  ];
  for (const t of types) {
    options.push({ value: t, label: getPluginTypeText(t) });
  }
  return options;
});

const filteredPlugins = computed(() => {
  let result = availablePlugins.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter(
      (p) =>
        p.display_name.toLowerCase().includes(kw) ||
        p.name.toLowerCase().includes(kw) ||
        (p.description && p.description.toLowerCase().includes(kw)),
    );
  }
  if (filterType.value !== 'all') {
    result = result.filter((p) => p.plugin_type === filterType.value);
  }
  if (filterStatus.value === 'enabled') {
    result = result.filter((p) => isEnabled(p.id));
  } else if (filterStatus.value === 'not_enabled') {
    result = result.filter((p) => !isEnabled(p.id));
  }
  return result;
});

async function loadPlugins() {
  loading.value = true;
  try {
    const [availableRes, enabled] = await Promise.all([
      getAvailablePluginsApi({ 'page[size]': 200 }),
      getEnabledPluginsApi(),
    ]);
    availablePlugins.value = availableRes.items;
    enabledPluginIds.value = new Set(
      enabled.filter((e) => e.is_active).map((e) => e.plugin_id),
    );
    enabledMap.value = new Map(enabled.map((e) => [e.plugin_id, e]));
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}

function isEnabled(pluginId: number): boolean {
  return enabledPluginIds.value.has(pluginId);
}

function onConfigure(plugin: AvailablePluginInfo) {
  const tenantPlugin = enabledMap.value.get(plugin.id);
  configDrawerRef.value?.open(plugin, tenantPlugin?.config);
}

function onEnable(plugin: AvailablePluginInfo) {
  Modal.confirm({
    title: $t('tenant.plugin.messages.confirmEnable'),
    onOk: async () => {
      try {
        await enableTenantPluginApi({ plugin_id: plugin.id });
        message.success($t('tenant.plugin.messages.enableSuccess'));
        await loadPlugins();
      } catch {
        // handled by interceptor
      }
    },
  });
}

function onDisable(plugin: AvailablePluginInfo) {
  Modal.confirm({
    title: $t('tenant.plugin.messages.confirmDisable'),
    onOk: async () => {
      try {
        await disableTenantPluginApi(plugin.id);
        message.success($t('tenant.plugin.messages.disableSuccess'));
        await loadPlugins();
      } catch {
        // handled by interceptor
      }
    },
  });
}

onMounted(loadPlugins);
</script>

<template>
  <Page
    auto-content-height
    :title="$t('tenant.plugin.pageTitle')"
    :description="$t('tenant.plugin.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 搜索 + 筛选 -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-1 flex-wrap items-center gap-3">
        <Input.Search
          v-model:value="searchKeyword"
          :placeholder="$t('tenant.plugin.searchPlaceholder')"
          allow-clear
          class="w-64"
        />
        <Segmented
          v-model:value="filterStatus"
          :options="statusFilters"
          size="small"
        />
      </div>
      <span class="text-xs text-muted-foreground">
        {{ $t('tenant.plugin.totalPlugins', { count: filteredPlugins.length }) }}
      </span>
    </div>

    <!-- 类型筛选（仅在有多种类型时显示） -->
    <div v-if="typeFilters.length > 2" class="flex items-center gap-2">
      <Segmented
        v-model:value="filterType"
        :options="typeFilters"
        size="small"
      />
    </div>

    <!-- 插件卡片网格 -->
    <Spin :spinning="loading">
      <div
        v-if="filteredPlugins.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <div
          v-for="plugin in filteredPlugins"
          :key="plugin.id"
          class="group relative rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-primary/40 hover:shadow-md"
        >
          <!-- 系统插件角标 -->
          <Tooltip
            v-if="plugin.is_system"
            :title="$t('tenant.plugin.isSystem')"
          >
            <div class="absolute right-3 top-3">
              <IconifyIcon
                icon="lucide:shield-check"
                class="size-4 text-warning"
              />
            </div>
          </Tooltip>

          <!-- 头部：图标 + 名称 + 版本 -->
          <div class="mb-3 flex items-start gap-3">
            <div
              class="flex size-11 shrink-0 items-center justify-center rounded-xl transition-colors"
              :class="isEnabled(plugin.id) ? 'bg-primary/10' : 'bg-muted'"
            >
              <IconifyIcon
                :icon="plugin.icon || 'lucide:plug'"
                class="size-5"
                :class="isEnabled(plugin.id) ? 'text-primary' : 'text-muted-foreground'"
              />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate text-sm font-semibold text-foreground">
                  {{ plugin.display_name }}
                </span>
                <span class="shrink-0 text-xs text-muted-foreground">
                  v{{ plugin.version }}
                </span>
              </div>
              <div
                v-if="plugin.author"
                class="mt-0.5 text-xs text-muted-foreground"
              >
                {{ $t('tenant.plugin.by') }} {{ plugin.author }}
              </div>
            </div>
          </div>

          <!-- 描述 -->
          <p
            class="mb-3 line-clamp-2 min-h-[2.5rem] text-xs leading-relaxed text-muted-foreground"
          >
            {{ plugin.description || '-' }}
          </p>

          <!-- 底部：标签 + 操作 -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5">
              <Tag :color="getPluginTypeColor(plugin.plugin_type)" class="!m-0">
                {{ getPluginTypeText(plugin.plugin_type) }}
              </Tag>
              <Tag
                v-if="isEnabled(plugin.id)"
                color="success"
                class="!m-0"
              >
                {{ $t('tenant.plugin.enabled') }}
              </Tag>
            </div>
            <div class="flex items-center gap-1">
              <template v-if="isEnabled(plugin.id)">
                <Tooltip
                  v-if="plugin.config_schema?.properties"
                  :title="$t('tenant.plugin.configure')"
                >
                  <Button
                    v-access:code="['tenant_plugin:configure']"
                    type="text"
                    size="small"
                    class="!size-7 !p-0"
                    @click="onConfigure(plugin)"
                  >
                    <IconifyIcon
                      icon="lucide:settings"
                      class="size-3.5 text-muted-foreground"
                    />
                  </Button>
                </Tooltip>
                <Tooltip :title="$t('tenant.plugin.disable')">
                  <Button
                    v-access:code="['tenant_plugin:disable']"
                    type="text"
                    size="small"
                    class="!size-7 !p-0"
                    @click="onDisable(plugin)"
                  >
                    <IconifyIcon
                      icon="lucide:power-off"
                      class="size-3.5 text-muted-foreground"
                    />
                  </Button>
                </Tooltip>
              </template>
              <Button
                v-else
                v-access:code="['tenant_plugin:enable']"
                type="primary"
                size="small"
                @click="onEnable(plugin)"
              >
                {{ $t('tenant.plugin.enable') }}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading" class="flex items-center justify-center py-20">
        <Empty
          :description="
            searchKeyword || filterType !== 'all' || filterStatus !== 'all'
              ? $t('tenant.plugin.noResults')
              : $t('tenant.plugin.noPlugins')
          "
        />
      </div>
    </Spin>

    <PluginConfigDrawer ref="configDrawerRef" @saved="loadPlugins" />
  </Page>
</template>
