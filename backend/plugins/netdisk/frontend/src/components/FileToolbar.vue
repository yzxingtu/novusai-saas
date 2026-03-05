<script lang="ts" setup>
/**
 * N14d: 文件工具栏 — 面包屑 + 新建文件夹 + 上传 + 排序 + 视图切换 + 搜索
 */
interface BreadcrumbItem { id: number | null; name: string; }

interface Props {
  breadcrumbs: BreadcrumbItem[];
  viewMode:    'grid' | 'list';
  sortBy:      string;
  sortOrder:   'asc' | 'desc';
  searchQuery: string;
}
interface Emits {
  (e: 'navigate', id: number | null, name: string): void;
  (e: 'setViewMode', mode: 'grid' | 'list'): void;
  (e: 'setSort', field: string, order: 'asc' | 'desc'): void;
  (e: 'search', q: string): void;
  (e: 'newFolder'): void;
  (e: 'upload'): void;
  (e: 'refresh'): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};


</script>

<template>
  <div class="flex items-center gap-2 py-1.5 px-3 border-b border-border flex-wrap min-h-[48px] shrink-0">
    <!-- 面包屑导航 -->
    <a-breadcrumb class="flex-1 min-w-0">
      <a-breadcrumb-item
        v-for="(crumb, idx) in breadcrumbs"
        :key="String(crumb.id)"
      >
        <a
          v-if="idx < breadcrumbs.length - 1"
          class="cursor-pointer"
          @click="emit('navigate', crumb.id, crumb.name)"
        >
          {{ crumb.id === null ? $t('plugin.netdisk.nav.root') : crumb.name }}
        </a>
        <span v-else class="text-foreground">
          {{ crumb.id === null ? $t('plugin.netdisk.nav.root') : crumb.name }}
        </span>
      </a-breadcrumb-item>
    </a-breadcrumb>

    <!-- 操作区 -->
    <div class="flex items-center gap-1.5 shrink-0">
      <!-- 搜索 -->
      <a-input-search
        class="w-[180px]"
        size="small"
        :placeholder="$t('plugin.netdisk.action.search')"
        :value="searchQuery"
        @search="(v: string) => emit('search', v)"
        @input="(e: Event) => emit('search', (e.target as HTMLInputElement).value)"
        allow-clear
      />

      <!-- 排序 -->
      <a-select
        :value="`${sortBy}-${sortOrder}`"
        size="small"
        class="w-[130px]"
        @change="(v: string) => { const [f, o] = v.split('-'); emit('setSort', f, o as 'asc' | 'desc'); }"
      >
        <a-select-option value="name-asc">{{ $t('plugin.netdisk.sort.name') }} ↑</a-select-option>
        <a-select-option value="name-desc">{{ $t('plugin.netdisk.sort.name') }} ↓</a-select-option>
        <a-select-option value="size_bytes-asc">{{ $t('plugin.netdisk.sort.size') }} ↑</a-select-option>
        <a-select-option value="size_bytes-desc">{{ $t('plugin.netdisk.sort.size') }} ↓</a-select-option>
        <a-select-option value="updated_at-desc">{{ $t('plugin.netdisk.sort.modified') }} ↓</a-select-option>
        <a-select-option value="updated_at-asc">{{ $t('plugin.netdisk.sort.modified') }} ↑</a-select-option>
      </a-select>

      <!-- 视图切换 -->
      <a-button-group size="small">
        <a-button :type="viewMode === 'grid' ? 'primary' : 'default'" :title="$t('plugin.netdisk.action.viewGrid')" @click="emit('setViewMode', 'grid')">
          <template #icon>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          </template>
        </a-button>
        <a-button :type="viewMode === 'list' ? 'primary' : 'default'" :title="$t('plugin.netdisk.action.viewList')" @click="emit('setViewMode', 'list')">
          <template #icon>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
          </template>
        </a-button>
      </a-button-group>

      <a-divider type="vertical" class="!h-5" />

      <!-- 新建文件夹 -->
      <a-button size="small" @click="emit('newFolder')">{{ $t('plugin.netdisk.action.newFolder') }}</a-button>

      <!-- 刷新 -->
      <a-button size="small" @click="emit('refresh')">{{ $t('plugin.netdisk.action.refresh') }}</a-button>

      <!-- 上传 -->
      <a-button type="primary" size="small" @click="emit('upload')">{{ $t('plugin.netdisk.action.upload') }}</a-button>
    </div>
  </div>
</template>
