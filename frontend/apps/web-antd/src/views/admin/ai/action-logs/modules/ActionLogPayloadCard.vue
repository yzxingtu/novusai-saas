<script lang="ts" setup>
import type { PayloadEntry } from '../action-log-detail-helpers';

import { Button, Card, Empty, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

import { formatPayloadSize } from '../action-log-detail-helpers';

defineOptions({ name: 'ActionLogPayloadCard' });

defineProps<{
  copyPayload: (text: string) => Promise<void>;
  emptyDescription: string;
  entries: PayloadEntry[];
  payloadText: string;
  title: string;
}>();
</script>

<template>
  <Card size="small" :title="title">
    <template #extra>
      <div class="flex items-center gap-2">
        <Tag>
          {{ $t('admin.ai.actionLog.fieldsCount', { count: entries.length }) }}
        </Tag>
        <Tag>{{ formatPayloadSize(payloadText) }}</Tag>
        <Button size="small" type="text" @click="copyPayload(payloadText)">
          {{ $t('admin.ai.actionLog.copyPayload') }}
        </Button>
      </div>
    </template>

    <div v-if="entries.length > 0" class="space-y-3">
      <div
        v-for="entry in entries"
        :key="entry.key"
        class="rounded-lg border border-border bg-background p-3"
      >
        <div class="mb-2 flex items-center justify-between gap-2">
          <span class="text-sm font-medium">{{ entry.key }}</span>
          <Tag v-if="entry.kind === 'json'">JSON</Tag>
        </div>

        <pre
          v-if="entry.kind === 'json'"
          class="m-0 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded bg-accent/60 p-3 text-xs"
          >{{ entry.valueText }}</pre
        >
        <code
          v-else
          class="block break-all rounded bg-accent/60 px-2 py-2 text-xs"
          >{{ entry.valueText }}</code
        >
      </div>
    </div>

    <Empty v-else :description="emptyDescription" />
  </Card>
</template>
