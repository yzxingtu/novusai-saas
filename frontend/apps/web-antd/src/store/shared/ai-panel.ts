/**
 * AI Panel state management / AI Panel 状态管理
 *
 * Manages AI slide panel global state: visibility, mode, active conversation,
 * pinned agent, tool call dispatch, etc. Replaces global-ai-chat.ts.
 * 管理 AI 侧滑面板的全局状态。
 */
import { ref } from 'vue';

import { defineStore } from 'pinia';

/** Panel display mode / 面板显示模式 */
export type AIPanelMode = 'full' | 'panel';

export interface PendingToolAction {
  invokeId: string;
  pageKey: string;
  operationName: string;
  operationLabel: string;
  operationDescription: string;
  params: Record<string, unknown>;
  resolved: boolean;
  allowed?: boolean;
  resolve: (allowed: boolean) => void;
  /** Timestamp when confirmation was requested (for 60s countdown) / 请求确认的时间戳（用于 60s 倒计时） */
  startedAt: number;
  /** Tool call ID for inlining confirmation card under the message / 工具调用 ID，用于在对应消息内联显示确认卡片 */
  toolCallId?: string;
}

export interface AIInteractionUpdate {
  action?: string;
  auto_approved?: boolean;
  kind: 'action_buttons' | 'pending_confirmation' | 'pending_consent';
  rejected?: boolean;
  table?: string;
  tool_name?: string;
  value?: string;
}

export const useAIPanelStore = defineStore('ai-panel', () => {
  // ==================== Panel state / 面板状态 ====================

  /** Whether panel is visible / 面板是否可见 */
  const visible = ref(false);

  /** Panel mode: panel (slide) / full (fullscreen) / 面板模式 */
  const mode = ref<AIPanelMode>('panel');

  /** Whether panel is minimized to floating bubble / 面板是否最小化为浮动气泡 */
  const minimized = ref(false);

  /** Whether panel is docked (pushes main content; undocked closes on outside click) / 面板是否固定 */
  const docked = ref(true);

  /** Panel current width (for layout sync, updates on drag) / 面板当前宽度 */
  const panelWidth = ref(460);

  // ==================== Conversation state / 对话状态 ====================

  /** Active conversation ID (null = new conversation) / 活跃对话 ID */
  const activeConversationId = ref<null | number>(null);

  /** Current conversation's main agent ID (for list display) / 当前对话的主智能体 ID */
  const activeAgentId = ref<null | number>(null);

  // ==================== Pinned agent / 固定智能体（Pin） ====================

  /** User-pinned agent ID (bypasses routing, uses this agent directly) / 用户固定的智能体 ID */
  const pinnedAgentId = ref<null | number>(null);

  /** Pinned agent name (for UI display) / 固定的智能体名称 */
  const pinnedAgentName = ref<null | string>(null);

  // ==================== Pending state / 待消费状态 ====================

  /** Agent ID set by external page to open / 外部页面设置的待打开智能体 ID */
  const pendingAgentId = ref<number | undefined>(undefined);

  /** Pending external message to send after panel opens / 面板打开后待发送的外部消息 */
  const pendingMessage = ref<null | string>(null);

  /** Pending conversation to restore after panel opens / 面板打开后待恢复的对话 */
  const pendingConversationId = ref<null | number>(null);

  /** Whether there are unread messages / 是否有未读消息 */
  const hasUnread = ref(false);

  // ==================== Panel actions / 面板操作 ====================

  function open() {
    visible.value = true;
    minimized.value = false;
    hasUnread.value = false;
  }

  function close() {
    visible.value = false;
    minimized.value = false;
  }

  function toggle() {
    if (visible.value) {
      minimize();
    } else {
      open();
    }
  }

  function minimize() {
    visible.value = false;
    minimized.value = activeConversationId.value !== null;
  }

  function restore() {
    visible.value = true;
    minimized.value = false;
    hasUnread.value = false;
  }

  function setFullMode() {
    mode.value = 'full';
  }

  function setPanelMode() {
    mode.value = 'panel';
  }

  function toggleMode() {
    mode.value = mode.value === 'panel' ? 'full' : 'panel';
  }

  function toggleDock() {
    docked.value = !docked.value;
  }

  // ==================== Conversation actions / 对话操作 ====================

  function setConversation(conversationId: null | number, agentId?: number) {
    activeConversationId.value = conversationId;
    if (agentId !== undefined) {
      activeAgentId.value = agentId;
    }
  }

  function resetConversation() {
    activeConversationId.value = null;
    activeAgentId.value = null;
  }

  // ==================== Pin actions / Pin 操作 ====================

  function pinAgent(agentId: number, agentName: string) {
    pinnedAgentId.value = agentId;
    pinnedAgentName.value = agentName;
  }

  function unpinAgent() {
    pinnedAgentId.value = null;
    pinnedAgentName.value = null;
  }

  function togglePin(agentId: number, agentName: string) {
    if (pinnedAgentId.value === agentId) {
      unpinAgent();
    } else {
      pinAgent(agentId, agentName);
    }
  }

  // ==================== External entry / 外部入口 ====================

  /**
   * Open panel from external page and preselect agent
   * 从外部页面打开面板并预选智能体
   */
  function openWithAgent(agentId: number) {
    pendingAgentId.value = agentId;
    open();
  }

  function queueMessage(message: null | string | undefined) {
    const normalized = message?.trim();
    pendingMessage.value = normalized || null;
  }

  function consumePendingMessage(): null | string {
    const message = pendingMessage.value;
    pendingMessage.value = null;
    return message;
  }

  function queueConversationRestore(conversationId: null | number | undefined) {
    pendingConversationId.value =
      typeof conversationId === 'number' && Number.isFinite(conversationId)
        ? conversationId
        : null;
  }

  function consumePendingConversationId(): null | number {
    const conversationId = pendingConversationId.value;
    pendingConversationId.value = null;
    return conversationId;
  }

  function openWithContext(options?: {
    agentId?: number;
    conversationId?: null | number;
    message?: null | string;
  }) {
    if (
      typeof options?.agentId === 'number' &&
      Number.isFinite(options.agentId)
    ) {
      pendingAgentId.value = options.agentId;
    }
    if (options?.message !== undefined) {
      queueMessage(options.message);
    }
    if (options?.conversationId !== undefined) {
      queueConversationRestore(options.conversationId);
    }
    open();
  }

  /**
   * Consume and clear pending agent ID / 消费并清除待使用的智能体 ID
   */
  function consumePendingAgentId(): number | undefined {
    const id = pendingAgentId.value;
    pendingAgentId.value = undefined;
    return id;
  }

  function markUnread() {
    if (!visible.value) {
      hasUnread.value = true;
    }
  }

  // ==================== Tool Action Confirmation / 工具动作确认 ====================

  const pendingToolActions = ref<PendingToolAction[]>([]);
  const pendingInteractionUpdates = ref<AIInteractionUpdate[]>([]);
  const RESOLVED_TOOL_ACTION_TTL_MS = 1500;
  const toolActionCleanupTimers = new Map<string, ReturnType<typeof setTimeout>>();

  function clearToolActionCleanupTimer(invokeId: string) {
    const timerId = toolActionCleanupTimers.get(invokeId);
    if (timerId !== undefined) {
      clearTimeout(timerId);
      toolActionCleanupTimers.delete(invokeId);
    }
  }

  function removeToolAction(invokeId: string) {
    clearToolActionCleanupTimer(invokeId);
    pendingToolActions.value = pendingToolActions.value.filter(
      (op) => op.invokeId !== invokeId,
    );
  }

  function scheduleResolvedToolActionCleanup(invokeId: string) {
    clearToolActionCleanupTimer(invokeId);
    const timerId = setTimeout(() => {
      removeToolAction(invokeId);
    }, RESOLVED_TOOL_ACTION_TTL_MS);
    toolActionCleanupTimers.set(invokeId, timerId);
  }

  function requestToolActionConfirmation(op: {
    invokeId: string;
    operationDescription: string;
    operationLabel: string;
    operationName: string;
    pageKey: string;
    params: Record<string, unknown>;
    toolCallId?: string;
  }): Promise<boolean> {
    clearResolvedToolActions();
    const existing = pendingToolActions.value.find(
      (item) => item.invokeId === op.invokeId,
    );
    if (existing && !existing.resolved) {
      existing.resolved = true;
      existing.allowed = false;
      existing.resolve(false);
    }
    removeToolAction(op.invokeId);
    return new Promise<boolean>((resolvePromise) => {
      pendingToolActions.value.push({
        ...op,
        resolved: false,
        resolve: resolvePromise,
        startedAt: Date.now(),
      });
    });
  }

  function resolveToolAction(invokeId: string, allowed: boolean) {
    const op = pendingToolActions.value.find((o) => o.invokeId === invokeId);
    if (!op || op.resolved) return;
    op.resolved = true;
    op.allowed = allowed;
    op.resolve(allowed);
    scheduleResolvedToolActionCleanup(invokeId);
  }

  function clearResolvedToolActions() {
    for (const op of pendingToolActions.value) {
      if (op.resolved) {
        clearToolActionCleanupTimer(op.invokeId);
      }
    }
    pendingToolActions.value = pendingToolActions.value.filter((o) => !o.resolved);
  }

  function queueInteractionUpdate(update: AIInteractionUpdate) {
    pendingInteractionUpdates.value.push({ ...update });
  }

  function consumeInteractionUpdates(): AIInteractionUpdate[] {
    const updates = [...pendingInteractionUpdates.value];
    pendingInteractionUpdates.value = [];
    return updates;
  }

  function restoreInteractionUpdates(updates: AIInteractionUpdate[]) {
    if (updates.length === 0) return;
    pendingInteractionUpdates.value = [
      ...updates.map((item) => ({ ...item })),
      ...pendingInteractionUpdates.value,
    ];
  }

  // ==================== Tool call dispatch / Tool Call 分发 ====================

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
      } catch (error) {
        console.warn(`[AIPanel] Tool call handler '${key}' error:`, error);
      }
    }
  }

  // ==================== Reset / 重置 ====================

  function $reset() {
    visible.value = false;
    mode.value = 'panel';
    minimized.value = false;
    docked.value = true;
    panelWidth.value = 460;
    activeConversationId.value = null;
    activeAgentId.value = null;
    pinnedAgentId.value = null;
    pinnedAgentName.value = null;
    pendingAgentId.value = undefined;
    pendingMessage.value = null;
    pendingConversationId.value = null;
    hasUnread.value = false;
    for (const invokeId of toolActionCleanupTimers.keys()) {
      clearToolActionCleanupTimer(invokeId);
    }
    pendingToolActions.value = [];
    pendingInteractionUpdates.value = [];
    toolCallHandlers.clear();
  }

  return {
    // State / 状态
    visible,
    mode,
    minimized,
    docked,
    panelWidth,
    activeConversationId,
    activeAgentId,
    pinnedAgentId,
    pinnedAgentName,
    pendingAgentId,
    pendingMessage,
    pendingConversationId,
    hasUnread,

    // Panel actions / 面板操作
    open,
    close,
    toggle,
    minimize,
    restore,
    setFullMode,
    setPanelMode,
    toggleMode,
    toggleDock,

    // Conversation / 会话
    setConversation,
    resetConversation,

    // Pin / 置顶
    pinAgent,
    unpinAgent,
    togglePin,

    // External / 外部
    openWithAgent,
    openWithContext,
    queueMessage,
    consumePendingMessage,
    queueConversationRestore,
    consumePendingConversationId,
    consumePendingAgentId,
    markUnread,
    // Tool action confirmation / 工具动作确认
    pendingToolActions,
    requestToolActionConfirmation,
    resolveToolAction,
    queueInteractionUpdate,
    consumeInteractionUpdates,
    restoreInteractionUpdates,
    clearResolvedToolActions,

    // Tool calls / 工具调用
    registerToolCallHandler,
    unregisterToolCallHandler,
    dispatchToolCall,

    // Reset / 重置
    $reset,
  };
});
