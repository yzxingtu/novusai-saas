/**
 * AI Panel 状态管理
 *
 * 管理 AI 侧滑面板的全局状态：可见性、模式、活跃对话、
 * 固定智能体、工具调用分发等。替代 global-ai-chat.ts。
 */
import { ref } from 'vue';

import { defineStore } from 'pinia';

/** 面板显示模式 */
export type AIPanelMode = 'full' | 'panel';

export const useAIPanelStore = defineStore('ai-panel', () => {
  // ==================== 面板状态 ====================

  /** 面板是否可见 */
  const visible = ref(false);

  /** 面板模式：panel（侧滑） / full（全屏） */
  const mode = ref<AIPanelMode>('panel');

  /** 面板是否最小化为浮动气泡 */
  const minimized = ref(false);

  /** 面板是否固定（固定时推开主内容，不固定时点击外部关闭） */
  const docked = ref(true);

  /** 面板当前宽度（用于布局联动，拖拽时实时更新） */
  const panelWidth = ref(460);

  // ==================== 对话状态 ====================

  /** 活跃对话 ID（null = 新对话） */
  const activeConversationId = ref<null | number>(null);

  /** 当前对话的主智能体 ID（列表展示用） */
  const activeAgentId = ref<null | number>(null);

  // ==================== 固定智能体（Pin） ====================

  /** 用户固定的智能体 ID（绕过路由，直接使用该智能体） */
  const pinnedAgentId = ref<null | number>(null);

  /** 固定的智能体名称（UI 展示用） */
  const pinnedAgentName = ref<null | string>(null);

  // ==================== 待消费状态 ====================

  /** 外部页面设置的待打开智能体 ID */
  const pendingAgentId = ref<number | undefined>(undefined);

  /** 是否有未读消息 */
  const hasUnread = ref(false);

  // ==================== 面板操作 ====================

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

  // ==================== 对话操作 ====================

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

  // ==================== Pin 操作 ====================

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

  // ==================== 外部入口 ====================

  /**
   * 从外部页面打开面板并预选智能体
   */
  function openWithAgent(agentId: number) {
    pendingAgentId.value = agentId;
    open();
  }

  /**
   * 消费并清除待使用的智能体 ID
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

  // ==================== Tool Call 分发 ====================

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

  // ==================== 重置 ====================

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
    toolCallHandlers.clear();
  }

  return {
    // State
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

    // Panel actions
    open,
    close,
    toggle,
    minimize,
    restore,
    setFullMode,
    setPanelMode,
    toggleMode,
    toggleDock,

    // Conversation
    setConversation,
    resetConversation,

    // Pin
    pinAgent,
    unpinAgent,
    togglePin,

    // External
    openWithAgent,
    consumePendingAgentId,
    markUnread,

    // Tool calls
    registerToolCallHandler,
    unregisterToolCallHandler,
    dispatchToolCall,

    // Reset
    $reset,
  };
});
