<script lang="ts" setup>
/**
 * Icon Picker Component
 * 图标选择器组件
 *
 * Core design / 核心设计：
 * 1. Common icon presets (select directly without searching) / 常用图标预设（无需搜索直接选）
 * 2. Browse tab: paginated loading by collection (lucide / simple-icons etc.), auto-load more on scroll / 浏览标签：按集合分页加载，滚动到底部自动加载更多
 * 3. Iconify API online search (on-demand loading) / Iconify API 在线搜索（按需加载）
 * 4. Manual icon name input + live preview / 手动输入图标名称 + 实时预览
 * 5. Popover instead of Modal, more lightweight / Popover 替代 Modal，更轻量
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { useDebounceFn } from '@vueuse/core';
import { Input, Popover, Select, Spin, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'IconPicker' });

withDefaults(
  defineProps<{
    placeholder?: string;
    value?: string;
  }>(),
  {
    value: '',
    placeholder: 'lucide:cpu',
  },
);

const emit = defineEmits<{
  'update:value': [value: string];
}>();

// ==================== Common icon presets / 常用图标预设 ====================

const PRESET_ICONS: Array<{ icon: string; label: string }> = [
  // AI / Machine Learning / 机器学习
  { icon: 'lucide:brain', label: 'brain' },
  { icon: 'lucide:cpu', label: 'cpu' },
  { icon: 'lucide:bot', label: 'bot' },
  { icon: 'lucide:sparkles', label: 'sparkles' },
  { icon: 'lucide:wand-2', label: 'wand' },
  { icon: 'lucide:zap', label: 'zap' },
  { icon: 'lucide:lightbulb', label: 'lightbulb' },
  { icon: 'lucide:atom', label: 'atom' },
  // Cloud / Technology / 云服务 / 技术
  { icon: 'lucide:cloud', label: 'cloud' },
  { icon: 'lucide:server', label: 'server' },
  { icon: 'lucide:database', label: 'database' },
  { icon: 'lucide:globe', label: 'globe' },
  { icon: 'lucide:network', label: 'network' },
  { icon: 'lucide:satellite', label: 'satellite' },
  { icon: 'lucide:terminal', label: 'terminal' },
  { icon: 'lucide:code', label: 'code' },
  // Communication / Messaging / 通信 / 消息
  { icon: 'lucide:message-circle', label: 'message' },
  { icon: 'lucide:send', label: 'send' },
  { icon: 'lucide:mail', label: 'mail' },
  { icon: 'lucide:phone', label: 'phone' },
  // Security / Admin / 安全 / 管理
  { icon: 'lucide:shield', label: 'shield' },
  { icon: 'lucide:key', label: 'key' },
  { icon: 'lucide:lock', label: 'lock' },
  { icon: 'lucide:settings', label: 'settings' },
  // Media / Visual / 媒体 / 视觉
  { icon: 'lucide:image', label: 'image' },
  { icon: 'lucide:eye', label: 'eye' },
  { icon: 'lucide:mic', label: 'mic' },
  { icon: 'lucide:video', label: 'video' },
  // Data / Analytics / 数据 / 分析
  { icon: 'lucide:bar-chart-3', label: 'chart' },
  { icon: 'lucide:activity', label: 'activity' },
  { icon: 'lucide:trending-up', label: 'trending' },
  { icon: 'lucide:layers', label: 'layers' },
  // Brand / 品牌相关
  { icon: 'simple-icons:openai', label: 'openai' },
  { icon: 'simple-icons:anthropic', label: 'anthropic' },
  { icon: 'simple-icons:google', label: 'google' },
  { icon: 'simple-icons:meta', label: 'meta' },
];

// ==================== Collection definitions / 集合定义 ====================

const COLLECTIONS = [
  { label: 'Lucide', value: 'lucide' },
  { label: 'Simple Icons', value: 'simple-icons' },
  { label: 'Material Design', value: 'mdi' },
  { label: 'Carbon', value: 'carbon' },
  { label: 'Tabler', value: 'tabler' },
];

// ==================== State / 状态 ====================

const popoverOpen = ref(false);
const searchKeyword = ref('');
const searchResults = ref<Array<{ icon: string; label: string }>>([]);
const searchLoading = ref(false);
const activeTab = ref<'browse' | 'preset' | 'search'>('preset');

// ==================== Browse collection state / 浏览集合状态 ====================

const browseCollection = ref('lucide');
const browseAllIcons = ref<string[]>([]);
const browseLoading = ref(false);
const browseVisibleCount = ref(48);
const BROWSE_PAGE_SIZE = 48;

const scrollContainerRef = ref<HTMLDivElement | null>(null);
const sentinelRef = ref<HTMLDivElement | null>(null);
let intersectionObserver: IntersectionObserver | null = null;

const browseDisplayIcons = computed(() => {
  const slice = browseAllIcons.value.slice(0, browseVisibleCount.value);
  return slice.map((name) => ({
    icon: `${browseCollection.value}:${name}`,
    label: name,
  }));
});

const browseHasMore = computed(
  () => browseVisibleCount.value < browseAllIcons.value.length,
);

/** Load all icon names of a collection via Iconify API / 通过 Iconify API 加载集合的所有图标名称 */
async function loadCollection(prefix: string) {
  browseLoading.value = true;
  browseAllIcons.value = [];
  browseVisibleCount.value = BROWSE_PAGE_SIZE;

  try {
    const res = await fetch(
      `https://api.iconify.design/collection?prefix=${encodeURIComponent(prefix)}`,
    );
    if (!res.ok) throw new Error('Failed to load collection');
    const data = await res.json();

    const icons: string[] = [];
    if (data.categories && typeof data.categories === 'object') {
      for (const arr of Object.values(data.categories)) {
        if (Array.isArray(arr)) icons.push(...arr);
      }
    }
    if (Array.isArray(data.uncategorized)) {
      icons.push(...data.uncategorized);
    }
    browseAllIcons.value = [...new Set(icons)];
  } catch {
    browseAllIcons.value = [];
  } finally {
    browseLoading.value = false;
  }
}

function loadMoreBrowse() {
  if (!browseHasMore.value || browseLoading.value) return;
  browseVisibleCount.value += BROWSE_PAGE_SIZE;
}

function setupObserver() {
  destroyObserver();
  if (!sentinelRef.value) return;
  intersectionObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) loadMoreBrowse();
    },
    { root: scrollContainerRef.value, threshold: 0.1 },
  );
  intersectionObserver.observe(sentinelRef.value);
}

function destroyObserver() {
  if (intersectionObserver) {
    intersectionObserver.disconnect();
    intersectionObserver = null;
  }
}

onBeforeUnmount(destroyObserver);

watch(activeTab, async (tab) => {
  if (tab === 'browse') {
    if (browseAllIcons.value.length === 0) {
      await loadCollection(browseCollection.value);
    }
    await nextTick();
    setupObserver();
  } else {
    destroyObserver();
  }
});

watch(browseCollection, async (prefix) => {
  if (activeTab.value === 'browse') {
    await loadCollection(prefix);
    await nextTick();
    setupObserver();
  }
});

// ==================== Search / 搜索 ====================

async function searchIcons(query: string) {
  if (!query.trim()) {
    searchResults.value = [];
    return;
  }
  searchLoading.value = true;
  try {
    const response = await fetch(
      `https://api.iconify.design/search?query=${encodeURIComponent(query)}&limit=48`,
    );
    if (!response.ok) throw new Error('Search failed');
    const data = await response.json();
    const icons: string[] = data.icons || [];
    searchResults.value = icons.map((icon) => ({
      icon,
      label: icon.split(':').pop() || icon,
    }));
  } catch {
    searchResults.value = [];
  } finally {
    searchLoading.value = false;
  }
}

const debouncedSearch = useDebounceFn(searchIcons, 400);

watch(searchKeyword, (val) => {
  if (val.trim()) {
    activeTab.value = 'search';
    debouncedSearch(val);
  } else if (activeTab.value === 'search') {
    activeTab.value = 'preset';
    searchResults.value = [];
  }
});

// ==================== Actions / 操作 ====================

function onSelectIcon(icon: string) {
  emit('update:value', icon);
  popoverOpen.value = false;
  searchKeyword.value = '';
}

function onClear() {
  emit('update:value', '');
}

function onManualInput(e: Event) {
  emit('update:value', (e.target as HTMLInputElement).value);
}

const displayIcons = computed(() => {
  if (activeTab.value === 'search') return searchResults.value;
  if (activeTab.value === 'browse') return browseDisplayIcons.value;
  return PRESET_ICONS;
});

const displayCount = computed(() => {
  if (activeTab.value === 'browse') {
    return `${browseDisplayIcons.value.length} / ${browseAllIcons.value.length}`;
  }
  return `${displayIcons.value.length}`;
});
</script>

<template>
  <div class="flex items-center gap-2">
    <Popover
      v-model:open="popoverOpen"
      trigger="click"
      placement="bottomLeft"
      overlay-class-name="icon-picker-popover"
    >
      <template #content>
        <div class="w-[360px]">
          <!-- Search box / 搜索框 -->
          <Input
            v-model:value="searchKeyword"
            :placeholder="$t('admin.ai.provider.iconPicker.searchPlaceholder')"
            allow-clear
            size="small"
            class="mb-3"
          >
            <template #prefix>
              <IconifyIcon
                icon="lucide:search"
                class="size-3.5 text-muted-foreground"
              />
            </template>
          </Input>

          <!-- Tab switch / Tab 切换 -->
          <div class="mb-2 flex items-center justify-between">
            <div class="flex gap-1 text-xs">
              <button
                class="rounded px-2 py-0.5 transition-colors"
                :class="
                  activeTab === 'preset'
                    ? 'bg-primary/10 font-medium text-primary'
                    : 'text-muted-foreground hover:text-foreground'
                "
                @click="
                  activeTab = 'preset';
                  searchKeyword = '';
                "
              >
                {{ $t('admin.ai.provider.iconPicker.preset') }}
              </button>
              <button
                class="rounded px-2 py-0.5 transition-colors"
                :class="
                  activeTab === 'browse'
                    ? 'bg-primary/10 font-medium text-primary'
                    : 'text-muted-foreground hover:text-foreground'
                "
                @click="
                  activeTab = 'browse';
                  searchKeyword = '';
                "
              >
                {{ $t('admin.ai.provider.iconPicker.browse') }}
              </button>
              <button
                class="rounded px-2 py-0.5 transition-colors"
                :class="
                  activeTab === 'search'
                    ? 'bg-primary/10 font-medium text-primary'
                    : 'text-muted-foreground hover:text-foreground'
                "
                @click="activeTab = 'search'"
              >
                {{ $t('admin.ai.provider.iconPicker.search') }}
              </button>
            </div>
            <span class="text-xs text-muted-foreground">
              {{ displayCount }} {{ $t('admin.ai.provider.iconPicker.icons') }}
            </span>
          </div>

          <!-- Collection selector (browse mode only) / 集合选择器（仅浏览模式） -->
          <div v-if="activeTab === 'browse'" class="mb-2">
            <Select
              v-model:value="browseCollection"
              :options="COLLECTIONS"
              size="small"
              class="w-full"
            />
          </div>

          <!-- Icon grid / 图标网格 -->
          <Spin :spinning="searchLoading || browseLoading" size="small">
            <div
              v-if="displayIcons.length > 0"
              ref="scrollContainerRef"
              class="grid max-h-[280px] grid-cols-8 gap-1 overflow-y-auto"
            >
              <Tooltip
                v-for="item in displayIcons"
                :key="item.icon"
                :title="item.icon"
                placement="top"
              >
                <button
                  class="flex size-10 items-center justify-center rounded-lg border border-transparent transition-all hover:border-primary/30 hover:bg-primary/5"
                  :class="
                    value === item.icon ? 'border-primary bg-primary/10' : ''
                  "
                  @click="onSelectIcon(item.icon)"
                >
                  <IconifyIcon
                    :icon="item.icon"
                    class="size-5 text-foreground/80"
                  />
                </button>
              </Tooltip>
              <!-- Sentinel element: triggers load more on scroll / 哨兵元素：滚动到此处触发加载更多 -->
              <div
                v-if="activeTab === 'browse' && browseHasMore"
                ref="sentinelRef"
                class="col-span-8 flex items-center justify-center py-2 text-xs text-muted-foreground"
              >
                <Spin size="small" />
              </div>
            </div>
            <div
              v-else-if="activeTab === 'search' && !searchLoading"
              class="flex h-[100px] items-center justify-center text-sm text-muted-foreground"
            >
              {{
                searchKeyword
                  ? $t('admin.ai.provider.iconPicker.noResults')
                  : $t('admin.ai.provider.iconPicker.searchTip')
              }}
            </div>
          </Spin>

          <!-- Manual input / 手动输入 -->
          <div class="mt-3 border-t border-border pt-3">
            <div class="flex items-center gap-2">
              <Input
                :value="value"
                :placeholder="placeholder"
                size="small"
                class="flex-1"
                @change="onManualInput"
              />
              <div
                v-if="value"
                class="flex size-8 items-center justify-center rounded-lg bg-accent"
              >
                <IconifyIcon :icon="value" class="size-5 text-primary" />
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Trigger / 触发器：自定义 flex 布局，保证图标按钮与 input 高度一致 -->
      <div
        class="flex h-9 w-full cursor-pointer items-stretch overflow-hidden rounded-lg border border-input bg-background text-sm transition-colors hover:border-primary/50 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20"
      >
        <!-- 图标选择区：与 input 等高 -->
        <div
          class="flex min-w-[36px] shrink-0 items-center justify-center border-r border-border bg-muted/30"
        >
          <IconifyIcon
            v-if="value"
            :icon="value"
            class="size-5 text-primary"
          />
          <IconifyIcon
            v-else
            icon="lucide:plus"
            class="size-5 text-muted-foreground transition-colors hover:text-primary"
          />
        </div>
        <!-- 输入框：重写为原生 input，与左侧图标区等高 -->
        <input
          :value="value"
          :placeholder="placeholder"
          readonly
          class="min-w-0 flex-1 cursor-pointer bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground"
        />
        <!-- 清空按钮 -->
        <div
          v-if="value"
          class="flex shrink-0 cursor-pointer items-center px-2 text-muted-foreground transition-colors hover:text-primary"
          @click.stop="onClear"
        >
          <IconifyIcon icon="lucide:x" class="size-4" />
        </div>
      </div>
    </Popover>
  </div>
</template>

<style>
.icon-picker-popover .ant-popover-inner {
  padding: 12px;
}
</style>
