<script setup lang="ts">
import type { MenuRecordRaw } from '@vben/types';

import { computed, nextTick, onMounted, ref, shallowRef, watch } from 'vue';
import { useRouter } from 'vue-router';

import { CornerDownLeft, SearchX, X } from '@vben/icons';
import { $t } from '@vben/locales';
import { mapTree, traverseTreeValues, uniqueByField } from '@vben/utils';

import { VbenIcon } from '@vben-core/shadcn-ui';
import { isHttpUrl } from '@vben-core/shared/utils';

import DOMPurify from 'dompurify';
import { onKeyStroke, useLocalStorage, useThrottleFn } from '@vueuse/core';

defineOptions({
  name: 'SearchPanel',
});

const props = withDefaults(
  defineProps<{ keyword?: string; menus?: MenuRecordRaw[] }>(),
  {
    keyword: '',
    menus: () => [],
  },
);
const emit = defineEmits<{ close: [] }>();

const router = useRouter();
const searchHistory = useLocalStorage<MenuRecordRaw[]>(
  `__search-history-${location.hostname}__`,
  [],
);
const activeIndex = ref(-1);
const searchItems = shallowRef<MenuRecordRaw[]>([]);
const searchResults = ref<MenuRecordRaw[]>([]);
const pathToNameMap = new Map<string, string>();

const displayResults = computed(() =>
  uniqueByField(searchResults.value, 'path'),
);

function buildPathToNameMap(menus: MenuRecordRaw[]) {
  traverseTreeValues(menus, (item) => {
    pathToNameMap.set(item.path, item.name);
  });
}

function getParentBreadcrumb(item: MenuRecordRaw): string {
  if (!item.parents || item.parents.length === 0) {
    return item.parent ? (pathToNameMap.get(item.parent) || '') : '';
  }
  return item.parents
    .map((p) => pathToNameMap.get(p))
    .filter(Boolean)
    .join(' / ');
}

function highlightMatch(text: string, keyword: string): string {
  if (!keyword || !text) return text;
  const reg = createSearchReg(keyword);
  if (!reg.test(text.toLowerCase())) return text;
  let result = '';
  let ki = 0;
  const lowerKeyword = keyword.toLowerCase();
  for (const char of text) {
    if (ki < lowerKeyword.length && char.toLowerCase() === lowerKeyword[ki]) {
      result += `<span class="text-primary font-semibold">${char}</span>`;
      ki++;
    } else {
      result += char;
    }
  }
  return DOMPurify.sanitize(result);
}

const handleSearch = useThrottleFn(search, 200);

// 搜索函数，用于根据搜索关键词查找匹配的菜单项
function search(searchKey: string) {
  // 去除搜索关键词的前后空格
  searchKey = searchKey.trim();

  // 如果搜索关键词为空，清空搜索结果并返回
  if (!searchKey) {
    searchResults.value = [];
    return;
  }

  // 使用搜索关键词创建正则表达式
  const reg = createSearchReg(searchKey);

  // 初始化结果数组
  const results: MenuRecordRaw[] = [];

  // 遍历搜索项
  traverseTreeValues(searchItems.value, (item) => {
    // 如果菜单项的名称匹配正则表达式，将其添加到结果数组中
    if (reg.test(item.name?.toLowerCase())) {
      results.push(item);
    }
  });

  // 更新搜索结果
  searchResults.value = results;

  // 如果有搜索结果，设置索引为 0
  if (results.length > 0) {
    activeIndex.value = 0;
  }

  // 赋值索引为 0
  activeIndex.value = 0;
}

// When the keyboard up and down keys move to an invisible place
// the scroll bar needs to scroll automatically
function scrollIntoView() {
  const element = document.querySelector(
    `[data-search-item="${activeIndex.value}"]`,
  );

  if (element) {
    element.scrollIntoView({ block: 'nearest' });
  }
}

// enter keyboard event
async function handleEnter() {
  if (searchResults.value.length === 0) {
    return;
  }
  const result = searchResults.value;
  const index = activeIndex.value;
  if (result.length === 0 || index < 0) {
    return;
  }
  const to = result[index];
  if (to) {
    searchHistory.value = uniqueByField([...searchHistory.value, to], 'path');
    handleClose();
    await nextTick();
    if (isHttpUrl(to.path)) {
      window.open(to.path, '_blank');
    } else {
      router.push({ path: to.path, replace: true });
    }
  }
}

// Arrow key up
function handleUp() {
  if (searchResults.value.length === 0) {
    return;
  }
  activeIndex.value--;
  if (activeIndex.value < 0) {
    activeIndex.value = searchResults.value.length - 1;
  }
  scrollIntoView();
}

// Arrow key down
function handleDown() {
  if (searchResults.value.length === 0) {
    return;
  }
  activeIndex.value++;
  if (activeIndex.value > searchResults.value.length - 1) {
    activeIndex.value = 0;
  }
  scrollIntoView();
}

// close search modal
function handleClose() {
  searchResults.value = [];
  emit('close');
}

// Activate when the mouse moves to a certain line
function handleMouseenter(e: MouseEvent) {
  const index = (e.target as HTMLElement)?.dataset.index;
  activeIndex.value = Number(index);
}

function removeItem(index: number) {
  if (props.keyword) {
    searchResults.value.splice(index, 1);
  } else {
    searchHistory.value.splice(index, 1);
  }
  activeIndex.value = Math.max(activeIndex.value - 1, 0);
  scrollIntoView();
}

// 存储所有需要转义的特殊字符
const code = new Set([
  '$',
  '(',
  ')',
  '*',
  '+',
  '.',
  '?',
  '[',
  '\\',
  ']',
  '^',
  '{',
  '|',
  '}',
]);

// 转换函数，用于转义特殊字符
function transform(c: string) {
  // 如果字符在特殊字符列表中，返回转义后的字符
  // 如果不在，返回字符本身
  return code.has(c) ? `\\${c}` : c;
}

// 创建搜索正则表达式
function createSearchReg(key: string) {
  // 将输入的字符串拆分为单个字符
  // 对每个字符进行转义
  // 然后用'.*'连接所有字符，创建正则表达式
  const keys = [...key].map((item) => transform(item)).join('.*');
  // 返回创建的正则表达式
  return new RegExp(`.*${keys}.*`);
}

watch(
  () => props.keyword,
  (val) => {
    if (val) {
      handleSearch(val);
    } else {
      searchResults.value = [...searchHistory.value];
    }
  },
);

onMounted(() => {
  searchItems.value = mapTree(props.menus, (item) => {
    return {
      ...item,
      name: $t(item?.name),
    };
  });
  buildPathToNameMap(searchItems.value);
  if (searchHistory.value.length > 0) {
    searchResults.value = searchHistory.value;
  }
  onKeyStroke('Enter', handleEnter);
  onKeyStroke('ArrowUp', handleUp);
  onKeyStroke('ArrowDown', handleDown);
  onKeyStroke('Escape', handleClose);
});
</script>

<template>
  <div>
    <!-- Empty state: no keyword, no history -->
    <div v-if="!keyword && searchResults.length === 0" class="px-4 py-3">
      <div
        class="flex items-center gap-4 text-xs text-muted-foreground/70"
      >
        <span class="flex items-center gap-1">
          <kbd
            class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
          >Enter</kbd>
          {{ $t('ui.widgets.search.select') }}
        </span>
        <span class="flex items-center gap-1">
          <kbd
            class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
          >↑↓</kbd>
          {{ $t('ui.widgets.search.navigate') }}
        </span>
        <span class="flex items-center gap-1">
          <kbd
            class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
          >Esc</kbd>
          {{ $t('ui.widgets.search.close') }}
        </span>
      </div>
      <div class="mt-3 flex flex-col items-center justify-center border-t border-border/30 py-6">
        <SearchX class="text-muted-foreground/30 size-8" />
        <p class="text-muted-foreground/60 mt-2 text-sm">
          {{ $t('ui.widgets.search.noRecent') }}
        </p>
      </div>
    </div>

    <!-- No search results -->
    <div
      v-else-if="keyword && searchResults.length === 0"
      class="flex flex-col items-center justify-center py-10"
    >
      <SearchX class="text-muted-foreground/30 size-8" />
      <p class="text-muted-foreground mt-3 text-sm">
        {{ $t('ui.widgets.search.noResults') }}
      </p>
      <p class="text-muted-foreground/50 mt-1 text-xs">
        "{{ keyword }}"
      </p>
    </div>

    <!-- Results or History -->
    <template v-else-if="displayResults.length > 0">
      <div class="max-h-[300px] overflow-y-auto p-2">
        <!-- Section header -->
        <div
          v-if="!keyword && searchHistory.length > 0"
          class="mb-2 flex items-center gap-1.5 px-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60"
        >
          <CornerDownLeft class="size-3" />
          {{ $t('ui.widgets.search.recent') }}
        </div>
        <div
          v-else-if="keyword"
          class="mb-2 flex items-center justify-between px-2"
        >
          <span class="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
            {{ $t('ui.widgets.search.title') }}
          </span>
          <span class="text-[10px] tabular-nums text-muted-foreground/50">
            {{ $t('ui.widgets.search.resultsCount', { count: displayResults.length }) }}
          </span>
        </div>

        <!-- Result items -->
        <div class="space-y-0.5">
          <div
            v-for="(item, index) in displayResults"
            :key="item.path"
            :data-index="index"
            :data-search-item="index"
            class="group flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 transition-colors"
            :class="
              activeIndex === index
                ? 'bg-primary/10 text-primary'
                : 'text-foreground hover:bg-muted'
            "
            @click="handleEnter"
            @mouseenter="handleMouseenter"
          >
            <div
              class="flex size-8 shrink-0 items-center justify-center rounded-lg text-xs font-medium transition-colors"
              :class="
                activeIndex === index
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              "
            >
              <VbenIcon :icon="item.icon" class="size-4" fallback />
            </div>

            <div class="min-w-0 flex-1">
              <div
                class="truncate text-sm font-medium"
                v-html="keyword ? highlightMatch(item.name, keyword) : item.name"
              ></div>
              <div class="flex items-center gap-2">
                <span
                  v-if="getParentBreadcrumb(item)"
                  class="truncate text-xs text-muted-foreground/70"
                >
                  {{ getParentBreadcrumb(item) }}
                </span>
                <span
                  v-if="item.path && !isHttpUrl(item.path)"
                  class="shrink-0 truncate text-[10px] tabular-nums text-muted-foreground/40"
                >
                  {{ item.path }}
                </span>
              </div>
            </div>

            <div class="flex shrink-0 items-center gap-1">
              <CornerDownLeft
                v-if="activeIndex === index"
                class="text-primary size-3.5"
              />
              <div
                class="flex items-center justify-center rounded-full p-1 opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100"
                @click.stop="removeItem(index)"
              >
                <X class="text-muted-foreground size-3.5" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer hints (when results are showing) -->
      <div
        class="flex items-center gap-4 border-t border-border/40 px-4 py-2.5 text-xs text-muted-foreground/70"
      >
        <span class="flex items-center gap-1">
          <kbd
            class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
          >Enter</kbd>
          {{ $t('ui.widgets.search.select') }}
        </span>
        <span class="flex items-center gap-1">
          <kbd
            class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
          >↑↓</kbd>
          {{ $t('ui.widgets.search.navigate') }}
        </span>
        <span class="flex items-center gap-1">
          <kbd
            class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
          >Esc</kbd>
          {{ $t('ui.widgets.search.close') }}
        </span>
      </div>
    </template>
  </div>
</template>
