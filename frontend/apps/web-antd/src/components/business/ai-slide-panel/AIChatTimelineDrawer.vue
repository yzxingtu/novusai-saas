<script lang="ts" setup>
import type { ConversationTimelineItem } from '#/api/shared/ai-chat';

import { Drawer, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatTimelineDrawer' });

const props = defineProps<{
  items: ConversationTimelineItem[];
  loading: boolean;
  open: boolean;
  refreshing: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
  'update:open': [value: boolean];
}>();
</script>

<template>
  <Drawer
    :open="props.open"
    :title="$t('common.globalAiChat.runTimeline')"
    width="640"
    @update:open="(value: boolean) => emit('update:open', value)"
  >
    <div class="mb-3 flex justify-end">
      <button
        type="button"
        class="rounded-lg border border-border px-3 py-1 text-xs text-foreground"
        @click="emit('refresh')"
      >
        {{ props.refreshing ? $t('common.loading') : $t('common.refresh') }}
      </button>
    </div>
    <div v-if="props.loading" class="flex justify-center py-10">
      <Spin />
    </div>
    <div
      v-else-if="props.items.length === 0"
      class="text-sm text-muted-foreground"
    >
      {{ $t('common.noData') }}
    </div>
    <div v-else class="space-y-3">
      <div
        v-for="(item, index) in props.items"
        :key="`${item.type}-${item.occurred_at || index}`"
        class="rounded-2xl border border-border/60 bg-muted/10 p-3"
      >
        <div class="flex items-center justify-between gap-3">
          <div class="text-sm font-semibold text-foreground">
            {{ item.title || item.type }}
          </div>
          <div class="text-[11px] text-muted-foreground">
            {{ item.occurred_at }}
          </div>
        </div>
        <div class="mt-1 text-xs text-muted-foreground">
          {{ item.summary || item.status }}
        </div>
        <pre
          v-if="item.detail_payload"
          class="mt-2 overflow-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-foreground"
          >{{ JSON.stringify(item.detail_payload, null, 2) }}</pre
        >
      </div>
    </div>
  </Drawer>
</template>
