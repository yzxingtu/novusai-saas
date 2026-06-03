import type { Ref } from 'vue';

import type { ConversationTimelineItem } from '#/api/shared/ai-chat';

import { usePanelLinkPreview } from './use-panel-link-preview';
import { usePanelShellOverlayBindings } from './use-panel-shell-overlay-bindings';

interface UsePanelShellRuntimeVisualsOptions {
  aiPanelStore: {
    close: () => void;
    hasUnread: boolean;
    minimized: boolean;
    restore: () => void;
    visible: boolean;
  };
  conversationContextDiagnostics: Ref<null | Record<string, unknown>>;
  lastRunSummary: Ref<null | Record<string, unknown>>;
  refreshTimeline: () => void;
  showContextDrawer: Ref<boolean>;
  showTimelineDrawer: Ref<boolean>;
  timelineItems: Ref<ConversationTimelineItem[]>;
  timelineLoading: Ref<boolean>;
  timelineRefreshing: Ref<boolean>;
}

export function usePanelShellRuntimeVisuals(
  options: UsePanelShellRuntimeVisualsOptions,
) {
  const { handleOpenUrl, previewImageUrl, previewImageVisible } =
    usePanelLinkPreview();

  const { overlayListeners, overlayProps } = usePanelShellOverlayBindings({
    aiPanelStore: options.aiPanelStore,
    conversationContextDiagnostics: options.conversationContextDiagnostics,
    lastRunSummary: options.lastRunSummary,
    previewImageUrl,
    previewImageVisible,
    refreshTimeline: options.refreshTimeline,
    showContextDrawer: options.showContextDrawer,
    showTimelineDrawer: options.showTimelineDrawer,
    timelineItems: options.timelineItems,
    timelineLoading: options.timelineLoading,
    timelineRefreshing: options.timelineRefreshing,
  });

  return {
    handleOpenUrl,
    overlayListeners,
    overlayProps,
  };
}
