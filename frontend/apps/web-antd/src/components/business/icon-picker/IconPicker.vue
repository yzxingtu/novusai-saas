<script lang="ts" setup>
/**
 * Lucide-only local icon picker.
 * Lucide 本地离线图标选择器。
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import {
  ensureLucideIconCatalogRegistered,
  IconifyIcon,
  isLucideCatalogIconId,
  normalizeLucideIconId,
} from '@vben/icons';

import { useDebounceFn } from '@vueuse/core';
import { Input, Popover, Spin, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'IconPicker' });

const props = withDefaults(
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

const PRESET_ICONS: Array<{ icon: string; label: string }> = [
  { icon: 'lucide:brain', label: 'brain' },
  { icon: 'lucide:cpu', label: 'cpu' },
  { icon: 'lucide:bot', label: 'bot' },
  { icon: 'lucide:sparkles', label: 'sparkles' },
  { icon: 'lucide:wand-2', label: 'wand-2' },
  { icon: 'lucide:zap', label: 'zap' },
  { icon: 'lucide:lightbulb', label: 'lightbulb' },
  { icon: 'lucide:atom', label: 'atom' },
  { icon: 'lucide:cloud', label: 'cloud' },
  { icon: 'lucide:server', label: 'server' },
  { icon: 'lucide:database', label: 'database' },
  { icon: 'lucide:globe', label: 'globe' },
  { icon: 'lucide:network', label: 'network' },
  { icon: 'lucide:route', label: 'route' },
  { icon: 'lucide:terminal', label: 'terminal' },
  { icon: 'lucide:code', label: 'code' },
  { icon: 'lucide:message-circle', label: 'message-circle' },
  { icon: 'lucide:send', label: 'send' },
  { icon: 'lucide:mail', label: 'mail' },
  { icon: 'lucide:phone', label: 'phone' },
  { icon: 'lucide:shield', label: 'shield' },
  { icon: 'lucide:key', label: 'key' },
  { icon: 'lucide:lock', label: 'lock' },
  { icon: 'lucide:settings', label: 'settings' },
  { icon: 'lucide:image', label: 'image' },
  { icon: 'lucide:eye', label: 'eye' },
  { icon: 'lucide:mic', label: 'mic' },
  { icon: 'lucide:video', label: 'video' },
  { icon: 'lucide:bar-chart-3', label: 'bar-chart-3' },
  { icon: 'lucide:activity', label: 'activity' },
  { icon: 'lucide:trending-up', label: 'trending-up' },
  { icon: 'lucide:layers', label: 'layers' },
  { icon: 'lucide:package', label: 'package' },
  { icon: 'lucide:plug', label: 'plug' },
  { icon: 'lucide:rocket', label: 'rocket' },
  { icon: 'lucide:briefcase', label: 'briefcase' },
];

const popoverOpen = ref(false);
const searchKeyword = ref('');
const searchResults = ref<Array<{ icon: string; label: string }>>([]);
const searchLoading = ref(false);
const activeTab = ref<'browse' | 'preset' | 'search'>('preset');
const browseAllIcons = ref<string[]>([]);
const browseLoading = ref(false);
const browseVisibleCount = ref(48);
const manualInputValue = ref('');

const BROWSE_PAGE_SIZE = 48;

const scrollContainerRef = ref<HTMLDivElement | null>(null);
const sentinelRef = ref<HTMLDivElement | null>(null);
let intersectionObserver: IntersectionObserver | null = null;

const lucideIconSet = computed(() => new Set(browseAllIcons.value));

function toDisplayItem(icon: string) {
  return {
    icon,
    label: icon.replace(/^lucide:/, ''),
  };
}

async function ensureLucideCatalogLoaded(): Promise<void> {
  if (browseAllIcons.value.length > 0) {
    return;
  }

  browseLoading.value = true;
  try {
    browseAllIcons.value = [...(await ensureLucideIconCatalogRegistered())];
  } finally {
    browseLoading.value = false;
  }
}

function isKnownLucideIcon(icon: null | string | undefined): boolean {
  if (!icon) {
    return false;
  }
  return lucideIconSet.value.has(normalizeLucideIconId(icon));
}

function getPreviewIcon(icon: null | string | undefined): string {
  if (!icon?.trim()) {
    return '';
  }

  const normalized = normalizeLucideIconId(icon);
  return isKnownLucideIcon(normalized) ? normalized : 'lucide:circle-alert';
}

const browseDisplayIcons = computed(() => {
  const slice = browseAllIcons.value.slice(0, browseVisibleCount.value);
  return slice.map((icon) => toDisplayItem(icon));
});

const browseHasMore = computed(
  () => browseVisibleCount.value < browseAllIcons.value.length,
);

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

const selectedPreviewIcon = computed(() =>
  getPreviewIcon(manualInputValue.value),
);

function loadMoreBrowse() {
  if (!browseHasMore.value || browseLoading.value) return;
  browseVisibleCount.value += BROWSE_PAGE_SIZE;
}

function setupObserver() {
  destroyObserver();
  if (!sentinelRef.value) return;

  intersectionObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) {
        loadMoreBrowse();
      }
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

watch(
  () => popoverOpen.value,
  async (open) => {
    if (!open) {
      destroyObserver();
      searchKeyword.value = '';
      return;
    }

    await ensureLucideCatalogLoaded();
    if (activeTab.value === 'browse') {
      await nextTick();
      setupObserver();
    }
  },
);

watch(
  () => activeTab.value,
  async (tab) => {
    if (tab === 'browse') {
      browseVisibleCount.value = BROWSE_PAGE_SIZE;
      await ensureLucideCatalogLoaded();
      await nextTick();
      setupObserver();
      return;
    }

    destroyObserver();

    if (tab === 'search' && searchKeyword.value.trim()) {
      debouncedSearch(searchKeyword.value);
    }
  },
);

watch(
  () => searchKeyword.value,
  (val) => {
    if (val.trim()) {
      activeTab.value = 'search';
      debouncedSearch(val);
      return;
    }

    searchResults.value = [];
    if (activeTab.value === 'search') {
      activeTab.value = 'preset';
    }
  },
);

watch(
  () => manualInputValue.value,
  async (icon) => {
    const normalized = normalizeLucideIconId(icon);
    if (!normalized || isLucideCatalogIconId(normalized)) {
      return;
    }

    await ensureLucideCatalogLoaded();
  },
  { immediate: true },
);

watch(
  () => searchKeyword.value,
  () => {
    if (activeTab.value === 'browse') {
      browseVisibleCount.value = BROWSE_PAGE_SIZE;
    }
  },
);

async function searchIcons(query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    searchResults.value = [];
    return;
  }

  searchLoading.value = true;
  try {
    await ensureLucideCatalogLoaded();
    searchResults.value = browseAllIcons.value
      .filter((icon) => icon.toLowerCase().includes(normalized))
      .slice(0, 96)
      .map((icon) => toDisplayItem(icon));
  } finally {
    searchLoading.value = false;
  }
}

const debouncedSearch = useDebounceFn((query: string) => {
  void searchIcons(query);
}, 120);

watch(
  () => props.value,
  (value) => {
    manualInputValue.value = value ?? '';
  },
  { immediate: true },
);

watch(
  () => manualInputValue.value,
  (value) => {
    const normalized = normalizeLucideIconId(value);
    if (!normalized) {
      emit('update:value', '');
      return;
    }

    if (!isKnownLucideIcon(normalized)) {
      return;
    }

    if (manualInputValue.value !== normalized) {
      manualInputValue.value = normalized;
      return;
    }

    emit('update:value', normalized);
  },
);

function onSelectIcon(icon: string) {
  const normalized = normalizeLucideIconId(icon);
  manualInputValue.value = normalized;
  emit('update:value', normalized);
  popoverOpen.value = false;
  searchKeyword.value = '';
}

function onClear() {
  manualInputValue.value = '';
  emit('update:value', '');
}

function onManualInput(value: string) {
  manualInputValue.value = value;
}
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
                    manualInputValue === item.icon
                      ? 'border-primary bg-primary/10'
                      : ''
                  "
                  @click="onSelectIcon(item.icon)"
                >
                  <IconifyIcon
                    :icon="item.icon"
                    class="size-5 text-foreground/80"
                  />
                </button>
              </Tooltip>
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

          <div class="mt-3 border-t border-border pt-3">
            <div class="flex items-center gap-2">
              <Input
                :value="manualInputValue"
                :placeholder="props.placeholder"
                size="small"
                class="flex-1"
                @update:value="onManualInput"
              />
              <div
                v-if="manualInputValue"
                class="flex size-8 items-center justify-center rounded-lg bg-accent"
              >
                <IconifyIcon
                  :icon="selectedPreviewIcon"
                  class="size-5"
                  :class="
                    selectedPreviewIcon === 'lucide:circle-alert'
                      ? 'text-destructive'
                      : 'text-primary'
                  "
                />
              </div>
            </div>
          </div>
        </div>
      </template>

      <div
        class="flex h-9 w-full cursor-pointer items-stretch overflow-hidden rounded-lg border border-input bg-background text-sm transition-colors focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 hover:border-primary/50"
      >
        <div
          class="flex min-w-[36px] shrink-0 items-center justify-center border-r border-border bg-muted/30"
        >
          <IconifyIcon
            v-if="manualInputValue"
            :icon="selectedPreviewIcon"
            class="size-5"
            :class="
              selectedPreviewIcon === 'lucide:circle-alert'
                ? 'text-destructive'
                : 'text-primary'
            "
          />
          <IconifyIcon
            v-else
            icon="lucide:plus"
            class="size-5 text-muted-foreground transition-colors hover:text-primary"
          />
        </div>
        <input
          :value="manualInputValue"
          :placeholder="props.placeholder"
          readonly
          class="min-w-0 flex-1 cursor-pointer bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground"
        />
        <div
          v-if="manualInputValue"
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
