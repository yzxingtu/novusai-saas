import type { Ref } from 'vue';

import type { MemoryState } from '#/api/shared/ai-chat';

import type { UseAIChatOptions } from './use-ai-chat-options';

import { ref, unref } from 'vue';

import {
  clearChatConversationMemoryApi,
  getChatConversationMemoryApi,
} from '#/api/shared/ai-chat';

interface UseAIChatMemoryDeps {
  activeConversationId: Ref<null | number>;
  lastMemoryUpdated?: Ref<boolean>;
  options: UseAIChatOptions;
}

export function useAIChatMemory(deps: UseAIChatMemoryDeps) {
  const { activeConversationId, options } = deps;

  const memoryState = ref<MemoryState | null>(null);
  const memoryLoading = ref(false);
  const clearingMemory = ref(false);
  const lastMemoryUpdated = deps.lastMemoryUpdated ?? ref(false);

  async function fetchConversationMemory(): Promise<MemoryState | null> {
    const convId = activeConversationId.value;
    if (!convId) {
      return null;
    }
    memoryLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix) as string;
      const state = await getChatConversationMemoryApi(prefix, convId);
      memoryState.value = state;
      return state;
    } catch {
      memoryState.value = null;
      return null;
    } finally {
      memoryLoading.value = false;
    }
  }

  async function clearConversationMemory(): Promise<boolean> {
    const convId = activeConversationId.value;
    if (!convId || clearingMemory.value) {
      return false;
    }
    clearingMemory.value = true;
    try {
      const prefix = unref(options.apiPrefix) as string;
      await clearChatConversationMemoryApi(prefix, convId);
      memoryState.value = null;
      lastMemoryUpdated.value = false;
      return true;
    } catch {
      return false;
    } finally {
      clearingMemory.value = false;
    }
  }

  function resetMemoryState() {
    memoryState.value = null;
    lastMemoryUpdated.value = false;
  }

  return {
    clearConversationMemory,
    clearingMemory,
    fetchConversationMemory,
    lastMemoryUpdated,
    memoryLoading,
    memoryState,
    resetMemoryState,
  };
}
