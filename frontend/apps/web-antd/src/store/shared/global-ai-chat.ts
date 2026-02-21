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

  /** Pending agent ID — set by external pages, consumed by drawer on open */
  const pendingAgentId = ref<number | undefined>(undefined);

  /** Whether there are unread messages (shown as badge on icon) */
  const hasUnread = ref(false);

  /** Whether the drawer is minimized to a floating bubble */
  const minimized = ref(false);

  function toggle() {
    if (open.value) {
      minimize();
    } else {
      open.value = true;
      minimized.value = false;
      hasUnread.value = false;
    }
  }

  function show() {
    open.value = true;
    minimized.value = false;
    hasUnread.value = false;
  }

  function hide() {
    open.value = false;
    minimized.value = false;
  }

  function minimize() {
    open.value = false;
    minimized.value = activeConversationId.value !== null;
  }

  function restore() {
    open.value = true;
    minimized.value = false;
    hasUnread.value = false;
  }

  /**
   * Open the drawer and auto-select a specific agent.
   * The AIChatPanel will consume pendingAgentId on next loadAgents().
   */
  function openWithAgent(agentId: number) {
    pendingAgentId.value = agentId;
    open.value = true;
    minimized.value = false;
    hasUnread.value = false;
  }

  function resetConversation() {
    activeConversationId.value = null;
  }

  /** Consume and clear the pending agent ID */
  function consumePendingAgentId(): number | undefined {
    const id = pendingAgentId.value;
    pendingAgentId.value = undefined;
    return id;
  }

  // ============ Tool Call Handlers ============

  type ToolCallHandler = (toolName: string, output: string) => void;

  const toolCallHandlers = new Map<string, ToolCallHandler>();

  function registerToolCallHandler(key: string, handler: ToolCallHandler) {
    toolCallHandlers.set(key, handler);
  }

  function unregisterToolCallHandler(key: string) {
    toolCallHandlers.delete(key);
  }

  function dispatchToolCall(toolName: string, output: string) {
    for (const [key, handler] of toolCallHandlers) {
      try {
        handler(toolName, output);
      } catch (err) {
        console.error(
          `[GlobalAIChat] Tool call handler '${key}' error:`,
          err,
        );
      }
    }
  }

  function markUnread() {
    if (!open.value) hasUnread.value = true;
  }

  function $reset() {
    open.value = false;
    minimized.value = false;
    selectedAgentId.value = null;
    activeConversationId.value = null;
    pendingAgentId.value = undefined;
    hasUnread.value = false;
    toolCallHandlers.clear();
  }

  return {
    open,
    selectedAgentId,
    activeConversationId,
    pendingAgentId,
    hasUnread,
    minimized,
    markUnread,
    toggle,
    show,
    hide,
    minimize,
    restore,
    openWithAgent,
    resetConversation,
    consumePendingAgentId,
    registerToolCallHandler,
    unregisterToolCallHandler,
    dispatchToolCall,
    $reset,
  };
});
