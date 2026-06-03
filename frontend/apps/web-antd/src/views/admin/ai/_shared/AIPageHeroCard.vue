<script lang="ts" setup>
import { computed, useSlots } from 'vue';

import { IconifyIcon } from '@vben/icons';

interface HeroChip {
  className?: string;
  icon?: string;
  key: string;
  text: string;
}

interface HeroMetric {
  key: string;
  label: string;
  value: number | string;
}

const props = withDefaults(
  defineProps<{
    chips?: HeroChip[];
    description?: string;
    icon?: string;
    iconClass?: string;
    iconWrapClass?: string;
    metrics?: HeroMetric[];
    title: string;
  }>(),
  {
    chips: () => [],
    description: '',
    icon: 'lucide:sparkles',
    iconClass: 'text-primary',
    iconWrapClass: 'bg-primary/10 text-primary',
    metrics: () => [],
  },
);

const slots = useSlots();

const hasAside = computed(() => {
  return props.metrics.length > 0 || Boolean(slots.actions);
});
</script>

<template>
  <section
    class="rounded-[20px] border border-border/70 bg-card px-4 py-3 shadow-sm"
  >
    <div
      class="flex flex-col gap-3 2xl:flex-row 2xl:items-start 2xl:justify-between"
    >
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="flex size-8 items-center justify-center rounded-xl"
            :class="iconWrapClass"
          >
            <IconifyIcon :icon="icon" class="size-4" :class="iconClass" />
          </span>
          <h1 class="text-base font-semibold text-foreground">
            {{ title }}
          </h1>
          <span
            v-if="description"
            class="hidden text-xs text-muted-foreground xl:inline"
          >
            {{ description }}
          </span>
        </div>

        <div v-if="chips.length > 0" class="mt-2 flex flex-wrap gap-2">
          <span
            v-for="chip in chips"
            :key="chip.key"
            class="inline-flex max-w-full items-center gap-2 rounded-full border border-transparent px-2.5 py-1 text-xs"
            :class="chip.className || 'bg-background/90 text-foreground'"
          >
            <IconifyIcon
              v-if="chip.icon"
              :icon="chip.icon"
              class="size-3.5 flex-shrink-0"
            />
            <span class="max-w-[320px] truncate">{{ chip.text }}</span>
          </span>
        </div>
      </div>

      <div
        v-if="hasAside"
        class="flex flex-col gap-3 2xl:min-w-[220px] 2xl:items-end"
      >
        <div v-if="metrics.length > 0" class="flex flex-wrap gap-2">
          <span
            v-for="metric in metrics"
            :key="metric.key"
            class="rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs text-muted-foreground"
          >
            <span class="mr-1 font-semibold text-foreground">
              {{ metric.value }}
            </span>
            {{ metric.label }}
          </span>
        </div>
        <div
          v-if="$slots.actions"
          class="flex flex-wrap items-center gap-2 2xl:justify-end"
        >
          <slot name="actions"></slot>
        </div>
      </div>
    </div>
  </section>
</template>
