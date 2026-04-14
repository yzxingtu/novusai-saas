import type { ComputedRef, Ref } from 'vue';

import type { ChatMessage, RichTextAITask } from '#/types/ai-chat';

import { onUnmounted, watch } from 'vue';

import { sourceEditorRegistryVersion } from '#/components/business/rich-text-editor/sourceEditorRegistry';

interface UseRichTextTaskOrchestrationWatchersOptions {
  activeConversationId: Ref<null | number>;
  applyRichTextTaskContext: () => Promise<void>;
  chatMessages: Ref<ChatMessage[]>;
  flushRichTextTaskQueue: () => void;
  hasLastAppliedRichTextAction: () => boolean;
  invalidateLastAppliedRichTextAction: () => void;
  isLastAppliedRichTextActionValid: () => boolean;
  onTaskQueued?: (() => void) | undefined;
  richTextTaskOrchestrationState: ComputedRef<'closed' | 'idle' | 'streaming'>;
  store: {
    clearPendingRichTextTask: (taskId?: string) => void;
    open: () => void;
    pendingRichTextTask: null | RichTextAITask;
    queueRichTextTask: (task: RichTextAITask) => void;
  };
  syncCurrentRichTextBinding: (conversationId: null | number) => void;
  syncMessageDraftStates: () => void;
}

export function useRichTextTaskOrchestrationWatchers(
  options: UseRichTextTaskOrchestrationWatchersOptions,
) {
  watch(
    options.activeConversationId,
    (conversationId, previousConversationId) => {
      options.syncCurrentRichTextBinding(conversationId);
      if (
        previousConversationId !== undefined &&
        previousConversationId !== conversationId &&
        options.hasLastAppliedRichTextAction()
      ) {
        options.invalidateLastAppliedRichTextAction();
      }
    },
  );

  watch(
    () =>
      options.chatMessages.value.map((message) => ({
        clientKey: message.clientKey,
        messageClientKey: message.richTextAI?.messageClientKey ?? null,
        role: message.role,
        source: message.source ?? null,
      })),
    () => {
      options.syncMessageDraftStates();
    },
    { flush: 'post', immediate: true },
  );

  watch(
    [
      options.richTextTaskOrchestrationState,
      () => options.store.pendingRichTextTask?.taskId,
    ],
    async ([state]) => {
      const pendingTask = options.store.pendingRichTextTask;
      if (!pendingTask) {
        if (state === 'idle') {
          options.flushRichTextTaskQueue();
        }
        return;
      }

      if (state === 'streaming') {
        options.store.queueRichTextTask(pendingTask);
        options.store.clearPendingRichTextTask(pendingTask.taskId);
        options.onTaskQueued?.();
        return;
      }

      if (state === 'closed') {
        options.store.open();
        return;
      }

      await options.applyRichTextTaskContext();
    },
    { flush: 'post', immediate: true },
  );

  watch(
    [
      options.activeConversationId,
      () => options.chatMessages.value.length,
      options.richTextTaskOrchestrationState,
    ],
    () => {
      if (options.richTextTaskOrchestrationState.value === 'idle') {
        options.flushRichTextTaskQueue();
      }
    },
    { flush: 'post' },
  );

  watch(sourceEditorRegistryVersion, () => {
    if (!options.isLastAppliedRichTextActionValid()) {
      options.invalidateLastAppliedRichTextAction();
    }
  });

  onUnmounted(() => {
    options.invalidateLastAppliedRichTextAction();
  });
}
