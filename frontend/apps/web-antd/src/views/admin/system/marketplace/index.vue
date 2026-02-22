<script lang="ts" setup>
import { computed, onMounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Empty,
  Input,
  Select,
  Segmented,
  Skeleton,
  Tag,
  Tooltip,
  message,
} from 'ant-design-vue';

import type {
  InstallStatus,
  MarketplacePlugin,
  RegistryCategory,
} from '#/api/admin/marketplace';

import {
  getMarketplaceListApi,
  installFromMarketplaceApi,
  refreshMarketplaceCacheApi,
  updateFromMarketplaceApi,
} from '#/api/admin/marketplace';
import { $t } from '#/locales';

import MarketplaceDetailDrawer from './MarketplaceDetailDrawer.vue';

defineOptions({ name: 'AdminSystemMarketplace' });

// ============================================================
// State
// ============================================================

const loading = ref(false);
const refreshing = ref(false);
const plugins = ref<MarketplacePlugin[]>([]);
const categories = ref<RegistryCategory[]>([]);
const mirror = ref('github');
const installingSlug = ref<string | null>(null);

// Filters
const keyword = ref('');
const activeCategory = ref('all');
const statusFilter = ref<InstallStatus | ''>('');
const typeFilter = ref('');
const debounceTimer = ref<ReturnType<typeof setTimeout> | null>(null);

// Mirror switcher
const mirrorOptions = [
  { value: 'github', label: 'GitHub', icon: 'lucide:github' },
  { value: 'gitee', label: 'Gitee', icon: 'lucide:git-branch' },
];

// Detail drawer
const drawerVisible = ref(false);
const selectedPlugin = ref<MarketplacePlugin | null>(null);

// ============================================================
// Computed
// ============================================================

const filteredPlugins = computed(() => plugins.value);

const totalCount = computed(() => plugins.value.length);

const installedCount = computed(
  () => plugins.value.filter((p) => p.install_status !== 'not_installed').length,
);

const updateCount = computed(
  () => plugins.value.filter((p) => p.install_status === 'update_available').length,
);

const categoryOptions = computed(() => {
  const allOption = {
    value: 'all',
    label: $t('admin.system.marketplace.allCategories'),
  };
  const opts = categories.value.map((c) => ({
    value: c.code,
    label: $t(`admin.system.marketplace.category.${c.code}`, c.name),
  }));
  return [allOption, ...opts];
});

const statusOptions = [
  { value: '', label: $t('admin.system.marketplace.allStatus') },
  { value: 'not_installed', label: $t('admin.system.marketplace.status.notInstalled') },
  { value: 'installed', label: $t('admin.system.marketplace.status.installed') },
  { value: 'update_available', label: $t('admin.system.marketplace.status.updateAvailable') },
];

// ============================================================
// Data loading
// ============================================================

async function loadPlugins() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {};
    if (keyword.value) params['filter[keyword]'] = keyword.value;
    if (activeCategory.value !== 'all') params['filter[category]'] = activeCategory.value;
    if (statusFilter.value) params['filter[install_status]'] = statusFilter.value;
    if (typeFilter.value) params['filter[plugin_type]'] = typeFilter.value;
    if (mirror.value) params['mirror'] = mirror.value;

    const res = await getMarketplaceListApi(params);
    plugins.value = res.items || [];
    categories.value = res.categories || [];
    mirror.value = res.mirror || 'github';
  } catch {
    plugins.value = [];
  } finally {
    loading.value = false;
  }
}

function switchMirror(newMirror: string) {
  if (mirror.value === newMirror) return;
  mirror.value = newMirror;
  loadPlugins();
}

async function handleRefresh() {
  refreshing.value = true;
  try {
    await refreshMarketplaceCacheApi();
    message.success($t('admin.system.marketplace.refreshSuccess'));
    await loadPlugins();
  } catch {
    // handled by global interceptor
  } finally {
    refreshing.value = false;
  }
}

function onKeywordChange() {
  if (debounceTimer.value) clearTimeout(debounceTimer.value);
  debounceTimer.value = setTimeout(() => {
    loadPlugins();
  }, 300);
}

// ============================================================
// Install / Update
// ============================================================

async function handleInstall(plugin: MarketplacePlugin) {
  installingSlug.value = plugin.slug;
  try {
    await installFromMarketplaceApi(plugin.slug);
    message.success(
      $t('admin.system.marketplace.installSuccess', { name: plugin.display_name }),
    );
    await loadPlugins();
  } catch {
    message.error($t('admin.system.marketplace.installFailed'));
  } finally {
    installingSlug.value = null;
  }
}

async function handleUpdate(plugin: MarketplacePlugin) {
  installingSlug.value = plugin.slug;
  try {
    await updateFromMarketplaceApi(plugin.slug);
    message.success(
      $t('admin.system.marketplace.updateSuccess', { name: plugin.display_name }),
    );
    await loadPlugins();
  } catch {
    message.error($t('admin.system.marketplace.updateFailed'));
  } finally {
    installingSlug.value = null;
  }
}

// ============================================================
// Detail drawer
// ============================================================

function openDetail(plugin: MarketplacePlugin) {
  selectedPlugin.value = plugin;
  drawerVisible.value = true;
}

function onDrawerRefresh() {
  loadPlugins();
}

// ============================================================
// Watchers & Lifecycle
// ============================================================

watch([activeCategory, statusFilter, typeFilter], () => {
  loadPlugins();
});

onMounted(() => {
  loadPlugins();
});
</script>

<template>
  <div class="marketplace-page p-5">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-foreground text-2xl font-bold">
            {{ $t('admin.system.marketplace.title') }}
          </h1>
          <p class="text-muted-foreground mt-1 text-sm">
            {{ $t('admin.system.marketplace.description') }}
          </p>
        </div>
        <div class="flex items-center gap-3">
          <div class="bg-muted flex items-center gap-1 rounded-lg p-1">
            <button
              v-for="m in mirrorOptions"
              :key="m.value"
              class="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-200"
              :class="mirror === m.value
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'"
              @click="switchMirror(m.value)"
            >
              <IconifyIcon :icon="m.icon" class="h-3.5 w-3.5" />
              <span>{{ m.label }}</span>
            </button>
          </div>
          <Button
            :loading="refreshing"
            @click="handleRefresh"
          >
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" />
            </template>
            {{ $t('admin.system.marketplace.refresh') }}
          </Button>
        </div>
      </div>

      <!-- Stats -->
      <div class="mt-4 flex items-center gap-4 text-sm">
        <span class="text-muted-foreground">
          {{ $t('admin.system.marketplace.pluginCount', { total: totalCount }) }}
        </span>
        <span class="text-muted-foreground">·</span>
        <span class="text-success">
          {{ $t('admin.system.marketplace.installedCount', { count: installedCount }) }}
        </span>
        <span v-if="updateCount > 0" class="text-warning">
          · {{ $t('admin.system.marketplace.updatesAvailable', { count: updateCount }) }}
        </span>
      </div>
    </div>

    <!-- Category Tabs -->
    <div class="mb-4">
      <Segmented
        v-model:value="activeCategory"
        :options="categoryOptions"
        size="large"
      />
    </div>

    <!-- Filter Bar -->
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <Input
        v-model:value="keyword"
        :placeholder="$t('admin.system.marketplace.searchPlaceholder')"
        allow-clear
        class="!w-72"
        @input="onKeywordChange"
      >
        <template #prefix>
          <IconifyIcon icon="lucide:search" class="text-muted-foreground" />
        </template>
      </Input>

      <Select
        v-model:value="statusFilter"
        :options="statusOptions"
        class="!w-36"
        :placeholder="$t('admin.system.marketplace.allStatus')"
      />

      <Select
        v-model:value="typeFilter"
        class="!w-36"
        :placeholder="$t('admin.system.marketplace.allTypes')"
        allow-clear
      >
        <Select.Option value="">{{ $t('admin.system.marketplace.allTypes') }}</Select.Option>
        <Select.Option value="adapter">Adapter</Select.Option>
        <Select.Option value="skill">Skill</Select.Option>
        <Select.Option value="hook">Hook</Select.Option>
        <Select.Option value="api">API</Select.Option>
        <Select.Option value="storage">Storage</Select.Option>
        <Select.Option value="composite">Composite</Select.Option>
      </Select>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <div v-for="i in 8" :key="i" class="bg-card rounded-xl border p-5">
        <Skeleton active :paragraph="{ rows: 3 }" />
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="filteredPlugins.length === 0"
      class="flex flex-col items-center justify-center py-20"
    >
      <Empty
        :description="keyword || statusFilter || typeFilter
          ? $t('admin.system.marketplace.noMatchResult')
          : $t('admin.system.marketplace.noPlugins')"
      />
      <p v-if="keyword || statusFilter || typeFilter" class="text-muted-foreground mt-2 text-sm">
        {{ $t('admin.system.marketplace.tryAdjustFilter') }}
      </p>
    </div>

    <!-- Plugin Card Grid -->
    <div
      v-else
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      <div
        v-for="plugin in filteredPlugins"
        :key="plugin.slug"
        class="plugin-card bg-card group cursor-pointer rounded-xl border p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
        @click="openDetail(plugin)"
      >
        <!-- Card Header -->
        <div class="mb-3 flex items-start justify-between">
          <div class="bg-primary/10 flex h-11 w-11 items-center justify-center rounded-lg">
            <IconifyIcon
              :icon="plugin.icon || 'lucide:puzzle'"
              class="text-primary h-6 w-6"
            />
          </div>
          <Badge
            v-if="plugin.official"
            :count="$t('admin.system.marketplace.official')"
            :number-style="{ backgroundColor: 'var(--primary)', fontSize: '11px' }"
          />
          <Tag v-else color="default" class="!m-0 !text-xs">
            {{ $t('admin.system.marketplace.community') }}
          </Tag>
        </div>

        <!-- Card Body -->
        <h3 class="text-foreground mb-1 truncate text-base font-semibold">
          {{ plugin.display_name }}
        </h3>
        <p class="text-muted-foreground mb-3 line-clamp-2 text-sm leading-relaxed">
          {{ plugin.description || '' }}
        </p>

        <!-- Tags -->
        <div v-if="plugin.tags && plugin.tags.length > 0" class="mb-3 flex flex-wrap gap-1">
          <Tag
            v-for="tag in plugin.tags.slice(0, 3)"
            :key="tag"
            class="!m-0 !text-xs"
            color="default"
          >
            {{ tag }}
          </Tag>
          <Tooltip
            v-if="plugin.tags.length > 3"
            :title="plugin.tags.slice(3).join(', ')"
          >
            <Tag class="!m-0 !text-xs" color="default">
              +{{ plugin.tags.length - 3 }}
            </Tag>
          </Tooltip>
        </div>

        <!-- Card Footer -->
        <div class="flex items-center justify-between border-t pt-3">
          <div class="text-muted-foreground flex items-center gap-2 text-xs">
            <span>{{ plugin.author || '-' }}</span>
            <span>·</span>
            <span>v{{ plugin.version }}</span>
          </div>

          <!-- Install Button -->
          <Button
            v-if="plugin.install_status === 'not_installed'"
            type="primary"
            size="small"
            :loading="installingSlug === plugin.slug"
            @click.stop="handleInstall(plugin)"
          >
            <template v-if="installingSlug !== plugin.slug" #icon>
              <IconifyIcon icon="lucide:download" />
            </template>
            {{
              installingSlug === plugin.slug
                ? $t('admin.system.marketplace.installing')
                : $t('admin.system.marketplace.install')
            }}
          </Button>

          <Tag
            v-else-if="plugin.install_status === 'installed'"
            color="success"
            class="!m-0"
          >
            <template #icon>
              <IconifyIcon icon="lucide:check" />
            </template>
            {{ $t('admin.system.marketplace.installed') }}
          </Tag>

          <Button
            v-else-if="plugin.install_status === 'update_available'"
            size="small"
            class="!border-warning !text-warning hover:!bg-warning/10"
            :loading="installingSlug === plugin.slug"
            @click.stop="handleUpdate(plugin)"
          >
            <template v-if="installingSlug !== plugin.slug" #icon>
              <IconifyIcon icon="lucide:arrow-up-circle" />
            </template>
            {{
              installingSlug === plugin.slug
                ? $t('admin.system.marketplace.updating')
                : $t('admin.system.marketplace.update', { version: plugin.version })
            }}
          </Button>
        </div>
      </div>
    </div>

    <!-- Detail Drawer -->
    <MarketplaceDetailDrawer
      v-model:open="drawerVisible"
      :plugin="selectedPlugin"
      @refresh="onDrawerRefresh"
      @install="handleInstall"
      @update="handleUpdate"
      :installing-slug="installingSlug"
    />
  </div>
</template>

<style scoped>
.plugin-card {
  border-color: var(--border);
}

.plugin-card:hover {
  border-color: var(--primary);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
