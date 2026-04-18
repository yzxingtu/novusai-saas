import type { Ref } from 'vue';

import type { ConversationTimelineItem } from '#/api/shared/ai-chat';

import { computed } from 'vue';

interface UsePanelShellOverlayBindingsOptions {
  aiPanelStore: {
    close: () => void;
    hasUnread: boolean;
    minimized: boolean;
    restore: () => void;
    visible: boolean;
  };
  conversationContextDiagnostics: Ref<null | Record<string, unknown>>;
  lastRunSummary: Ref<null | Record<string, unknown>>;
  previewImageUrl: Ref<null | string> | Ref<string>;
  previewImageVisible: Ref<boolean>;
  refreshTimeline: () => void;
  showContextDrawer: Ref<boolean>;
  showTimelineDrawer: Ref<boolean>;
  timelineItems: Ref<ConversationTimelineItem[]>;
  timelineLoading: Ref<boolean>;
  timelineRefreshing: Ref<boolean>;
}

export function usePanelShellOverlayBindings(
  options: UsePanelShellOverlayBindingsOptions,
) {
  const overlayProps = computed(() => ({
    conversationContextDiagnostics:
      options.conversationContextDiagnostics.value,
    hasUnread: options.aiPanelStore.hasUnread,
    lastRunSummary: options.lastRunSummary.value,
    minimizedOpen:
      options.aiPanelStore.minimized && !options.aiPanelStore.visible,
    previewImageUrl: options.previewImageUrl.value,
    previewImageVisible: options.previewImageVisible.value,
    showContextDrawer: options.showContextDrawer.value,
    showTimelineDrawer: options.showTimelineDrawer.value,
    timelineItems: options.timelineItems.value,
    timelineLoading: options.timelineLoading.value,
    timelineRefreshing: options.timelineRefreshing.value,
  }));

  const overlayListeners = {
    close: () => options.aiPanelStore.close(),
    refreshTimeline: options.refreshTimeline,
    restore: () => options.aiPanelStore.restore(),
    'update:previewImageVisible': (value: boolean) => {
      options.previewImageVisible.value = value;
    },
    'update:showContextDrawer': (value: boolean) => {
      options.showContextDrawer.value = value;
    },
    'update:showTimelineDrawer': (value: boolean) => {
      options.showTimelineDrawer.value = value;
    },
  };

  return { overlayProps, overlayListeners };
}
