<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

defineProps<{
  description: string;
  icon: string;
  title: string;
}>();
</script>

<template>
  <div class="flex items-center gap-3">
    <span
      class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
    >
      <IconifyIcon :icon="icon" class="size-5" />
    </span>
    <div>
      <h2 class="text-xl font-semibold text-foreground">
        {{ title }}
      </h2>
      <p class="mt-1 text-sm text-muted-foreground">
        {{ description }}
      </p>
    </div>
  </div>
</template>
