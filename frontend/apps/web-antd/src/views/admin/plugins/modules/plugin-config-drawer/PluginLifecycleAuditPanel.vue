<script setup lang="ts">
import type { PluginLifecycleAuditReport } from '#/api/admin/plugin';

import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

const props = defineProps<{
  loading: boolean;
  onRefresh: (pluginId: number) => Promise<void> | void;
  payload: null | PluginLifecycleAuditReport;
  pluginId: number;
  prettyJson: (value: unknown) => string;
}>();
</script>

<template>
  <div class="mb-6 rounded-lg border border-border/60 p-4">
    <div class="mb-2 flex items-center justify-between gap-2">
      <h4 class="text-sm font-medium">
        {{ $t('admin.plugin.lifecycleAudit.title') }}
      </h4>
      <Button
        size="small"
        :loading="props.loading"
        @click="props.onRefresh(props.pluginId)"
      >
        <IconifyIcon icon="lucide:refresh-cw" class="mr-1.5 size-3.5" />
        {{ $t('admin.plugin.lifecycleAudit.refresh') }}
      </Button>
    </div>
    <div v-if="props.loading" class="text-xs text-muted-foreground">
      {{ $t('admin.plugin.lifecycleAudit.loading') }}
    </div>
    <template v-else-if="props.payload">
      <div class="mb-3 grid grid-cols-1 gap-2 md:grid-cols-2">
        <div
          class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
        >
          <div class="text-[11px] text-muted-foreground">
            {{ $t('admin.plugin.lifecycleAudit.runtimeKind') }}
          </div>
          <div class="mt-1 text-sm font-medium text-foreground">
            {{ String(props.payload.runtime_kind || '-') }}
          </div>
        </div>
        <div
          class="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
        >
          <div class="text-[11px] text-muted-foreground">
            {{ $t('admin.plugin.lifecycleAudit.degradedReason') }}
          </div>
          <div class="mt-1 text-sm font-medium text-foreground">
            {{ String(props.payload.degraded_reason || '-') }}
          </div>
        </div>
      </div>
      <pre
        class="max-h-56 overflow-auto rounded-lg border border-border/60 bg-accent/30 p-3 font-mono text-xs leading-5"
        >{{ props.prettyJson(props.payload) }}</pre
      >
    </template>
    <div v-else class="text-xs text-muted-foreground">
      {{ $t('admin.plugin.lifecycleAudit.unavailable') }}
    </div>
  </div>
</template>
