<script lang="ts" setup>
import type { DashboardSummaryPanel } from './types';

import { IconifyIcon } from '@vben/icons';

defineProps<{
  items: DashboardSummaryPanel[];
}>();
</script>

<template>
  <div class="mt-5 grid gap-3 sm:grid-cols-2">
    <div
      v-for="panel in items"
      :key="panel.key"
      class="rounded-[22px] border border-border/60 bg-background/80 p-4"
    >
      <div class="flex items-center gap-3">
        <span
          class="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary"
        >
          <IconifyIcon :icon="panel.icon" class="size-4.5" />
        </span>
        <h3 class="text-base font-semibold text-foreground">
          {{ panel.title }}
        </h3>
      </div>
      <div class="mt-4 space-y-3">
        <div
          v-for="row in panel.rows"
          :key="row.label"
          class="flex items-center justify-between gap-3 text-sm"
        >
          <span class="text-muted-foreground">{{ row.label }}</span>
          <span class="font-medium text-foreground">{{ row.value }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
