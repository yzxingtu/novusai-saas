<script lang="ts" setup>
import type { DashboardMetricCard } from './types';

import { IconifyIcon } from '@vben/icons';

defineProps<{
  items: DashboardMetricCard[];
}>();
</script>

<template>
  <div class="grid gap-3 sm:grid-cols-2">
    <div
      v-for="card in items"
      :key="card.key"
      class="rounded-[24px] border border-border/60 bg-background/90 p-4 shadow-sm"
    >
      <div class="flex items-center justify-between">
        <span
          class="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary"
        >
          <IconifyIcon :icon="card.icon" class="size-4.5" />
        </span>
        <span class="text-3xl font-semibold tracking-tight text-foreground">
          {{ card.value }}
        </span>
      </div>
      <div class="mt-4 text-sm text-muted-foreground">
        {{ card.label }}
      </div>
    </div>
  </div>
</template>
