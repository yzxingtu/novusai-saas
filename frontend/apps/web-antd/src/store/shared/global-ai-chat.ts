/**
 * Global AI Floating Chat State
 *
 * Manages the floating AI chat drawer state (open/close, selected agent,
 * active conversation) shared across admin and tenant layouts.
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useGlobalAIChatStore = defineStore('global-ai-chat', () => {
  /** Whether the chat drawer is visible */
  const open = ref(false);

  /** Currently selected agent ID */
  const selectedAgentId = ref<number | null>(null);

  /** Active conversation ID (null = new conversation) */
  const activeConversationId = ref<number | null>(null);

  function toggle() {
    open.value = !open.value;
  }

  function show() {
    open.value = true;
  }

  function hide() {
    open.value = false;
  }

  function resetConversation() {
    activeConversationId.value = null;
  }

  function $reset() {
    open.value = false;
    selectedAgentId.value = null;
    activeConversationId.value = null;
  }

  return {
    open,
    selectedAgentId,
    activeConversationId,
    toggle,
    show,
    hide,
    resetConversation,
    $reset,
  };
});
