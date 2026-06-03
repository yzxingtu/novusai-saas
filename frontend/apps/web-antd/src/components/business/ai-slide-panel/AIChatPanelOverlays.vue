<script lang="ts" setup>
import type { ConversationTimelineItem } from '#/api/shared/ai-chat';

import { Image } from 'ant-design-vue';

import AIChatContextDiagnosticsDrawer from './AIChatContextDiagnosticsDrawer.vue';
import AIChatPanelMinimizedBubble from './AIChatPanelMinimizedBubble.vue';
import AIChatTimelineDrawer from './AIChatTimelineDrawer.vue';

defineOptions({ name: 'AIChatPanelOverlays' });

withDefaults(
  defineProps<{
    conversationContextDiagnostics?: null | Record<string, unknown>;
    hasUnread?: boolean;
    lastRunSummary?: null | Record<string, unknown>;
    minimizedOpen?: boolean;
    previewImageUrl?: null | string;
    previewImageVisible?: boolean;
    showContextDrawer?: boolean;
    showTimelineDrawer?: boolean;
    timelineItems?: ConversationTimelineItem[];
    timelineLoading?: boolean;
    timelineRefreshing?: boolean;
  }>(),
  {
    conversationContextDiagnostics: null,
    hasUnread: false,
    lastRunSummary: null,
    minimizedOpen: false,
    previewImageUrl: null,
    previewImageVisible: false,
    showContextDrawer: false,
    showTimelineDrawer: false,
    timelineItems: () => [],
    timelineLoading: false,
    timelineRefreshing: false,
  },
);

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'refreshTimeline'): void;
  (e: 'restore'): void;
  (e: 'update:previewImageVisible', value: boolean): void;
  (e: 'update:showContextDrawer', value: boolean): void;
  (e: 'update:showTimelineDrawer', value: boolean): void;
}>();
</script>

<template>
  <AIChatPanelMinimizedBubble
    :open="minimizedOpen"
    :has-unread="hasUnread"
    @restore="emit('restore')"
    @close="emit('close')"
  />

  <AIChatContextDiagnosticsDrawer
    :open="showContextDrawer"
    :conversation-context-diagnostics="conversationContextDiagnostics"
    :last-run-summary="lastRunSummary"
    @update:open="emit('update:showContextDrawer', $event)"
  />

  <AIChatTimelineDrawer
    :items="timelineItems"
    :loading="timelineLoading"
    :open="showTimelineDrawer"
    :refreshing="timelineRefreshing"
    @refresh="emit('refreshTimeline')"
    @update:open="emit('update:showTimelineDrawer', $event)"
  />

  <Image
    v-if="previewImageUrl"
    :src="previewImageUrl"
    :preview="{
      visible: previewImageVisible,
      onVisibleChange: (visible: boolean) =>
        emit('update:previewImageVisible', visible),
    }"
    class="hidden"
  />
</template>
