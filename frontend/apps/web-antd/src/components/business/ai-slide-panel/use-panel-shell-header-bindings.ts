import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type { ConversationTimelineItem } from '#/api/shared/ai-chat';

import { computed } from 'vue';

interface UsePanelShellHeaderBindingsOptions {
  activeConversationId: Ref<null | number>;
  aiPanelStore: { docked: boolean; mode: 'full' | 'panel' };
  canForceReroute: ComputedRef<boolean>;
  forceRerouteNextTurn: Ref<boolean>;
  headerConversationSummary: Ref<string>;
  headerMemoryHasAttention: Ref<boolean>;
  headerMoreHasAttention: Ref<boolean>;
  headerMoreMenuItems: Ref<ItemType[]>;
  hasHeaderVariableValues: Ref<boolean>;
  memoryLoading: Ref<boolean>;
  onEditHeaderVars: () => void;
  onToggleMemory: () => void | Promise<void>;
  onToggleForceReroute: () => void;
  panelTitle: ComputedRef<string>;
  routeNotice: Ref<null | string>;
  routing: Ref<boolean>;
  showHeaderMemoryButton: Ref<boolean>;
  showHeaderMoreMenu: Ref<boolean>;
  showHeaderVarsButton: Ref<boolean>;
  showHistory: Ref<boolean>;
  showMemoryPanel: Ref<boolean>;
  showContextDrawer: Ref<boolean>;
  showTimelineDrawer: Ref<boolean>;
  timelineItems: Ref<ConversationTimelineItem[]>;
  timelineLoading: Ref<boolean>;
  timelineRefreshing: Ref<boolean>;
  refreshTimeline: () => void;
  isPinned: ComputedRef<boolean>;
  toggleHistory: () => void;
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
    hasHeaderVariableValues: options.hasHeaderVariableValues.value,
    headerMemoryHasAttention: options.headerMemoryHasAttention.value,
    headerMoreHasAttention: options.headerMoreHasAttention.value,
    headerMoreMenuItems: options.headerMoreMenuItems.value,
    memoryLoading: options.memoryLoading.value,
    showHeaderMemoryButton: options.showHeaderMemoryButton.value,
    showHeaderMoreMenu: options.showHeaderMoreMenu.value,
    showHeaderVarsButton: options.showHeaderVarsButton.value,
    showHistory: options.showHistory.value,
    showMemoryPanel: options.showMemoryPanel.value,
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
    newChat: options.onStartNewChat,
    toggleHistory: options.toggleHistory,
    toggleMemory: options.onToggleMemory,
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
