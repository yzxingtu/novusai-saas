import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type { AgentItem, ChatMessage } from '#/types/ai-chat';

import { computed, onUnmounted, ref } from 'vue';

import { usePanelContextBridge } from './use-panel-context-bridge';
import { usePanelHeader } from './use-panel-header';

interface UsePanelShellHeaderContextOptions {
  activeConversationId: Ref<null | number>;
  agents: Ref<Array<{ id: number }>>;
  applyVariables: (
    agentId: number,
    values: Record<string, string>,
    persist: boolean,
  ) => void;
  agentsWithVarsInConversation: Ref<AgentItem[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  apiPrefix: Ref<string>;
  chatMessages: Ref<ChatMessage[]>;
  clearConversationMemory: () => boolean | Promise<boolean>;
  consumePendingAgentId: () => null | number;
  conversations: Ref<Array<{ agent_name?: null | string; id: number }>>;
  ensureAgentVarsLoaded: (agentId: number) => void;
  exportMenuItems: ComputedRef<ItemType[]>;
  fetchConversationMemory: () => Promise<unknown> | unknown;
  handleSendMessage: () => boolean | Promise<boolean>;
  inputMessage: Ref<string>;
  isPinned: ComputedRef<boolean>;
  lastMemoryUpdated: Ref<boolean | null | number | string>;
  loadAgents: (selectedAgentId?: number) => Promise<unknown> | unknown;
  loadConversationMessages: (
    conversationId: number,
  ) => Promise<unknown> | unknown;
  loadConversations: () => Promise<unknown> | unknown;
  onConversationRestored: () => void;
  onMessageSent: () => void;
  onOpenMultiVarsEditor: () => void;
  pendingConversationId: Ref<null | number | undefined>;
  pendingMessage: Ref<null | string | undefined>;
  routing: Ref<boolean>;
  selectedAgent: Ref<AgentItem | null>;
  selectedAgentId: Ref<null | number>;
  sending: Ref<boolean>;
  sendMessage: (options: {
    agentId: number;
    consumeMention?: boolean;
  }) => Promise<unknown> | unknown;
  startNewConversation: (forceReset?: boolean) => void;
  resetEndpointCaches: () => void;
  storePendingAgentId: Ref<number | undefined>;
  storePendingConversationId: Ref<null | number>;
  storePendingMessage: Ref<null | string>;
  streaming: Ref<boolean>;
  totalTokensUsed: Ref<number>;
  unpinAgent: () => void;
  visible: Ref<boolean>;
  /** Callback when page context is collected during panel open */
  onPageContextCollected?: (ctx: null | Record<string, unknown>) => void;
}

export function usePanelShellHeaderContext(
  options: UsePanelShellHeaderContextOptions,
) {
  const manualNewConversationAgentId = ref<null | number>(null);
  const showHistory = ref(false);
  const showMemoryPanel = ref(false);
  const forceRerouteNextTurn = ref(false);
  const routeNotice = ref<null | string>(null);
  let routeNoticeTimer: null | ReturnType<typeof setTimeout> = null;

  function showRouteNotice(text: string) {
    routeNotice.value = text;
    if (routeNoticeTimer) clearTimeout(routeNoticeTimer);
    routeNoticeTimer = setTimeout(() => {
      routeNotice.value = null;
    }, 4000);
  }

  const currentConversationAgentName = computed(() => {
    if (!options.activeConversationId.value) return '';
    return (
      options.selectedAgent.value?.name ||
      options.conversations.value.find(
        (conversation) =>
          conversation.id === options.activeConversationId.value,
      )?.agent_name ||
      ''
    );
  });

  const canForceReroute = computed(
    () =>
      !!options.activeConversationId.value &&
      !options.isPinned.value &&
      !options.routing.value &&
      !options.sending.value &&
      !options.streaming.value,
  );

  function clearRoutingIntent() {
    forceRerouteNextTurn.value = false;
    manualNewConversationAgentId.value = null;
  }

  function onToggleForceReroute() {
    forceRerouteNextTurn.value = !forceRerouteNextTurn.value;
  }

  const contextBridge = usePanelContextBridge({
    agents: options.agents,
    activeConversationId: options.activeConversationId,
    allAgentsVariables: options.allAgentsVariables,
    apiPrefix: options.apiPrefix,
    applyVariables: options.applyVariables,
    clearMentionedAgent: () => {},
    chatMessages: options.chatMessages,
    consumePendingAgentId: options.consumePendingAgentId,
    ensureAgentVarsLoaded: options.ensureAgentVarsLoaded,
    forceRerouteNextTurn,
    handleSendMessage: options.handleSendMessage,
    inputMessage: options.inputMessage,
    loadAgents: options.loadAgents,
    loadConversationMessages: options.loadConversationMessages,
    loadConversations: options.loadConversations,
    manualNewConversationAgentId,
    onConversationRestored: options.onConversationRestored,
    onMessageSent: options.onMessageSent,
    pendingConversationId: options.pendingConversationId,
    pendingMessage: options.pendingMessage,
    sendMessage: options.sendMessage,
    selectedAgentId: options.selectedAgentId,
    showHistory,
    showMemoryPanel,
    startNewConversation: options.startNewConversation,
    resetEndpointCaches: options.resetEndpointCaches,
    storePendingAgentId: options.storePendingAgentId,
    storePendingConversationId: options.storePendingConversationId,
    storePendingMessage: options.storePendingMessage,
    visible: options.visible,
    onPageContextCollected: options.onPageContextCollected as
      | undefined
      | ((ctx: unknown) => void),
  });

  const header = usePanelHeader({
    activeConversationId: options.activeConversationId,
    agentsWithVarsInConversation: options.agentsWithVarsInConversation,
    allAgentsVariables: options.allAgentsVariables,
    apiPrefix: options.apiPrefix,
    chatMessages: options.chatMessages,
    clearConversationMemory: options.clearConversationMemory,
    currentConversationAgentName,
    exportMenuItems: options.exportMenuItems,
    fetchConversationMemory: options.fetchConversationMemory,
    forceRerouteNextTurn,
    isPinned: options.isPinned,
    lastMemoryUpdated: options.lastMemoryUpdated,
    loadConversationMessages: options.loadConversationMessages,
    onOpenMultiVarsEditor: options.onOpenMultiVarsEditor,
    onOpenVarsModal: contextBridge.openVarsModal,
    routing: options.routing,
    selectedAgent: options.selectedAgent,
    showHistory,
    showMemoryPanel,
    totalTokensUsed: options.totalTokensUsed,
    unpinAgent: options.unpinAgent,
  });

  onUnmounted(() => {
    if (routeNoticeTimer) clearTimeout(routeNoticeTimer);
  });

  return {
    ...contextBridge,
    ...header,
    canForceReroute,
    clearRoutingIntent,
    forceRerouteNextTurn,
    manualNewConversationAgentId,
    onToggleForceReroute,
    routeNotice,
    showHistory,
    showMemoryPanel,
    showRouteNotice,
  };
}
