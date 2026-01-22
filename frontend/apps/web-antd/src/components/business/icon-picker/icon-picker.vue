<!-- eslint-disable vue/html-closing-bracket-newline -->
<script lang="ts" setup>
import type { IconCategory } from './icons-data';

/**
 * 图标选择器组件
 * 支持 Lucide 图标和项目自定义 SVG 图标
 * 使用 @iconify/vue 的 Icon 组件动态渲染，无需逐个引入
 * 使用虚拟滚动优化大量图标的渲染性能
 */
import { computed, nextTick, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { useVirtualList } from '@vueuse/core';
import { Input, message, Modal, Segmented, Tooltip } from 'ant-design-vue';

import { copyToClipboard } from '#/utils/common';

import {
  ALL_CATEGORIES,
  ALL_ICONS_WITH_PREFIX,
  getFullIconName,
} from './icons-data';
import { setupIconPickerIcons } from './setup-icons';

defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  select: [icon: string];
  'update:open': [value: boolean];
}>();

// 预加载 Lucide 图标集，确保图标能够离线显示
setupIconPickerIcons();

// 搜索关键词
const searchKeyword = ref('');
// 当前分类
const activeCategory = ref('all');

// 虚拟滚动配置
const ICONS_PER_ROW = 9;
// 每行高度（88px 图标高度 + 8px 间距）
const ITEM_HEIGHT = 96;

// 计算总图标数
const totalIconCount = computed(() => ALL_ICONS_WITH_PREFIX.length);

// 分类选项
const categoryOptions = computed(() => [
  { label: `全部 (${totalIconCount.value})`, value: 'all' },
  ...ALL_CATEGORIES.map((cat) => ({
    label: `${cat.label} (${cat.icons.length})`,
    value: cat.name,
  })),
]);

interface IconItem {
  key: string; // 唯一 key，使用 category-iconName 格式
  name: string;
  fullName: string;
  prefix: string;
}

// 过滤后的图标列表（带唯一 key，避免重复）
const filteredIcons = computed(() => {
  const result: IconItem[] = [];

  // 根据分类筛选
  if (activeCategory.value === 'all') {
    // 所有分类 - 使用 category-icon 作为唯一 key
    for (const cat of ALL_CATEGORIES) {
      for (const icon of cat.icons) {
        result.push({
          key: `${cat.name}-${icon}`, // 唯一 key
          name: icon,
          fullName: getFullIconName(icon, cat.prefix),
          prefix: cat.prefix,
        });
      }
    }
  } else {
    const category = ALL_CATEGORIES.find(
      (c) => c.name === activeCategory.value,
    ) as IconCategory | undefined;
    if (category) {
      for (const icon of category.icons) {
        result.push({
          key: `${category.name}-${icon}`,
          name: icon,
          fullName: getFullIconName(icon, category.prefix),
          prefix: category.prefix,
        });
      }
    }
  }

  // 根据搜索关键词筛选
  if (searchKeyword.value.trim()) {
    const keyword = searchKeyword.value.toLowerCase().trim();
    return result.filter((item) => item.name.includes(keyword));
  }

  return result;
});

// 将图标列表按行分组（用于虚拟滚动）
const iconRows = computed(() => {
  const rows: IconItem[][] = [];
  const icons = filteredIcons.value;
  for (let i = 0; i < icons.length; i += ICONS_PER_ROW) {
    rows.push(icons.slice(i, i + ICONS_PER_ROW));
  }
  return rows;
});

// 虚拟滚动
const {
  list: virtualRows,
  containerProps,
  wrapperProps,
} = useVirtualList(iconRows, {
  itemHeight: ITEM_HEIGHT,
  overscan: 3, // 额外渲染的行数
});

// 监听分类/搜索变化，重置滚动位置
watch([activeCategory, searchKeyword], () => {
  nextTick(() => {
    if (containerProps.ref.value) {
      containerProps.ref.value.scrollTop = 0;
    }
  });
});

// 选中图标
function onSelectIcon(fullName: string) {
  emit('select', fullName);
}

// 复制图标名称
async function onCopyIcon(fullName: string, event: Event) {
  event.stopPropagation();
  const success = await copyToClipboard(fullName);
  if (success) {
    message.success(`已复制: ${fullName}`);
  } else {
    message.error('复制失败');
  }
}

// 关闭弹窗
function onClose() {
  emit('update:open', false);
  // 重置搜索
  searchKeyword.value = '';
  activeCategory.value = 'all';
}
</script>

<template>
  <Modal
    :open="open"
    title="图标选择器"
    width="960px"
    :footer="null"
    centered
    @cancel="onClose"
  >
    <div class="flex flex-col gap-4">
      <!-- 搜索框 -->
      <Input
        v-model:value="searchKeyword"
        placeholder="搜索图标名称，如: user, arrow, check, avatar..."
        allow-clear
        size="large"
      >
        <template #prefix>
          <IconifyIcon icon="lucide:search" class="text-gray-400" />
        </template>
      </Input>

      <!-- 分类选择 -->
      <div class="overflow-x-auto pb-2">
        <Segmented
          v-model:value="activeCategory"
          :options="categoryOptions"
          size="small"
        />
      </div>

      <!-- 图标统计 -->
      <div
        class="flex items-center justify-between text-sm text-muted-foreground"
      >
        <span>
          共 {{ filteredIcons.length }} 个图标
          <span v-if="searchKeyword" class="ml-1">
            (搜索: "{{ searchKeyword }}")
          </span>
        </span>
        <span class="text-xs">
          <span class="mr-3 inline-flex items-center gap-1">
            <span class="size-2 rounded-full bg-success"></span>
            项目图标 (svg:)
          </span>
          <span class="inline-flex items-center gap-1">
            <span class="size-2 rounded-full bg-primary"></span>
            Lucide (lucide:)
          </span>
        </span>
      </div>

      <!-- 图标网格 (虚拟滚动) -->
      <div
        v-if="filteredIcons.length === 0"
        class="flex h-[420px] items-center justify-center rounded-lg border border-gray-200 bg-gray-50/50 text-gray-400 dark:border-gray-700 dark:bg-gray-800/50"
      >
        <div class="text-center">
          <IconifyIcon icon="lucide:search-x" class="mb-2 size-12" />
          <p>没有找到匹配的图标</p>
        </div>
      </div>
      <div
        v-else
        v-bind="containerProps"
        class="h-[420px] overflow-y-auto rounded-lg border border-gray-200 bg-gray-50/50 p-3 dark:border-gray-700 dark:bg-gray-800/50"
      >
        <div v-bind="wrapperProps">
          <div
            v-for="{ index, data: row } in virtualRows"
            :key="index"
            class="grid gap-2"
            style="grid-template-columns: repeat(9, 96px); margin-bottom: 8px"
          >
            <Tooltip
              v-for="item in row"
              :key="item.key"
              :title="item.fullName"
              placement="top"
            >
              <div
                class="group relative flex h-[88px] w-[96px] cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border bg-card p-2 transition-[border-color,box-shadow] duration-150 hover:shadow-md"
                :class="[
                  item.prefix === 'svg'
                    ? 'border-success/30 hover:border-success/60'
                    : 'border-border hover:border-primary/30',
                ]"
                @click="onSelectIcon(item.fullName)"
              >
                <!-- 前缀标记 -->
                <span
                  v-if="activeCategory === 'all'"
                  class="absolute left-1 top-1 rounded px-1 text-[8px] font-medium"
                  :class="[
                    item.prefix === 'svg'
                      ? 'bg-success/10 text-success'
                      : 'bg-primary/10 text-primary',
                  ]"
                >
                  {{ item.prefix }}
                </span>
                <IconifyIcon
                  :icon="item.fullName"
                  class="size-7 text-gray-700 transition-transform duration-150 group-hover:scale-110 group-hover:text-primary dark:text-gray-300"
                />
                <span
                  class="w-full truncate text-center text-[10px] leading-tight text-gray-500 dark:text-gray-400"
                >
                  {{ item.name }}
                </span>
                <!-- 复制按钮 -->
                <button
                  class="absolute right-1 top-1 rounded p-0.5 opacity-0 transition-opacity duration-150 hover:bg-gray-100 group-hover:opacity-100 dark:hover:bg-gray-700"
                  title="复制图标名称"
                  @click="onCopyIcon(item.fullName, $event)"
                >
                  <IconifyIcon
                    icon="lucide:copy"
                    class="size-3.5 text-gray-400"
                  />
                </button>
              </div>
            </Tooltip>
          </div>
        </div>
      </div>

      <!-- 使用说明开关 -->
      <details
        class="group rounded-lg border border-gray-200 dark:border-gray-700"
      >
        <summary
          class="flex cursor-pointer items-center gap-2 rounded-lg bg-gray-50 px-4 py-2.5 text-sm font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300"
        >
          <IconifyIcon icon="lucide:book-open" class="size-4" />
          图标使用指南
          <IconifyIcon
            icon="lucide:chevron-right"
            class="ml-auto size-4 transition-transform group-open:rotate-90"
          />
        </summary>
        <div class="space-y-3 p-4">
          <!-- Lucide 图标 -->
          <div class="rounded-lg bg-primary/5 p-3">
            <p class="mb-2 text-sm font-medium text-primary">
              ✅ Lucide 图标（已预加载，离线可用）
            </p>
            <div class="space-y-2 text-xs text-muted-foreground">
              <p>点击图标复制名称后直接使用：</p>
              <div class="rounded bg-muted p-2">
                <code class="block text-foreground"
                  >&lt;IconifyIcon icon="lucide:user" class="size-5" /&gt;</code
                >
              </div>
              <p>Lucide 图标已全部预加载，无需联网。</p>
            </div>
          </div>

          <!-- Tailwind CSS 图标类 -->
          <div class="rounded-lg bg-accent/50 p-3">
            <p class="mb-2 text-sm font-medium text-accent-foreground">
              ✅ Tailwind CSS 图标类（离线可用）
            </p>
            <div class="space-y-1.5 text-xs text-muted-foreground">
              <div class="rounded bg-muted p-2">
                <code class="block text-foreground"
                  >&lt;span class="icon-[lucide--user] size-5" /&gt;</code
                >
                <code class="block text-foreground"
                  >&lt;span class="icon-[tabler--home] size-5" /&gt;</code
                >
              </div>
              <p>
                格式：<code class="text-primary">icon-[图标集--图标名]</code
                >，用 <code class="text-primary">--</code> 代替
                <code class="text-primary">:</code>
              </p>
            </div>
          </div>

          <!-- 自定义 SVG -->
          <div class="rounded-lg bg-success/5 p-3">
            <p class="mb-2 text-sm font-medium text-success">
              自定义 SVG / iconfont
            </p>
            <div class="space-y-1.5 text-xs text-muted-foreground">
              <p>
                将 SVG 放入
                <code class="text-success">packages/icons/src/svg/icons/</code>
                自动注册：
              </p>
              <div class="rounded bg-muted p-2">
                <code class="block text-foreground"
                  >// my-icon.svg → svg:my-icon</code
                >
                <code class="block text-foreground"
                  >&lt;IconifyIcon icon="svg:my-icon" /&gt;</code
                >
              </div>
              <p>
                支持从
                <a
                  href="https://www.iconfont.cn"
                  target="_blank"
                  class="text-primary underline"
                  >iconfont.cn</a
                >
                下载的 SVG
              </p>
            </div>
          </div>

          <!-- 其他图标集 -->
          <div class="rounded-lg bg-muted/50 p-3">
            <p class="mb-2 text-sm font-medium text-foreground">
              其他 Iconify 图标集（需联网）
            </p>
            <div class="space-y-1.5 text-xs text-muted-foreground">
              <div class="grid grid-cols-3 gap-1 text-[11px]">
                <span
                  ><code class="text-foreground/70">tabler:</code> Tabler</span
                >
                <span
                  ><code class="text-foreground/70">mdi:</code> Material
                  Design</span
                >
                <span
                  ><code class="text-foreground/70">ant-design:</code> Ant
                  Design</span
                >
                <span
                  ><code class="text-foreground/70">carbon:</code> Carbon</span
                >
                <span
                  ><code class="text-foreground/70">ph:</code> Phosphor</span
                >
                <span
                  ><code class="text-foreground/70">ri:</code> Remix Icon</span
                >
              </div>
              <p>
                非 Lucide 图标首次使用需联网加载，或使用 Tailwind
                类方式离线使用。
              </p>
            </div>
          </div>

          <!-- 参考链接 -->
          <div class="flex flex-wrap gap-3 text-xs text-muted-foreground">
            <a
              href="https://lucide.dev/icons"
              target="_blank"
              class="text-primary underline"
              >Lucide</a
            >
            <a
              href="https://icon-sets.iconify.design"
              target="_blank"
              class="text-primary/80 underline"
              >Iconify 图标集</a
            >
            <a
              href="https://www.iconfont.cn"
              target="_blank"
              class="text-primary/80 underline"
              >iconfont.cn</a
            >
          </div>
        </div>
      </details>
    </div>
  </Modal>
</template>

<style scoped>
.group {
  position: relative;
}
</style>
