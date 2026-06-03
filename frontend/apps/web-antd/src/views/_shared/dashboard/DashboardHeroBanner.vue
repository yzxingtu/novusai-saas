<script lang="ts" setup>
import type {
  DashboardChip,
  DashboardHeroAction,
  DashboardMetricCard,
} from './types';

import { IconifyIcon } from '@vben/icons';

import DashboardMetricCards from './DashboardMetricCards.vue';

withDefaults(
  defineProps<{
    actions?: DashboardHeroAction[];
    badge: string;
    badgeDotClass?: string;
    badgeIcon?: string;
    chips: DashboardChip[];
    description: string;
    metrics: DashboardMetricCard[];
    primaryGlowClass?: string;
    secondaryGlowClass?: string;
    title: string;
  }>(),
  {
    actions: () => [],
    badgeDotClass: 'bg-primary',
    badgeIcon: undefined,
    primaryGlowClass: 'bg-primary/10',
    secondaryGlowClass: 'bg-sky-500/10',
  },
);

const emit = defineEmits<{
  select: [route: string];
}>();

function getActionClass(variant: DashboardHeroAction['variant']) {
  if (variant === 'secondary') {
    return 'border border-border/70 bg-background/90 text-foreground hover:border-primary/25 hover:text-primary';
  }
  return 'bg-primary text-primary-foreground shadow-lg shadow-primary/15 hover:shadow-xl hover:shadow-primary/20';
}
</script>

<template>
  <section
    class="relative overflow-hidden rounded-[32px] border border-border/70 bg-card px-6 py-7 shadow-sm sm:px-8"
  >
    <div
      class="absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent"
    ></div>
    <div
      class="absolute -right-24 top-0 size-72 rounded-full blur-3xl"
      :class="primaryGlowClass"
    ></div>
    <div
      class="absolute left-0 top-1/2 size-60 -translate-y-1/2 rounded-full blur-3xl"
      :class="secondaryGlowClass"
    ></div>

    <div class="relative space-y-6">
      <div
        class="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]"
      >
        <div class="space-y-5">
          <div
            class="bg-primary/8 inline-flex items-center gap-2 rounded-full border border-primary/20 px-3 py-1 text-xs font-medium text-primary"
          >
            <IconifyIcon v-if="badgeIcon" :icon="badgeIcon" class="size-3.5" />
            <span
              v-else
              class="size-2 rounded-full"
              :class="badgeDotClass"
            ></span>
            {{ badge }}
          </div>
          <div>
            <h1
              class="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
            >
              {{ title }}
            </h1>
            <p
              class="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base"
            >
              {{ description }}
            </p>
          </div>

          <div v-if="actions.length > 0" class="flex flex-wrap gap-3">
            <button
              v-for="action in actions"
              :key="action.key"
              class="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium transition-all hover:scale-[1.01]"
              :class="getActionClass(action.variant)"
              type="button"
              @click="emit('select', action.route)"
            >
              <IconifyIcon
                v-if="action.icon"
                :icon="action.icon"
                class="size-4"
              />
              {{ action.label }}
            </button>
          </div>

          <div class="flex flex-wrap gap-3 text-sm">
            <span
              v-for="chip in chips"
              :key="chip.key"
              class="inline-flex items-center gap-2 rounded-full border px-3 py-2"
              :class="[chip.border, chip.badge]"
            >
              <IconifyIcon :icon="chip.icon" class="size-4" />
              {{ chip.text }}
            </span>
          </div>
        </div>

        <DashboardMetricCards :items="metrics" />
      </div>

      <slot name="footer"></slot>
    </div>
  </section>
</template>
