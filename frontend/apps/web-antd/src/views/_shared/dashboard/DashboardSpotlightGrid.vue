<script lang="ts" setup>
import type { DashboardSpotlightItem } from './types';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

const props = defineProps<{
  items: DashboardSpotlightItem[];
}>();

function getToneClass(tone?: DashboardSpotlightItem['tone']) {
  switch (tone) {
    case 'positive': {
      return {
        accent: 'bg-emerald-500/12 text-emerald-700 dark:text-emerald-300',
        border: 'border-emerald-500/20',
      };
    }
    case 'warning': {
      return {
        accent: 'bg-amber-500/12 text-amber-700 dark:text-amber-300',
        border: 'border-amber-500/20',
      };
    }
    default: {
      return {
        accent: 'bg-background/90 text-foreground',
        border: 'border-border/60',
      };
    }
  }
}

const gridClass = computed(() =>
  props.items.length >= 4
    ? 'grid gap-3 lg:grid-cols-4 sm:grid-cols-2'
    : 'grid gap-3 lg:grid-cols-3 sm:grid-cols-2',
);
</script>

<template>
  <div :class="gridClass">
    <div
      v-for="item in items"
      :key="item.key"
      class="rounded-[24px] border bg-background/80 p-4"
      :class="getToneClass(item.tone).border"
    >
      <div class="flex items-start justify-between gap-3">
        <span
          class="flex size-10 items-center justify-center rounded-2xl"
          :class="getToneClass(item.tone).accent"
        >
          <IconifyIcon :icon="item.icon" class="size-4.5" />
        </span>
        <div class="text-right">
          <div class="text-2xl font-semibold tracking-tight text-foreground">
            {{ item.value }}
          </div>
          <div
            v-if="item.detail"
            class="mt-1 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground"
          >
            {{ item.detail }}
          </div>
        </div>
      </div>
      <div class="mt-4 text-sm text-muted-foreground">
        {{ item.label }}
      </div>
    </div>
  </div>
</template>
