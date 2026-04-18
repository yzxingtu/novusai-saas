<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { prettyMonitoringPayload } from './monitoring-call-log-presentation';

defineOptions({ name: 'MonitoringCallLogPayloadCard' });

defineProps<{
  icon: string;
  payload: null | Record<string, unknown> | undefined;
  title: string;
}>();
</script>

<template>
  <article class="rounded-2xl border border-border/70 bg-card p-4 shadow-sm">
    <div
      class="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground"
    >
      <IconifyIcon :icon="icon" class="size-4 text-primary" />
      <span>{{ title }}</span>
    </div>
    <pre
      class="max-h-96 overflow-auto rounded-xl border border-border/60 bg-accent/30 p-3 font-mono text-xs leading-5"
      >{{ prettyMonitoringPayload(payload) }}</pre
    >
  </article>
</template>
