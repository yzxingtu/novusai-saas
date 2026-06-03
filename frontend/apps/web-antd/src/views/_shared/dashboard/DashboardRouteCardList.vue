<script lang="ts" setup>
import type { DashboardRouteCardItem } from './types';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

const props = withDefaults(
  defineProps<{
    columns?: 1 | 2;
    items: DashboardRouteCardItem[];
    variant?: 'action' | 'signal';
  }>(),
  {
    columns: 1,
    variant: 'action',
  },
);

const emit = defineEmits<{
  select: [route: string];
}>();

const arrowIcon = computed(() =>
  props.variant === 'signal' ? 'lucide:arrow-up-right' : 'lucide:arrow-right',
);

const listClass = computed(() =>
  props.columns === 2 ? 'mt-5 grid gap-3 lg:grid-cols-2' : 'mt-5 grid gap-3',
);
</script>

<template>
  <div :class="listClass">
    <button
      v-for="item in items"
      :key="item.key"
      class="group flex w-full items-start gap-3 rounded-[22px] border border-border/60 bg-background/80 px-4 py-4 text-left transition-all hover:border-primary/25 hover:bg-primary/5"
      type="button"
      @click="emit('select', item.route)"
    >
      <span
        class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
      >
        <IconifyIcon :icon="item.icon" class="size-4.5" />
      </span>
      <span class="min-w-0 flex-1">
        <template v-if="variant === 'signal'">
          <span
            class="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground"
          >
            {{ item.title }}
          </span>
          <span class="mt-2 block text-lg font-semibold text-foreground">
            {{ item.value }}
          </span>
        </template>
        <template v-else>
          <span class="block text-base font-semibold text-foreground">
            {{ item.title }}
          </span>
        </template>
        <span class="mt-2 block text-sm leading-6 text-muted-foreground">
          {{ item.description }}
        </span>
      </span>
      <IconifyIcon
        :icon="arrowIcon"
        class="mt-1 size-4 shrink-0 text-muted-foreground transition-all group-hover:text-primary"
        :class="
          variant === 'signal'
            ? 'transition-colors'
            : 'transition-transform group-hover:translate-x-0.5'
        "
      />
    </button>
  </div>
</template>
