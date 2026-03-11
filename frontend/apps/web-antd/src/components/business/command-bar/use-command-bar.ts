/**
 * Command Bar State Management Composable
 * Command Bar 状态管理 Composable
 *
 * Manages Command Bar logical state:
 * - Toggle control (Ctrl+K shortcut)
 * - Input content management
 * - @mention agent selection
 * - AI Panel linkage
 * - Recent conversation list
 * 管理 Command Bar 的逻辑状态：
 * - 开关控制（Ctrl+K 快捷键）
 * - 输入内容管理
 * - @mention 智能体选择
 * - AI Panel 联动
 * - 最近对话列表
 */
import { type Ref, computed, onMounted, onUnmounted, ref, unref } from 'vue';

import type {
  AgentItem,
  ConversationItem,
} from '#/components/business/ai-chat-panel/types';

import {
  getChatAgentsApi,
  getGlobalConversationsApi,
} from '#/api/shared/ai-chat';
import { useAIPanelStore } from '#/store';

/** Command Bar mode / Command Bar 模式 */
export type CommandBarMode = 'input' | 'mention';

export interface UseCommandBarOptions {
  /** API prefix / API 前缀 */
  apiPrefix: Ref<string> | string;
  /** Whether user has AI chat permission / 是否有 AI 聊天权限 */
  canChat: Ref<boolean>;
}

export function useCommandBar(options: UseCommandBarOptions) {
  const aiPanelStore = useAIPanelStore();

  // ==================== State / 状态 ====================

  /** Whether Command Bar is open / 是否打开 Command Bar */
  const open = ref(false);

  /** Input text content / 输入文本内容 */
  const inputText = ref('');

  /** Current mode (input or mention) / 当前模式（输入或提及） */
  const mode = ref<CommandBarMode>('input');

  /** Available agent list / 可用智能体列表 */
  const agents = ref<AgentItem[]>([]);

  /** Agent loading state / 智能体加载中 */
  const agentsLoading = ref(false);

  /** @mention filter keyword / @mention 过滤关键词 */
  const mentionQuery = ref('');

  /** Recent conversation list / 最近对话列表 */
  const recentConversations = ref<ConversationItem[]>([]);

  /** Recent conversations loading state / 最近对话加载中 */
  const recentLoading = ref(false);

  // ==================== 计算属性 ====================

  /** Filtered agent list by @mention query / @mention 过滤后的智能体列表 */
  const filteredAgents = computed(() => {
    const query = mentionQuery.value.toLowerCase();
    if (!query) return agents.value;
    return agents.value.filter(
      (a) =>
        a.name.toLowerCase().includes(query) ||
        (a.description && a.description.toLowerCase().includes(query)),
    );
  });

  // ==================== 打开/关闭 ====================

  /**
   * Show Command Bar / 显示 Command Bar
   */
  function show() {
    if (!unref(options.canChat)) return;
    open.value = true;
    mode.value = 'input';
    mentionQuery.value = '';
    loadRecentConversations();
  }

  /**
   * Hide Command Bar / 隐藏 Command Bar
   */
  function hide() {
    open.value = false;
    inputText.value = '';
    mode.value = 'input';
    mentionQuery.value = '';
  }

  /**
   * Toggle Command Bar / 切换 Command Bar
   */
  function toggle() {
    if (open.value) {
      hide();
    } else {
      show();
    }
  }

  // ==================== 快捷键 ====================

  /**
   * Handle keydown event / 处理按键事件
   * @param e KeyboardEvent
   */
  function _handleKeydown(e: KeyboardEvent) {
    // Ctrl+K (or Cmd+K on macOS)
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      e.stopPropagation();
      toggle();
      return;
    }

    // ---- State / 状态 ----
    // Esc 关闭 Command Bar
    if (e.key === 'Escape' && open.value) {
      e.preventDefault();
      hide();
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', _handleKeydown, { capture: true });
  });

  onUnmounted(() => {
    document.removeEventListener('keydown', _handleKeydown, { capture: true });
  });

  // ==================== 智能体列表 ====================

  /**
   * Load agent list / 加载智能体列表
   */
  async function loadAgents() {
    if (agents.value.length > 0) return;
    agentsLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix);
      const res = await getChatAgentsApi<AgentItem>(prefix);
      agents.value = res.items;
    } catch {
      // handled by interceptor
    } finally {
      agentsLoading.value = false;
    }
  }

  /**
   * Force refresh agent list / 强制刷新智能体列表
   */
  async function refreshAgents() {
    agents.value = [];
    await loadAgents();
  }

  // ==================== 最近对话 ====================

  /**
   * Load recent conversation list / 加载最近对话列表
   */
  async function loadRecentConversations() {
    recentLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix);
      const res = await getGlobalConversationsApi<ConversationItem>(prefix, 7);
      recentConversations.value = res.items.slice(0, 7);
    } catch {
      // handled by interceptor
    } finally {
      recentLoading.value = false;
    }
  }

  // ==================== @mention ====================

  /**
   * Enter @mention mode / 进入 @mention 模式
   * Triggered when user types @ / 当用户输入 @ 时触发
   */
  function enterMentionMode() {
    mode.value = 'mention';
    mentionQuery.value = '';
    loadAgents();
  }

  /**
   * Select @mention agent / 选择 @mention 智能体
   * If already pinned, unpin (toggle); otherwise pin the agent / 如果已固定则取消固定（toggle），否则固定该智能体
   * Return to input mode / 回到输入模式
   * @param agent AgentItem
   */
  function selectMentionAgent(agent: AgentItem) {
    aiPanelStore.togglePin(agent.id, agent.name);
    mode.value = 'input';
    mentionQuery.value = '';
    // Remove @xxx prefix from input / 移除输入中的 @xxx 前缀
    const text = inputText.value.replace(/^@\S*\s?/, '');
    inputText.value = text;
  }

  /**
   * Exit @mention mode / 退出 @mention 模式
   */
  function exitMentionMode() {
    mode.value = 'input';
    mentionQuery.value = '';
  }

  // ==================== Input handling / 输入处理 ====================

  /**
   * Handle input change / 处理输入变化
   * Detects @ character, auto-enters/exits mention mode / 检测 @ 字符，自动进入/退出 mention 模式
   * @param value string
   */
  function onInputChange(value: string) {
    inputText.value = value;

    if (mode.value === 'mention') {
      // ---- Agent Loading / Agent 加载 ----
      // Update mention filter word (text after @) / 更新 mention 过滤词（@ 后面的文字）
      const match = /^@(\S*)/.exec(value);
      if (match) {
        mentionQuery.value = match[1] || '';
      } else {
        // User deleted @, exit mention mode / 用户删除了 @，退出 mention 模式
        exitMentionMode();
      }
    } else if (value.startsWith('@')) {
      enterMentionMode();
    }
  }

  // ==================== Send message / 发送消息 ====================

  /**
   * Submit message
   * 提交消息
   *
   * Passes message to AI Panel for handling (Panel handles routing and streaming).
   * 将消息传递给 AI Panel 处理（由 Panel 负责路由和流式请求）。
   * Command Bar only collects input and opens Panel.
   * Command Bar 只负责收集输入并打开 Panel。
   *
   * @returns Submitted message text (empty string means only open panel, no message) / 提交的消息文本（空字符串表示仅打开面板，不发消息）
   */
  function submit(): string {
    const message = inputText.value.trim();

    // Close Command Bar / 关闭 Command Bar
    hide();

    // Open AI Panel / 打开 AI Panel
    if (!aiPanelStore.visible) {
      aiPanelStore.open();
    }

    return message;
  }

  // ==================== Reset / 重置 ====================

  function $reset() {
    open.value = false;
    inputText.value = '';
    mode.value = 'input';
    mentionQuery.value = '';
    agents.value = [];
    agentsLoading.value = false;
  }

  return {
    // State
    open,
    inputText,
    mode,
    agents,
    agentsLoading,
    mentionQuery,
    filteredAgents,
    recentConversations,
    recentLoading,

    // Actions
    show,
    hide,
    toggle,
    loadAgents,
    refreshAgents,
    loadRecentConversations,
    enterMentionMode,
    selectMentionAgent,
    exitMentionMode,
    onInputChange,
    submit,
    $reset,
  };
}
