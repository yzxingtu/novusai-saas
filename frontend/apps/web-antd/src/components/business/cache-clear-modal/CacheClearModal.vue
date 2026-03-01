<script lang="ts" setup>
/**
 * 缓存清理弹窗组件
 *
 * 展示服务端 + 前端缓存分类的统计信息，支持选择性清理。
 * - 服务端缓存：通过 API 获取统计、执行清理
 * - 前端缓存：客户端扫描 localStorage / sessionStorage / preferences
 */
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';

import { useVbenModal } from '@vben/common-ui';
import { useTabbarStore } from '@vben/stores';

import {
  Checkbox,
  Divider,
  Spin,
  Tag,
  message,
} from 'ant-design-vue';

import {
  getCacheSummaryApi,
  clearCacheApi,
} from '#/api/admin/cache';
import { $t } from '#/locales';

// ============================================================
// Types
// ============================================================

interface CacheItem {
  category: string;
  key_count: number;
  size_bytes: number;
  size_human: string;
  source: 'backend' | 'frontend';
}

// ============================================================
// 前端缓存类别定义
// ============================================================

const FE_CATEGORIES = ['fe_local_storage', 'fe_tab_cache', 'fe_preferences'] as const;
type FrontendCategory = typeof FE_CATEGORIES[number];

/** Token 相关 key 后缀，清理 localStorage 时必须保留 */
const TOKEN_KEY_SUFFIXES = [
  'admin_token', 'admin_refresh_token',
  'tenant_admin_token', 'tenant_admin_refresh_token',
  'tenant_user_token', 'tenant_user_refresh_token',
];

/** Preference 相关 key 后缀 */
const PREF_KEY_SUFFIXES = ['preferences', 'preferences-locale', 'preferences-theme'];

// ============================================================
// State
// ============================================================

const router = useRouter();

const loading = ref(false);
const clearing = ref(false);

const backendItems = ref<CacheItem[]>([]);
const frontendItems = ref<CacheItem[]>([]);

const isAdminSide = computed(() => {
  return !router.currentRoute.value.path.startsWith('/tenant');
});
const selectedCategories = ref<Set<string>>(new Set());

const allItems = computed(() => [...backendItems.value, ...frontendItems.value]);
const totalCount = computed(() => allItems.value.length);

const allSelected = computed(() => {
  return totalCount.value > 0 && selectedCategories.value.size === totalCount.value;
});

const hasSelection = computed(() => selectedCategories.value.size > 0);
const selectedCount = computed(() => selectedCategories.value.size);

const totalSizeHuman = computed(() => {
  const total = allItems.value.reduce((sum, item) => sum + item.size_bytes, 0);
  return formatBytes(total);
});

// ============================================================
// Helpers
// ============================================================

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const val = bytes / 1024 ** i;
  return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${units[i]!}`;
}

function getStorageByteSize(value: string): number {
  return new Blob([value]).size;
}

function isTokenKey(key: string): boolean {
  return TOKEN_KEY_SUFFIXES.some((suffix) => key.endsWith(suffix));
}

function isPrefKey(key: string): boolean {
  return PREF_KEY_SUFFIXES.some((suffix) => key.endsWith(`-${suffix}`));
}

// ============================================================
// Selection
// ============================================================

function toggleCategory(category: string) {
  const next = new Set(selectedCategories.value);
  if (next.has(category)) {
    next.delete(category);
  } else {
    next.add(category);
  }
  selectedCategories.value = next;
}

function toggleAll() {
  if (allSelected.value) {
    selectedCategories.value = new Set();
  } else {
    selectedCategories.value = new Set(allItems.value.map((c) => c.category));
  }
}

// ============================================================
// 前端缓存扫描
// ============================================================

function scanFrontendCaches(): CacheItem[] {
  const items: CacheItem[] = [];

  // 1. fe_local_storage — 非 Token、非 Preferences 的 localStorage 条目
  {
    let keyCount = 0;
    let sizeBytes = 0;
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key || isTokenKey(key) || isPrefKey(key)) continue;
      keyCount++;
      const val = localStorage.getItem(key);
      if (val) sizeBytes += getStorageByteSize(val);
    }
    items.push({
      category: 'fe_local_storage',
      key_count: keyCount,
      size_bytes: sizeBytes,
      size_human: formatBytes(sizeBytes),
      source: 'frontend',
    });
  }

  // 2. fe_tab_cache — sessionStorage 中的标签页缓存
  {
    let keyCount = 0;
    let sizeBytes = 0;
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (!key) continue;
      keyCount++;
      const val = sessionStorage.getItem(key);
      if (val) sizeBytes += getStorageByteSize(val);
    }
    items.push({
      category: 'fe_tab_cache',
      key_count: keyCount,
      size_bytes: sizeBytes,
      size_human: formatBytes(sizeBytes),
      source: 'frontend',
    });
  }

  // 3. fe_preferences — Preferences localStorage 条目
  {
    let keyCount = 0;
    let sizeBytes = 0;
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key || !isPrefKey(key)) continue;
      keyCount++;
      const val = localStorage.getItem(key);
      if (val) sizeBytes += getStorageByteSize(val);
    }
    items.push({
      category: 'fe_preferences',
      key_count: keyCount,
      size_bytes: sizeBytes,
      size_human: formatBytes(sizeBytes),
      source: 'frontend',
    });
  }

  return items;
}

// ============================================================
// 前端缓存清理
// ============================================================

function clearFrontendCategory(category: FrontendCategory) {
  switch (category) {
    case 'fe_local_storage': {
      const keysToRemove: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && !isTokenKey(key) && !isPrefKey(key)) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach((k) => localStorage.removeItem(k));
      break;
    }
    case 'fe_tab_cache': {
      sessionStorage.clear();
      try {
        const tabbarStore = useTabbarStore();
        tabbarStore.$reset();
      } catch {
        // tabbar store may not be initialized
      }
      break;
    }
    case 'fe_preferences': {
      const keysToRemove: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && isPrefKey(key)) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach((k) => localStorage.removeItem(k));
      break;
    }
  }
}

// ============================================================
// Load & Clear
// ============================================================

async function loadSummary() {
  loading.value = true;
  try {
    if (isAdminSide.value) {
      const res = await getCacheSummaryApi();
      backendItems.value = res.categories.map((c) => ({
        ...c,
        source: 'backend' as const,
      }));
    } else {
      backendItems.value = [];
    }
    frontendItems.value = scanFrontendCaches();
    // default select all
    selectedCategories.value = new Set(allItems.value.map((c) => c.category));
  } catch {
    message.error($t('admin.system.cache.clearFailed'));
  } finally {
    loading.value = false;
  }
}

const [Modal, modalApi] = useVbenModal({
  async onConfirm() {
    if (!hasSelection.value) return;

    clearing.value = true;
    modalApi.lock();
    try {
      const selected = selectedCategories.value;
      const backendCats = backendItems.value
        .filter((c) => selected.has(c.category))
        .map((c) => c.category);
      const frontendCats = frontendItems.value
        .filter((c) => selected.has(c.category))
        .map((c) => c.category) as FrontendCategory[];

      const messages: string[] = [];

      // 清理服务端缓存
      if (backendCats.length > 0) {
        const result = await clearCacheApi({ categories: backendCats });
        messages.push(
          `${$t('admin.system.cache.clearedKeys', { count: result.cleared_keys })}`,
          `${$t('admin.system.cache.clearedSize', { size: result.cleared_size_human })}`,
          `${$t('admin.system.cache.duration', { ms: result.duration_ms })}`,
        );
      }

      // 清理前端缓存
      if (frontendCats.length > 0) {
        for (const cat of frontendCats) {
          clearFrontendCategory(cat);
        }
        messages.push($t('admin.system.cache.frontendCleared'));
      }

      message.success(
        `${$t('admin.system.cache.clearSuccess')} — ${messages.join('，')}`,
      );
      modalApi.close();
    } catch {
      message.error($t('admin.system.cache.clearFailed'));
      modalApi.unlock();
    } finally {
      clearing.value = false;
    }
  },

  async onOpenChange(isOpen) {
    if (isOpen) {
      await loadSummary();
    } else {
      backendItems.value = [];
      frontendItems.value = [];
      selectedCategories.value = new Set();
    }
  },

  title: $t('admin.system.cache.title'),
  confirmText: $t('admin.system.cache.tooltip'),
});

function open() {
  modalApi.open();
}

defineExpose({ open });
</script>

<template>
  <Modal>
    <Spin :spinning="loading || clearing">
      <div v-if="!loading && allItems.length > 0">
        <!-- Header: select all + total size -->
        <div class="mb-3 flex items-center justify-between">
          <Checkbox :checked="allSelected" @change="toggleAll">
            {{ allSelected ? $t('admin.system.cache.deselectAll') : $t('admin.system.cache.selectAll') }}
            <span class="text-muted-foreground ml-1 text-xs">
              ({{ selectedCount }}/{{ totalCount }})
            </span>
          </Checkbox>
          <Tag color="blue">
            {{ $t('admin.system.cache.totalSize') }}: {{ totalSizeHuman }}
          </Tag>
        </div>

        <!-- 服务端缓存 -->
        <template v-if="backendItems.length > 0">
          <Divider orientation="left" class="!my-2 !text-xs">
            {{ $t('admin.system.cache.backendSection') }}
          </Divider>
          <div class="space-y-2">
            <div
              v-for="item in backendItems"
              :key="item.category"
              class="flex cursor-pointer items-center rounded-lg border border-border px-3 py-2.5 transition-colors hover:bg-accent/50"
              :class="{
                'border-primary/30 bg-primary/5': selectedCategories.has(item.category),
              }"
              @click="toggleCategory(item.category)"
            >
              <Checkbox
                :checked="selectedCategories.has(item.category)"
                class="mr-3"
                @click.stop
                @change="toggleCategory(item.category)"
              />
              <div class="min-w-0 flex-1">
                <div class="text-sm font-medium text-foreground">
                  {{ $t(`admin.system.cache.category.${item.category}`) }}
                </div>
              </div>
              <div class="ml-4 flex items-center gap-3 text-xs text-muted-foreground">
                <span>{{ item.key_count }} {{ $t('admin.system.cache.columns.keyCount') }}</span>
                <Tag :color="item.size_bytes > 0 ? 'orange' : 'default'">
                  {{ item.size_human }}
                </Tag>
              </div>
            </div>
          </div>
        </template>

        <!-- 前端缓存 -->
        <Divider orientation="left" class="!my-2 !mt-4 !text-xs">
          {{ $t('admin.system.cache.frontendSection') }}
        </Divider>
        <div class="space-y-2">
          <div
            v-for="item in frontendItems"
            :key="item.category"
            class="flex cursor-pointer items-center rounded-lg border border-border px-3 py-2.5 transition-colors hover:bg-accent/50"
            :class="{
              'border-primary/30 bg-primary/5': selectedCategories.has(item.category),
            }"
            @click="toggleCategory(item.category)"
          >
            <Checkbox
              :checked="selectedCategories.has(item.category)"
              class="mr-3"
              @click.stop
              @change="toggleCategory(item.category)"
            />
            <div class="min-w-0 flex-1">
              <div class="text-sm font-medium text-foreground">
                {{ $t(`admin.system.cache.category.${item.category}`) }}
              </div>
            </div>
            <div class="ml-4 flex items-center gap-3 text-xs text-muted-foreground">
              <span>{{ item.key_count }} {{ $t('admin.system.cache.columns.keyCount') }}</span>
              <Tag :color="item.size_bytes > 0 ? 'orange' : 'default'">
                {{ item.size_human }}
              </Tag>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-if="!loading && allItems.length === 0"
        class="py-8 text-center text-muted-foreground"
      >
        {{ $t('admin.system.cache.noCache') }}
      </div>
    </Spin>
  </Modal>
</template>
