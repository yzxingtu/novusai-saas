<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Skeleton } from 'ant-design-vue';

import { $t as t } from '#/locales';

import { useSystemLogsContext } from '../composables/useSystemLogs';

const {
  activeCategory,
  categories,
  getCategoryVisual,
  loading,
  onCategorySelect,
} = useSystemLogsContext();

const skeletonPlaceholders = computed(() =>
  Array.from({ length: 4 }, (_, i) => i + 1),
);
</script>

<template>
  <section
    class="rounded-[20px] border border-border/70 bg-card px-3 py-3 shadow-sm"
  >
    <div
      class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"
    >
      <div class="flex items-center gap-2">
        <span class="text-sm font-medium text-foreground">
          {{ t('admin.system.systemLog.categories') }}
        </span>
        <span class="text-xs text-muted-foreground">
          {{ categories.length }}
        </span>
      </div>

      <div
        v-if="loading && categories.length === 0"
        class="grid w-full gap-2 sm:grid-cols-2 xl:max-w-[720px] xl:grid-cols-4"
      >
        <div
          v-for="item in skeletonPlaceholders"
          :key="item"
          class="rounded-xl border border-border/60 bg-background/80 px-3 py-2"
        >
          <Skeleton active :paragraph="{ rows: 1 }" :title="false" />
        </div>
      </div>

      <div
        v-else
        class="flex gap-2 overflow-x-auto pb-1 xl:flex-wrap xl:justify-end xl:overflow-visible xl:pb-0"
      >
        <button
          v-for="category in categories"
          :key="category.code"
          type="button"
          class="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border px-3 text-left text-sm transition-all"
          :class="
            category.code === activeCategory
              ? `${getCategoryVisual(category.code).activeCard} shadow-sm`
              : 'border-border/60 bg-background/80 hover:border-primary/20 hover:bg-accent/40'
          "
          @click="onCategorySelect(category.code)"
        >
          <span
            class="flex size-7 items-center justify-center rounded-lg"
            :class="getCategoryVisual(category.code).iconWrap"
          >
            <IconifyIcon
              :icon="getCategoryVisual(category.code).icon"
              class="size-3.5"
            />
          </span>
          <span class="font-medium text-foreground">{{ category.name }}</span>
          <span class="text-xs text-muted-foreground">{{
            category.fileCount
          }}</span>
        </button>
      </div>
    </div>
  </section>
</template>
