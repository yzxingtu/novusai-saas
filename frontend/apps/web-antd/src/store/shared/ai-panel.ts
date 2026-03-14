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

  function setConversation(conversationId: number | null, agentId?: number) {
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

  // ==================== Page Operation Confirmation / 页面操作确认 ====================

  interface PendingPageOp {
    invokeId: string;
    pageKey: string;
    operationName: string;
    operationLabel: string;
    operationDescription: string;
    params: Record<string, unknown>;
    resolved: boolean;
    allowed?: boolean;
    resolve: (allowed: boolean) => void;
  }

  const pendingPageOps = ref<PendingPageOp[]>([]);

  function requestPageOpConfirmation(op: {
    invokeId: string;
    pageKey: string;
    operationName: string;
    operationLabel: string;
    operationDescription: string;
    params: Record<string, unknown>;
  }): Promise<boolean> {
    return new Promise<boolean>((resolvePromise) => {
      pendingPageOps.value.push({
        ...op,
        resolved: false,
        resolve: resolvePromise,
      });
    });
  }

  function resolvePageOp(invokeId: string, allowed: boolean) {
    const op = pendingPageOps.value.find((o) => o.invokeId === invokeId);
    if (!op || op.resolved) return;
    op.resolved = true;
    op.allowed = allowed;
    op.resolve(allowed);
  }

  function clearResolvedPageOps() {
    pendingPageOps.value = pendingPageOps.value.filter((o) => !o.resolved);
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
        console.error(`[AIPanel] Tool call handler '${key}' error:`, error);
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
    hasUnread.value = false;
    pendingPageOps.value = [];
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
    consumePendingAgentId,
    markUnread,

    // Page operation confirmation / 页面操作确认
    pendingPageOps,
    requestPageOpConfirmation,
    resolvePageOp,
    clearResolvedPageOps,

    // Tool calls / 工具调用
    registerToolCallHandler,
    unregisterToolCallHandler,
    dispatchToolCall,

    // Reset / 重置
    $reset,
  };
});
