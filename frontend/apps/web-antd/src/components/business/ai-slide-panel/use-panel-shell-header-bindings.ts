import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type { UsePageAICapabilityReturn } from './use-page-ai-capability';

import type { ConversationTimelineItem } from '#/api/shared/ai-chat';

import { computed } from 'vue';

interface UsePanelShellHeaderBindingsOptions {
  activeConversationId: Ref<null | number>;
  aiPanelStore: { docked: boolean; mode: 'full' | 'panel' };
  canForceReroute: ComputedRef<boolean>;
  forceRerouteNextTurn: Ref<boolean>;
  headerConversationSummary: Ref<string>;
  headerMoreHasAttention: Ref<boolean>;
  headerMoreMenuItems: Ref<ItemType[]>;
  hasHeaderVariableValues: Ref<boolean>;
  onEditHeaderVars: () => void;
  onToggleForceReroute: () => void;
  panelTitle: ComputedRef<string>;
  pageAICapability: UsePageAICapabilityReturn;
  routeNotice: Ref<null | string>;
  routing: Ref<boolean>;
  showHeaderMoreMenu: Ref<boolean>;
  showHeaderVarsButton: Ref<boolean>;
  showHistory: Ref<boolean>;
  showContextDrawer: Ref<boolean>;
  showTimelineDrawer: Ref<boolean>;
  timelineItems: Ref<ConversationTimelineItem[]>;
  timelineLoading: Ref<boolean>;
  timelineRefreshing: Ref<boolean>;
  refreshTimeline: () => void;
  isPinned: ComputedRef<boolean>;
  toggleHistory: () => void;
  togglePageAIDetails: () => void;
  expandAllPageAIOperations: () => void;
  onStartNewChat: () => void;
  handleClose: () => void;
  handleMinimize: () => void;
  handleToggleDock: () => void;
  handleToggleMode: () => void;
}

export function usePanelShellHeaderBindings(
  options: UsePanelShellHeaderBindingsOptions,
) {
  const headerProps = computed(() => ({
    docked: options.aiPanelStore.docked,
    headerConversationSummary: options.headerConversationSummary.value,
    mode: options.aiPanelStore.mode,
    panelTitle: options.panelTitle.value,
    routeNotice: options.routeNotice.value,
    routing: options.routing.value,
  }));

  const toolbarProps = computed(() => ({
    canForceReroute: options.canForceReroute.value,
    forceRerouteNextTurn: options.forceRerouteNextTurn.value,
    hasExpandablePageAIDetails:
      options.pageAICapability.hasExpandablePageAIDetails?.value ?? false,
    hasHeaderVariableValues: options.hasHeaderVariableValues.value,
    hasPageAI: options.pageAICapability.hasPageAI.value,
    headerMoreHasAttention: options.headerMoreHasAttention.value,
    headerMoreMenuItems: options.headerMoreMenuItems.value,
    pageAIDetailsExpanded: options.pageAICapability.pageAIDetailsExpanded.value,
    pageAIDiagnostics: options.pageAICapability.pageAIDiagnostics.value,
    pageAIFallbackOnly: options.pageAICapability.pageAIFallbackOnly.value,
    pageAIOperationCount: options.pageAICapability.pageAIOperationCount.value,
    pageAIRailTooltip: options.pageAICapability.pageAIRailTooltip.value,
    pageAIRemainingOperationCount:
      options.pageAICapability.pageAIRemainingOperationCount.value,
    pageAIStatBadges: options.pageAICapability.pageAIStatBadges.value,
    pageAISummary: options.pageAICapability.pageAISummary.value,
    pageAIVisibleOperations:
      options.pageAICapability.pageAIVisibleOperations.value,
    resolvedPageAITitle: options.pageAICapability.resolvedPageAITitle.value,
    showHeaderMoreMenu: options.showHeaderMoreMenu.value,
    showHeaderVarsButton: options.showHeaderVarsButton.value,
    showHistory: options.showHistory.value,
    showRerouteButton:
      !!options.activeConversationId.value && !options.isPinned.value,
  }));

  const headerListeners = {
    close: options.handleClose,
    minimize: options.handleMinimize,
    toggleDock: options.handleToggleDock,
    toggleMode: options.handleToggleMode,
  };

  const toolbarListeners = {
    editVars: options.onEditHeaderVars,
    expandAllOperations: options.expandAllPageAIOperations,
    newChat: options.onStartNewChat,
    toggleHistory: options.toggleHistory,
    togglePageDetails: options.togglePageAIDetails,
    toggleReroute: options.onToggleForceReroute,
  };

  return {
    headerProps,
    headerListeners,
    toolbarProps,
    toolbarListeners,
    showContextDrawer: options.showContextDrawer,
    showTimelineDrawer: options.showTimelineDrawer,
    timelineItems: options.timelineItems,
    timelineLoading: options.timelineLoading,
    timelineRefreshing: options.timelineRefreshing,
    refreshTimeline: options.refreshTimeline,
  };
}
