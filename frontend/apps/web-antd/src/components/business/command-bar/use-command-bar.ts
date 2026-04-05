import type { Ref } from 'vue';

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
 * - Menu search (smart detection)
 * 管理 Command Bar 的逻辑状态：
 * - 开关控制（Ctrl+K 快捷键）
 * - 输入内容管理
 * - @mention 智能体选择
 * - AI Panel 联动
 * - 最近对话列表
 * - 菜单搜索（智能判断）
 */
import type { MenuRecordRaw } from '@vben/types';

import type { AgentItem, ConversationItem } from '#/types/ai-chat';
import type {
  MenuNavigationEntry,
  MenuNavigationSearchResult,
} from '#/utils/menu-navigation';

import { computed, onMounted, onUnmounted, ref, unref, watch } from 'vue';

import { $t } from '@vben/locales';

import {
  getChatAgentsApi,
  getGlobalConversationsApi,
  updateChatConversationTitleApi,
} from '#/api/shared/ai-chat';
import { useAIPanelStore } from '#/store';
import { getEndpointFromPath } from '#/utils';
import { normalizeStarterQuestions } from '#/utils/ai-starter-questions';
import {
  buildMenuNavigationEntries,
  searchMenuNavigationEntries,
} from '#/utils/menu-navigation';

/** Command Bar mode / Command Bar 模式 */
export type CommandBarMode = 'input' | 'mention';

export interface UseCommandBarOptions {
  /** API prefix / API 前缀 */
  apiPrefix: Ref<string> | string;
  /** Whether user has AI chat permission / 是否有 AI 聊天权限 */
  canChat: Ref<boolean>;
  /** Menu tree for search / 搜索用菜单树 */
  menus: Ref<MenuRecordRaw[]>;
}

export function useCommandBar(options: UseCommandBarOptions) {
  const aiPanelStore = useAIPanelStore();
  const AGENT_CACHE_TTL_MS = 60_000;

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
  const agentsLoadedAt = ref(0);

  /** @mention filter keyword / @mention 过滤关键词 */
  const mentionQuery = ref('');

  /** Recent conversation list / 最近对话列表 */
  const recentConversations = ref<ConversationItem[]>([]);

  /** Recent conversations loading state / 最近对话加载中 */
  const recentLoading = ref(false);

  // ==================== Menu search / 菜单搜索 ====================

  const searchItems = ref<MenuNavigationEntry[]>([]);

  function _buildSearchItems(menus: MenuRecordRaw[]) {
    searchItems.value = buildMenuNavigationEntries({
      currentEndpoint: getEndpointFromPath(unref(options.apiPrefix)),
      menus,
      translate: $t,
    });
  }

  watch(
    () => unref(options.menus),
    (menus) => {
      if (menus && menus.length > 0) {
        _buildSearchItems(menus);
      }
    },
    { immediate: true },
  );

  const menuSearchResults = computed<MenuNavigationSearchResult[]>(() => {
    const text = inputText.value.trim();
    if (!text || text.startsWith('@') || mode.value === 'mention') return [];
    return searchMenuNavigationEntries(searchItems.value, text);
  });

  function getMenuBreadcrumb(item: MenuNavigationEntry): string {
    return item.breadcrumb.slice(0, -1).join(' / ');
  }

  // ==================== 计算属性 / computed ====================

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

  const selectedAgent = computed(() => {
    const pinnedAgentId = aiPanelStore.pinnedAgentId;
    if (!pinnedAgentId) return null;
    return agents.value.find((agent) => agent.id === pinnedAgentId) ?? null;
  });

  const effectiveWelcomeMessage = computed(
    () => selectedAgent.value?.welcome_message || '',
  );

  const effectiveSuggestedQuestions = computed<string[]>(() =>
    normalizeStarterQuestions(selectedAgent.value?.suggested_questions),
  );

  // ==================== 打开/关闭 / open & close ====================

  /**
   * Show Command Bar / 显示 Command Bar
   */
  async function show() {
    if (!unref(options.canChat)) return;
    open.value = true;
    mode.value = 'input';
    mentionQuery.value = '';
    void loadRecentConversations();
    if (
      aiPanelStore.pinnedAgentId &&
      !agents.value.some((agent) => agent.id === aiPanelStore.pinnedAgentId)
    ) {
      await loadAgents();
    }
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
      void show();
    }
  }

  // ==================== 快捷键 / hotkeys ====================

  /**
   * Handle keydown event / 处理按键事件
   * @param e KeyboardEvent
   */
  function _handleKeydown(e: KeyboardEvent) {
    // Ctrl+K (or Cmd+K on macOS) / 打开命令面板快捷键
    if (
      (e.ctrlKey || e.metaKey) &&
      typeof e.key === 'string' &&
      e.key.toLowerCase() === 'k'
    ) {
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

  // ==================== 智能体列表 / agents ====================

  /**
   * Load agent list / 加载智能体列表
   */
  async function loadAgents(force = false) {
    if (agentsLoading.value) return;
    const isCacheFresh =
      agents.value.length > 0 &&
      Date.now() - agentsLoadedAt.value < AGENT_CACHE_TTL_MS;
    if (!force && isCacheFresh) return;
    agentsLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix);
      const res = await getChatAgentsApi<AgentItem>(prefix);
      agents.value = res.items;
      agentsLoadedAt.value = Date.now();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      agentsLoading.value = false;
    }
  }

  /**
   * Force refresh agent list / 强制刷新智能体列表
   */
  async function refreshAgents() {
    agents.value = [];
    agentsLoadedAt.value = 0;
    await loadAgents(true);
  }

  // ==================== 最近对话 / recent chats ====================

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
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      recentLoading.value = false;
    }
  }

  /**
   * Update conversation title / 更新对话标题
   */
  async function updateConversationTitle(convId: number, title: string) {
    try {
      const prefix = unref(options.apiPrefix);
      await updateChatConversationTitleApi(prefix, convId, title);
      const conv = recentConversations.value.find((c) => c.id === convId);
      if (conv) conv.title = title || null;
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  // ==================== @mention / @提及 ====================

  /**
   * Enter @mention mode / 进入 @mention 模式
   * Triggered when user types @ / 当用户输入 @ 时触发
   */
  function enterMentionMode() {
    mode.value = 'mention';
    mentionQuery.value = '';
    void loadAgents();
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
    agentsLoadedAt.value = 0;
    agentsLoading.value = false;
  }

  return {
    // State / 状态
    open,
    inputText,
    mode,
    agents,
    agentsLoading,
    mentionQuery,
    filteredAgents,
    selectedAgent,
    effectiveWelcomeMessage,
    effectiveSuggestedQuestions,
    recentConversations,
    recentLoading,
    menuSearchResults,
    getMenuBreadcrumb,

    // Actions / 动作
    show,
    hide,
    toggle,
    loadAgents,
    refreshAgents,
    loadRecentConversations,
    updateConversationTitle,
    enterMentionMode,
    selectMentionAgent,
    exitMentionMode,
    onInputChange,
    submit,
    $reset,
  };
}
