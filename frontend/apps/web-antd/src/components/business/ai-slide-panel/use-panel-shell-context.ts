import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type { AgentItem, ChatMessage } from '#/types/ai-chat';

import { computed, ref } from 'vue';

import { usePanelShellHeaderContext } from './use-panel-shell-header-context';
import { usePanelVarsEditor } from './use-panel-vars-editor';

interface UsePanelShellContextOptions {
  activeConversationId: Ref<null | number>;
  agents: Ref<AgentItem[]>;
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
  pendingConversationId: Ref<null | number | undefined>;
  pendingMessage: Ref<null | string | undefined>;
  routing: Ref<boolean>;
  selectedAgent: Ref<AgentItem | null>;
  selectedAgentId: Ref<null | number>;
  sending: Ref<boolean>;
  sendMessage: (options: {
    agentId: number;
    consumeMention?: boolean;
  }) => Promise<boolean>;
  startNewConversation: (forceReset?: boolean) => void;
  storePendingAgentId: Ref<number | undefined>;
  storePendingConversationId: Ref<null | number>;
  storePendingMessage: Ref<null | string>;
  streaming: Ref<boolean>;
  totalTokensUsed: Ref<number>;
  unpinAgent: () => void;
  visible: Ref<boolean>;
  applyVariables: (
    agentId: number,
    values: Record<string, string>,
    persist: boolean,
  ) => void;
}

export function usePanelShellContext(options: UsePanelShellContextOptions) {
  const openMultiVarsEditorRef = ref<() => void>(() => {});

  const headerContext = usePanelShellHeaderContext({
    activeConversationId: options.activeConversationId,
    agents: options.agents,
    agentsWithVarsInConversation: options.agentsWithVarsInConversation,
    allAgentsVariables: options.allAgentsVariables,
    apiPrefix: options.apiPrefix,
    applyVariables: options.applyVariables,
    chatMessages: options.chatMessages,
    clearConversationMemory: options.clearConversationMemory,
    consumePendingAgentId: options.consumePendingAgentId,
    conversations: options.conversations,
    ensureAgentVarsLoaded: options.ensureAgentVarsLoaded,
    exportMenuItems: options.exportMenuItems,
    fetchConversationMemory: options.fetchConversationMemory,
    handleSendMessage: options.handleSendMessage,
    inputMessage: options.inputMessage,
    isPinned: options.isPinned,
    lastMemoryUpdated: options.lastMemoryUpdated,
    loadAgents: options.loadAgents,
    loadConversationMessages: options.loadConversationMessages,
    loadConversations: options.loadConversations,
    onConversationRestored: options.onConversationRestored,
    onMessageSent: options.onMessageSent,
    onOpenMultiVarsEditor: () => openMultiVarsEditorRef.value(),
    pendingConversationId: options.pendingConversationId,
    pendingMessage: options.pendingMessage,
    routing: options.routing,
    selectedAgent: options.selectedAgent,
    selectedAgentId: options.selectedAgentId,
    sending: options.sending,
    sendMessage: options.sendMessage,
    startNewConversation: options.startNewConversation,
    storePendingAgentId: options.storePendingAgentId,
    storePendingConversationId: options.storePendingConversationId,
    storePendingMessage: options.storePendingMessage,
    streaming: options.streaming,
    totalTokensUsed: options.totalTokensUsed,
    unpinAgent: options.unpinAgent,
    visible: options.visible,
  });

  const varsEditor = usePanelVarsEditor({
    agentsWithVarsInConversation: options.agentsWithVarsInConversation,
    allAgentsVariables: options.allAgentsVariables,
    applyVariables: options.applyVariables,
    ensureAgentVarsLoaded: options.ensureAgentVarsLoaded,
    varsFormValues: headerContext.varsFormValues,
    varsPersist: headerContext.varsPersist,
  });
  openMultiVarsEditorRef.value = varsEditor.openMultiVarsEditor;

  const agentVarsModalProps = computed(() => ({
    multiAgents: options.agentsWithVarsInConversation.value,
    multiOpen: varsEditor.multiVarsModalVisible.value,
    multiPersist: varsEditor.multiVarsPersist.value,
    multiValues: varsEditor.multiVarsFormValues,
    singleAgent: headerContext.varsModalAgent.value,
    singleOpen: headerContext.varsModalVisible.value,
    singlePersist: headerContext.varsPersist.value,
    singleValues: headerContext.varsFormValues,
  }));

  const agentVarsModalListeners = {
    multiCancel: varsEditor.onMultiVarsCancel,
    multiConfirm: varsEditor.onMultiVarsConfirm,
    multiPersistChange: varsEditor.onMultiPersistChange,
    multiValueChange: varsEditor.onMultiVarValueChange,
    singleCancel: headerContext.onVarsCancel,
    singleConfirm: headerContext.onVarsConfirm,
    singlePersistChange: varsEditor.onSinglePersistChange,
    singleValueChange: varsEditor.onSingleVarValueChange,
  };

  return {
    ...headerContext,
    agentVarsModalListeners,
    agentVarsModalProps,
  };
}
