import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type { PageContext } from '#/api/shared/ai-chat';
import type {
  AgentItem,
  ChatMessage,
  RichTextAIApplyMode,
  RichTextAITask,
  RichTextConversationBinding,
} from '#/types/ai-chat';

import { computed, ref } from 'vue';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';

import { usePanelShellHeaderContext } from './use-panel-shell-header-context';
import { usePanelVarsEditor } from './use-panel-vars-editor';
import { useRichTextTaskOrchestration } from './use-rich-text-task-orchestration';

interface ShellRichTextStore {
  bindRichTextConversation: (
    binding: Omit<RichTextConversationBinding, 'updatedAt'> & {
      updatedAt?: number;
    },
  ) => void;
  clearPendingRichTextTask: (taskId?: string) => void;
  getRichTextConversationBinding: (
    pageKey: string,
    editorInstanceId: string,
    agentId: number,
  ) => null | RichTextConversationBinding;
  markRichTextTaskApplied: (
    taskId: string,
    options?: {
      conversationId?: null | number;
      lastAppliedMode?: RichTextAIApplyMode;
    },
  ) => void;
  markRichTextTaskUndone: (
    taskId: string,
    options?: {
      conversationId?: null | number;
      lastAppliedMode?: RichTextAIApplyMode;
    },
  ) => void;
  open: () => void;
  pendingRichTextTask: null | RichTextAITask;
  promoteQueuedRichTextTask: () => null | RichTextAITask;
  queueRichTextTask: (task: RichTextAITask) => void;
  visible: boolean;
}

interface UsePanelShellContextOptions {
  activeConversationId: Ref<null | number>;
  agents: Ref<AgentItem[]>;
  agentsWithVarsInConversation: Ref<AgentItem[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  apiPrefix: Ref<string>;
  chatMessages: Ref<ChatMessage[]>;
  clearConversationMemory: () => boolean | Promise<boolean>;
  clearResolvedPageOps: () => void;
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
  panelStore: ShellRichTextStore;
  pendingConversationId: Ref<null | number | undefined>;
  pendingMessage: Ref<null | string | undefined>;
  routing: Ref<boolean>;
  selectedAgent: Ref<AgentItem | null>;
  selectedAgentId: Ref<null | number>;
  sending: Ref<boolean>;
  sendMessage: (options: {
    agentId: number;
    consumeMention?: boolean;
    pageContext: null | PageContext;
    routeSource?: string;
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
    persist?: boolean,
  ) => void;
}

export function usePanelShellContext(options: UsePanelShellContextOptions) {
  const sendPreparedRichTextTaskRef = ref<
    (task: RichTextAITask) => Promise<boolean>
  >(async () => false);
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
    clearPendingRichTextTask: options.panelStore.clearPendingRichTextTask,
    clearResolvedPageOps: options.clearResolvedPageOps,
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
    sendPreparedRichTextTask: (task) => sendPreparedRichTextTaskRef.value(task),
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

  const richTextTask = useRichTextTaskOrchestration({
    activeConversationId: options.activeConversationId,
    agents: options.agents,
    allAgentsVariables: options.allAgentsVariables,
    chatMessages: options.chatMessages,
    ensureAgentVarsLoaded: options.ensureAgentVarsLoaded,
    inputMessage: options.inputMessage,
    loadConversationMessages: options.loadConversationMessages,
    manualNewConversationAgentId: headerContext.manualNewConversationAgentId,
    onMissingVariables: ({ agentId, agentName, requiredVars, task }) => {
      headerContext.deferSendForMissingVariables({
        agentId,
        agentName,
        pageContext: null,
        requiredVars,
        richTextTask: task,
        routeSource: 'rich_text_ai',
      });
    },
    onTaskQueued: () => {
      message.info($t('common.richTextTaskQueued'));
    },
    selectedAgentId: options.selectedAgentId,
    sendMessage: options.sendMessage,
    sending: options.sending,
    showHistory: headerContext.showHistory,
    showMemoryPanel: headerContext.showMemoryPanel,
    startNewConversation: options.startNewConversation,
    store: options.panelStore,
    streaming: options.streaming,
  });
  sendPreparedRichTextTaskRef.value = richTextTask.sendPreparedRichTextTask;

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
    getRichTextDraftState: richTextTask.getRichTextDraftState,
    onRichTextApply: richTextTask.onRichTextApply,
    onRichTextDiscard: richTextTask.onRichTextDiscard,
    onRichTextUndo: richTextTask.onRichTextUndo,
  };
}
