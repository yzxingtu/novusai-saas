import type { Ref } from 'vue';

import type { ConversationTimelineItem } from '#/api/shared/ai-chat';

import { computed } from 'vue';

import { $t } from '#/locales';

import { usePanelLinkPreview } from './use-panel-link-preview';
import { usePanelShellOverlayBindings } from './use-panel-shell-overlay-bindings';

type InteractionMode = 'confirm' | 'trusted_auto';

interface UsePanelShellRuntimeVisualsOptions {
  aiPanelStore: {
    close: () => void;
    hasUnread: boolean;
    minimized: boolean;
    restore: () => void;
    visible: boolean;
  };
  conversationContextDiagnostics: Ref<null | Record<string, unknown>>;
  interactionMode: Ref<InteractionMode>;
  interactionModeEffective: Ref<InteractionMode>;
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
  const interactionModeLabel = computed(() =>
    options.interactionModeEffective.value === 'trusted_auto'
      ? $t('common.globalAiChat.modeTrustedAuto')
      : $t('common.globalAiChat.modeConfirm'),
  );

  const interactionModeRequested = computed(() =>
    options.interactionMode.value === 'trusted_auto'
      ? $t('common.globalAiChat.modeTrustedAuto')
      : $t('common.globalAiChat.modeConfirm'),
  );

  const interactionModeDowngraded = computed(
    () =>
      options.interactionMode.value === 'trusted_auto' &&
      options.interactionModeEffective.value === 'confirm',
  );

  const interactionModeDowngradeText = computed(() => {
    const reason = String(options.lastRunSummary.value?.downgrade_reason || '');
    if (reason === 'missing_runtime_trust_policy') {
      return $t('common.globalAiChat.trustedAutoDowngradeMissingPolicy');
    }
    return reason || '';
  });

  const { handleOpenUrl, previewImageUrl, previewImageVisible } =
    usePanelLinkPreview();

  const { overlayListeners, overlayProps } = usePanelShellOverlayBindings({
    aiPanelStore: options.aiPanelStore,
    conversationContextDiagnostics: options.conversationContextDiagnostics,
    interactionModeDowngraded,
    interactionModeDowngradeText,
    interactionModeLabel,
    interactionModeRequested,
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
