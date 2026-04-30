import type { Ref } from 'vue';

import type {
  LastAppliedRichTextAction,
  RichTextDraftUiStateInternal,
} from './rich-text-task-bridge';

import type {
  AgentItem,
  ChatMessage,
  InputVariable,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextAITask,
  RichTextConversationBinding,
  RichTextDraftRuntimeState,
} from '#/types/ai-chat';

import { computed, ref } from 'vue';

import { getAgentInputVariables } from '#/types/ai-chat';

import {
  applyRichTextTaskToEditor,
  attachRichTextTaskToMessage,
  computeRichTextDraftState,
  isLastAppliedRichTextActionValid,
  undoRichTextTaskInEditor,
} from './rich-text-task-bridge';
import { useRichTextTaskOrchestrationWatchers } from './use-rich-text-task-orchestration-watchers';

type RichTextTaskOrchestrationState = 'closed' | 'idle' | 'streaming';

interface RichTextTaskPanelStore {
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

interface UseRichTextTaskOrchestrationOptions {
  activeConversationId: Ref<null | number>;
  agents: Ref<AgentItem[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  chatMessages: Ref<ChatMessage[]>;
  ensureAgentVarsLoaded: (agentId: number) => void;
  inputMessage: Ref<string>;
  loadConversationMessages: (
    conversationId: number,
  ) => Promise<unknown> | unknown;
  manualNewConversationAgentId: Ref<null | number>;
  onMissingVariables: (payload: {
    agentId: number;
    agentName: string;
    requiredVars: InputVariable[];
    task: RichTextAITask;
  }) => void;
  onTaskQueued: () => void;
  selectedAgentId: Ref<null | number>;
  sendMessage: (options: {
    agentId: number;
    routeSource: 'rich_text_ai';
  }) => Promise<boolean>;
  sending: Ref<boolean>;
  showHistory: Ref<boolean>;
  showMemoryPanel: Ref<boolean>;
  startNewConversation: (preserveSelected?: boolean) => unknown;
  store: RichTextTaskPanelStore;
  streaming: Ref<boolean>;
}

export function useRichTextTaskOrchestration(
  options: UseRichTextTaskOrchestrationOptions,
) {
  const richTextDraftUiStateByKey = ref<
    Record<string, RichTextDraftUiStateInternal>
  >({});
  const currentRichTextDispatchTask = ref<null | RichTextAITask>(null);
  const lastAppliedRichTextAction = ref<LastAppliedRichTextAction | null>(null);

  const richTextTaskOrchestrationState =
    computed<RichTextTaskOrchestrationState>(() => {
      if (!options.store.visible) {
        return 'closed';
      }
      if (options.sending.value || options.streaming.value) {
        return 'streaming';
      }
      return 'idle';
    });

  function setRichTextDraftUiState(
    clientKey: string,
    patch: Partial<RichTextDraftUiStateInternal>,
  ) {
    richTextDraftUiStateByKey.value = {
      ...richTextDraftUiStateByKey.value,
      [clientKey]: {
        ...richTextDraftUiStateByKey.value[clientKey],
        ...patch,
      },
    };
  }

  function ensureRichTextDraftUiState(clientKey: string) {
    if (richTextDraftUiStateByKey.value[clientKey]) {
      return;
    }
    setRichTextDraftUiState(clientKey, {});
  }

  function getRichTextBinding(task: RichTextAITask) {
    return options.store.getRichTextConversationBinding(
      task.pageKey,
      task.editorInstanceId,
      task.agentId,
    );
  }

  function invalidateLastAppliedRichTextAction() {
    if (!lastAppliedRichTextAction.value) {
      return;
    }
    const { clientKey } = lastAppliedRichTextAction.value;
    setRichTextDraftUiState(clientKey, { undoAvailable: false });
    lastAppliedRichTextAction.value = null;
  }

  function findAgentMissingVariables(agentId: number) {
    const agent = options.agents.value.find(
      (candidate) => candidate.id === agentId,
    );
    const requiredVars = getAgentInputVariables(agent).filter(
      (item) => item.required,
    );
    if (requiredVars.length === 0) {
      return null;
    }

    options.ensureAgentVarsLoaded(agentId);
    const agentVars = options.allAgentsVariables.value[agentId] ?? {};
    const missingVars = requiredVars.filter(
      (item) => !agentVars[item.name]?.trim(),
    );
    if (missingVars.length === 0) {
      return null;
    }

    return {
      agentName: agent?.name ?? '',
      requiredVars,
    };
  }

  async function sendPreparedRichTextTask(
    task: RichTextAITask,
  ): Promise<boolean> {
    const missingVariables = findAgentMissingVariables(task.agentId);
    if (missingVariables) {
      options.onMissingVariables({
        agentId: task.agentId,
        agentName: missingVariables.agentName || task.title || '',
        requiredVars: missingVariables.requiredVars,
        task,
      });
      return false;
    }

    options.inputMessage.value = task.message;
    const previousMessageCount = options.chatMessages.value.length;
    const sendPromise = options.sendMessage({
      agentId: task.agentId,
      routeSource: 'rich_text_ai',
    });
    const newAssistantMessage = [...options.chatMessages.value]
      .slice(previousMessageCount)
      .find((message) => message.role === 'assistant');
    const taggedTask = attachRichTextTaskToMessage(newAssistantMessage, task);
    if (taggedTask) {
      ensureRichTextDraftUiState(
        taggedTask.messageClientKey ?? newAssistantMessage?.clientKey ?? '',
      );
      currentRichTextDispatchTask.value = taggedTask;
      options.store.clearPendingRichTextTask(taggedTask.taskId);
    }
    const sent = await sendPromise;
    currentRichTextDispatchTask.value = null;
    return sent;
  }

  async function dispatchRichTextTask(task: RichTextAITask) {
    if (richTextTaskOrchestrationState.value === 'streaming') {
      options.store.queueRichTextTask(task);
      options.store.clearPendingRichTextTask(task.taskId);
      options.onTaskQueued();
      return;
    }

    if (!options.store.visible) {
      options.store.open();
      return;
    }

    const normalizedTask: RichTextAITask = {
      ...task,
      state: task.state === 'queued' ? 'ready' : task.state,
      updatedAt: Date.now(),
    };
    options.showHistory.value = false;
    options.showMemoryPanel.value = false;

    const binding = getRichTextBinding(normalizedTask);
    if (
      binding &&
      options.activeConversationId.value !== binding.conversationId
    ) {
      await options.loadConversationMessages(binding.conversationId);
    } else if (!binding) {
      options.manualNewConversationAgentId.value = normalizedTask.agentId;
      if (options.selectedAgentId.value !== normalizedTask.agentId) {
        options.selectedAgentId.value = normalizedTask.agentId;
      }
      options.startNewConversation(true);
    }

    await sendPreparedRichTextTask({
      ...normalizedTask,
      conversationId: binding?.conversationId ?? null,
    });
  }

  function flushRichTextTaskQueue() {
    if (richTextTaskOrchestrationState.value !== 'idle') {
      return;
    }
    const promotedTask = options.store.promoteQueuedRichTextTask();
    if (!promotedTask) {
      return;
    }
    void dispatchRichTextTask(promotedTask);
  }

  async function applyRichTextTaskContext() {
    const task = options.store.pendingRichTextTask;
    if (!task) {
      return;
    }
    await dispatchRichTextTask(task);
  }

  function syncCurrentRichTextBinding(conversationId: null | number) {
    const task = currentRichTextDispatchTask.value;
    if (
      !task ||
      typeof conversationId !== 'number' ||
      !Number.isFinite(conversationId)
    ) {
      return;
    }

    const nextTask: RichTextAITask = {
      ...task,
      conversationId,
      updatedAt: Date.now(),
    };
    currentRichTextDispatchTask.value = nextTask;
    options.store.bindRichTextConversation({
      conversationId,
      pageKey: nextTask.pageKey,
      editorInstanceId: nextTask.editorInstanceId,
      agentId: nextTask.agentId,
      messageIndex: nextTask.messageIndex,
      task: nextTask,
    });

    if (!nextTask.messageClientKey) {
      return;
    }

    const targetMessage = options.chatMessages.value.find(
      (message) => message.clientKey === nextTask.messageClientKey,
    );
    if (targetMessage?.role === 'assistant') {
      targetMessage.richTextAI = nextTask;
    }
  }

  function getRichTextDraftState(
    message: ChatMessage,
  ): null | RichTextDraftRuntimeState {
    if (message.role !== 'assistant' || !message.richTextAI) {
      return null;
    }
    const uiState = richTextDraftUiStateByKey.value[message.clientKey];
    if (!uiState) {
      return null;
    }
    return computeRichTextDraftState(message.richTextAI, uiState);
  }

  function onRichTextDiscard(index: number) {
    const messageItem = options.chatMessages.value[index];
    if (!messageItem) {
      return;
    }
    setRichTextDraftUiState(messageItem.clientKey, { discarded: true });
  }

  function onRichTextApply(
    index: number,
    target: RichTextAIApplyTarget,
    mode: RichTextAIApplyMode,
  ) {
    const messageItem = options.chatMessages.value[index];
    if (!messageItem) {
      return;
    }

    const result = applyRichTextTaskToEditor(messageItem, target, mode);
    if (result.kind === 'editor_unavailable') {
      setRichTextDraftUiState(messageItem.clientKey, {
        discarded: false,
      });
      return;
    }
    if (result.kind !== 'applied') {
      return;
    }

    invalidateLastAppliedRichTextAction();

    if (messageItem.role === 'assistant') {
      messageItem.richTextAI = result.nextTask;
    }
    setRichTextDraftUiState(messageItem.clientKey, {
      discarded: false,
      lastApplyMode: mode,
      lastApplyTarget: target,
      undoAvailable: true,
      editorRevisionAfterApply: result.editorRevisionAfterApply,
    });
    lastAppliedRichTextAction.value = {
      clientKey: messageItem.clientKey,
      pageKey: result.nextTask.pageKey,
      editorInstanceId: result.nextTask.editorInstanceId,
      editorRevisionAfterApply: result.editorRevisionAfterApply,
    };
    options.store.markRichTextTaskApplied(result.nextTask.taskId, {
      conversationId:
        result.nextTask.conversationId ??
        options.activeConversationId.value ??
        null,
      lastAppliedMode: mode,
    });
  }

  function onRichTextUndo(index: number) {
    const messageItem = options.chatMessages.value[index];
    if (!messageItem) {
      return;
    }

    const result = undoRichTextTaskInEditor(
      messageItem,
      richTextDraftUiStateByKey.value[messageItem.clientKey],
    );
    if (result.kind === 'invalidate_last_action') {
      invalidateLastAppliedRichTextAction();
      return;
    }
    if (result.kind !== 'undone') {
      return;
    }

    if (messageItem.role === 'assistant') {
      messageItem.richTextAI = result.nextTask;
    }
    setRichTextDraftUiState(messageItem.clientKey, {
      undoAvailable: false,
    });
    options.store.markRichTextTaskUndone(result.nextTask.taskId, {
      conversationId:
        result.nextTask.conversationId ??
        options.activeConversationId.value ??
        null,
      lastAppliedMode: result.nextTask.lastAppliedMode,
    });
    if (lastAppliedRichTextAction.value?.clientKey === messageItem.clientKey) {
      lastAppliedRichTextAction.value = null;
    }
  }

  function syncMessageDraftStates() {
    for (const message of options.chatMessages.value) {
      if (
        message.role !== 'assistant' ||
        message.source !== 'rich_text_ai' ||
        !message.richTextAI ||
        message.richTextAI.messageClientKey !== message.clientKey
      ) {
        continue;
      }
      ensureRichTextDraftUiState(message.clientKey);
    }
  }

  useRichTextTaskOrchestrationWatchers({
    activeConversationId: options.activeConversationId,
    applyRichTextTaskContext,
    chatMessages: options.chatMessages,
    flushRichTextTaskQueue,
    hasLastAppliedRichTextAction: () => !!lastAppliedRichTextAction.value,
    invalidateLastAppliedRichTextAction,
    isLastAppliedRichTextActionValid: () =>
      !lastAppliedRichTextAction.value ||
      isLastAppliedRichTextActionValid(lastAppliedRichTextAction.value),
    onTaskQueued: options.onTaskQueued,
    richTextTaskOrchestrationState,
    store: options.store,
    syncCurrentRichTextBinding,
    syncMessageDraftStates,
  });

  return {
    getRichTextDraftState,
    onRichTextApply,
    onRichTextDiscard,
    onRichTextUndo,
    sendPreparedRichTextTask,
  };
}
