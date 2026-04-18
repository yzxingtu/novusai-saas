<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { prettyMonitoringPayload } from './monitoring-call-log-presentation';

defineOptions({ name: 'MonitoringCallLogRootCauseCard' });

defineProps<{
  loading: boolean;
  payload: null | Record<string, unknown>;
}>();

defineEmits<{ refresh: [] }>();
</script>

<template>
  <section
    class="mt-4 rounded-2xl border border-border/70 bg-card px-4 py-4 shadow-sm"
  >
    <div class="mb-2 flex items-center justify-between gap-2">
      <div
        class="flex items-center gap-2 text-sm font-semibold text-foreground"
      >
        <IconifyIcon icon="lucide:search-check" class="size-4 text-primary" />
        <span>Root Cause</span>
      </div>
      <button
        class="rounded-md border border-border/60 px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground"
        @click="$emit('refresh')"
      >
        Refresh
      </button>
    </div>
    <div v-if="loading" class="py-3 text-xs text-muted-foreground">
      Loading root cause...
    </div>
    <template v-else-if="payload">
      <div class="mb-2 grid grid-cols-1 gap-2 md:grid-cols-3">
        <div
          class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
        >
          <div class="text-[11px] text-muted-foreground">Status</div>
          <div class="mt-1 text-sm font-medium text-foreground">
            {{ String(payload.status || '-') }}
          </div>
        </div>
        <div
          class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
        >
          <div class="text-[11px] text-muted-foreground">Failure Layer</div>
          <div class="mt-1 text-sm font-medium text-foreground">
            {{ String(payload.failure_layer || '-') }}
          </div>
        </div>
        <div
          class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
        >
          <div class="text-[11px] text-muted-foreground">Cause Code</div>
          <div class="mt-1 text-sm font-medium text-foreground">
            {{ String(payload.cause_code || '-') }}
          </div>
        </div>
      </div>
      <pre
        class="max-h-72 overflow-auto rounded-xl border border-border/60 bg-accent/30 p-3 font-mono text-xs leading-5"
        >{{ prettyMonitoringPayload(payload) }}</pre
      >
    </template>
    <div v-else class="py-3 text-xs text-muted-foreground">
      Root cause report is unavailable for this call log.
    </div>
  </section>
</template>
