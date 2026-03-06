/**
 * Command Bar Composable
 *
 * 管理 Command Bar 的逻辑状态：
 * - 全局快捷键 Ctrl+J 打开/关闭
 * - 输入文本与 @mention 智能体选择
 * - 发送消息后联动 AI Panel 打开
 * - 最近对话列表快速恢复
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

/** Command Bar 模式 */
export type CommandBarMode = 'input' | 'mention';

export interface UseCommandBarOptions {
  /** API 前缀（响应式） */
  apiPrefix: Ref<string> | string;
  /** 是否有 AI 聊天权限 */
  canChat: Ref<boolean>;
}

export function useCommandBar(options: UseCommandBarOptions) {
  const aiPanelStore = useAIPanelStore();

  // ==================== 状态 ====================

  /** Command Bar 是否打开 */
  const open = ref(false);

  /** 当前输入文本 */
  const inputText = ref('');

  /** 当前模式 */
  const mode = ref<CommandBarMode>('input');

  /** 可用智能体列表（@mention 用） */
  const agents = ref<AgentItem[]>([]);

  /** 智能体加载中 */
  const agentsLoading = ref(false);

  /** @mention 过滤关键词 */
  const mentionQuery = ref('');

  /** 最近对话列表（最多 7 条） */
  const recentConversations = ref<ConversationItem[]>([]);

  /** 最近对话加载中 */
  const recentLoading = ref(false);

  // ==================== 计算属性 ====================

  /** @mention 过滤后的智能体列表 */
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

  function show() {
    if (!unref(options.canChat)) return;
    open.value = true;
    mode.value = 'input';
    mentionQuery.value = '';
    loadRecentConversations();
  }

  function hide() {
    open.value = false;
    inputText.value = '';
    mode.value = 'input';
    mentionQuery.value = '';
  }

  function toggle() {
    if (open.value) {
      hide();
    } else {
      show();
    }
  }

  // ==================== 快捷键 ====================

  function _handleKeydown(e: KeyboardEvent) {
    // Ctrl+J (or Cmd+J on macOS)
    if ((e.ctrlKey || e.metaKey) && e.key === 'j') {
      e.preventDefault();
      e.stopPropagation();
      toggle();
      return;
    }

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

  /** 强制刷新智能体列表 */
  async function refreshAgents() {
    agents.value = [];
    await loadAgents();
  }

  // ==================== 最近对话 ====================

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
   * 进入 @mention 模式
   * 当用户输入 @ 时触发
   */
  function enterMentionMode() {
    mode.value = 'mention';
    mentionQuery.value = '';
    loadAgents();
  }

  /**
   * 选择 @mention 的智能体
   * 如果已固定则取消固定（toggle），否则固定该智能体
   * 回到输入模式
   */
  function selectMentionAgent(agent: AgentItem) {
    aiPanelStore.togglePin(agent.id, agent.name);
    mode.value = 'input';
    mentionQuery.value = '';
    // 移除输入中的 @xxx 前缀
    const text = inputText.value.replace(/^@\S*\s?/, '');
    inputText.value = text;
  }

  /** 退出 @mention 模式 */
  function exitMentionMode() {
    mode.value = 'input';
    mentionQuery.value = '';
  }

  // ==================== 输入处理 ====================

  /**
   * 处理输入变化
   * 检测 @ 字符，自动进入/退出 mention 模式
   */
  function onInputChange(value: string) {
    inputText.value = value;

    if (mode.value === 'mention') {
      // 更新 mention 过滤词（@ 后面的文字）
      const match = /^@(\S*)/.exec(value);
      if (match) {
        mentionQuery.value = match[1] || '';
      } else {
        // 用户删除了 @，退出 mention 模式
        exitMentionMode();
      }
    } else if (value.startsWith('@')) {
      enterMentionMode();
    }
  }

  // ==================== 发送消息 ====================

  /**
   * 提交消息
   *
   * 将消息传递给 AI Panel 处理（由 Panel 负责路由和流式请求）。
   * Command Bar 只负责收集输入并打开 Panel。
   *
   * @returns 提交的消息文本（空字符串表示仅打开面板，不发消息）
   */
  function submit(): string {
    const message = inputText.value.trim();

    // 关闭 Command Bar
    hide();

    // 打开 AI Panel
    if (!aiPanelStore.visible) {
      aiPanelStore.open();
    }

    return message;
  }

  // ==================== 重置 ====================

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
