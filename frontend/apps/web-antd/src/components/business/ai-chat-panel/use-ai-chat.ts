/**
 * AI 对话 Composable / AI Chat Composable
 *
 * 封装全部 AI 对话业务逻辑：智能体加载、会话管理、SSE 流式、文件上传、
 * 工具调用、授权确认等。全页对话与全局抽屉对话共用。
 * Encapsulates all AI chat business logic: agent loading, conversation management,
 * SSE streaming, file uploads, tool calls, consent handling.
 * Used by both the full-page chat and the global drawer chat.
 */
import type { Ref } from 'vue';

import type {
  ActionButton,
  AgentItem,
  ChatAttachment,
  ChatMessage,
  ConversationItem,
  InteractionMode,
  MentionCandidate,
  PendingConfirmation,
  PendingConsent,
  RagSource,
  ToolCallEvent,
} from './types';

import type {
  AgentChatRequestBody,
  ChatKBBindingInfo,
  ConversationDetailResponse,
  MemoryState,
  PageContext,
  RawMessageItem,
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/ai-chat';
import type { AppErrorInfo } from '#/utils/request';

import { computed, nextTick, ref, unref, watch } from 'vue';

import { message } from 'ant-design-vue';

import {
  buildChatAttachmentFromUpload,
  clearChatConversationMemoryApi,
  deleteChatConversationApi,
  getChatAgentKBBindingsApi,
  getChatAgentsApi,
  getChatConversationMemoryApi,
  getChatConversationMessagesApi,
  getGlobalConversationsApi,
  sendChatStreamApi,
  updateChatConversationTitleApi,
  uploadChatFileApi,
} from '#/api/shared/ai-chat';
import { normalizePageKey } from '#/components/business/ai-slide-panel/page-key-utils';
import { useFileUpload } from '#/composables/use-file-upload';
import { CHAT_ACCEPT_ATTRIBUTE } from '#/constants/upload';
import { $t } from '#/locales';
import { useSocketIOStore } from '#/store';
import { useAIPanelStore } from '#/store/shared/ai-panel';
import { waitForPageSessionJoin } from '#/composables/use-page-operation-channel';
import {
  addConsent,
  clearConsents,
  getConsentedActions,
} from '#/utils/ai-consent';
import { showRequestError } from '#/utils/error-helpers';
import { toAvatarDisplayUrl } from '#/utils/image';
import {
  normalizeSseEventError,
  normalizeSseTransportError,
} from '#/utils/request';
import { resolveRoutePageKey } from '#/components/business/ai-slide-panel/page-key-utils';

import {
  extractLeadingAgentMentionDraft,
  filterKnowledgeBasesByMentionQuery,
  moveStreamingContentToThinking,
} from './chat-input-utils';
import { resolveConversationRequestState } from './conversation-binding';
import { getAgentInputVariables } from './types';

export interface UseAIChatOptions {
  /** API prefix: '/admin', '/tenant', or '/api/user' / API 前缀 */
  apiPrefix: Ref<string> | string;
  /** Upload endpoint / 上传接口地址 */
  uploadUrl: Ref<string> | string;
  /** Initial agent ID to auto-select after loading agents / 加载后默认选中的智能体 ID */
  initialAgentId?: number | Ref<number | undefined>;
  /** Initial conversation ID to auto-load after agent is selected / 选中智能体后默认加载的对话 ID */
  initialConversationId?: number | Ref<number | undefined>;
  /** Callback when a tool call completes successfully / 工具调用成功回调 */
  onToolCall?: (toolName: string, output: string) => void;
  /** Callback when streaming completes (used for unread badge) / 流式结束回调（未读角标等） */
  onStreamComplete?: () => void;
  pageContextResolver?: () => null | PageContext;
  pageSessionIdGetter?: () => string;
  /** Callback when required input variables are missing — opens the vars modal / 必填变量缺失时回调，打开变量弹窗 */
  onVariablesMissing?: () => void;
}

export function useAIChat(options: UseAIChatOptions) {
  const { validateChatFile, revokePreviewUrls } = useFileUpload();
  const socketIOStore = useSocketIOStore();
  const aiPanelStore = useAIPanelStore();
  const PAGE_OPERATION_SOCKET_READY_TIMEOUT_MS = 3000;
  const PAGE_OPERATION_SOCKET_READY_POLL_MS = 100;
  const PAGE_OPERATION_SOCKET_SETTLE_MS = 250;

  const interactionMode = ref<InteractionMode>('confirm');

  function refreshPageSessionRoom(pageContext?: null | PageContext): void {
    const pageSessionId = options.pageSessionIdGetter?.();
    if (!pageSessionId || !socketIOStore.isConnected) return;
    socketIOStore.emit('page_session_join', {
      page_session_id: pageSessionId,
      page_key:
        normalizePageKey(pageContext?.page_key ?? '') ||
        resolveRoutePageKey(undefined, window.location.pathname),
    });
  }

  function hasPageOperations(pageContext?: null | PageContext): boolean {
    const availableOperations = pageContext?.page_data?.available_operations;
    return Array.isArray(availableOperations) && availableOperations.length > 0;
  }

  function resolveSocketEndpoint(
    apiPrefix: string,
  ): 'admin' | 'tenant' | 'user' {
    if (apiPrefix.startsWith('/admin')) {
      return 'admin';
    }
    if (apiPrefix.startsWith('/api/user')) {
      return 'user';
    }
    return 'tenant';
  }

  async function ensurePageOperationChannelReady(
    apiPrefix: string,
    pageContext?: null | PageContext,
  ): Promise<boolean> {
    if (!hasPageOperations(pageContext) || !options.pageSessionIdGetter) {
      return true;
    }

    if (!socketIOStore.isConnected) {
      socketIOStore.connect?.(resolveSocketEndpoint(apiPrefix));

      const startedAt = Date.now();
      while (
        !socketIOStore.isConnected &&
        Date.now() - startedAt < PAGE_OPERATION_SOCKET_READY_TIMEOUT_MS
      ) {
        await new Promise<void>((resolve) => {
          setTimeout(resolve, PAGE_OPERATION_SOCKET_READY_POLL_MS);
        });
      }
    }

    if (!socketIOStore.isConnected) {
      return false;
    }

    refreshPageSessionRoom(pageContext);
    const pageSessionId = options.pageSessionIdGetter?.() || '';
    const pageKey =
      normalizePageKey(pageContext?.page_key ?? '') ||
      resolveRoutePageKey(undefined, window.location.pathname);
    if (!pageSessionId || !pageKey) {
      return false;
    }
    const joined = await waitForPageSessionJoin(
      pageSessionId,
      pageKey,
      PAGE_OPERATION_SOCKET_READY_TIMEOUT_MS,
      PAGE_OPERATION_SOCKET_READY_POLL_MS,
    );
    if (!joined) {
      return false;
    }
    await new Promise<void>((resolve) => {
      setTimeout(resolve, PAGE_OPERATION_SOCKET_SETTLE_MS);
    });
    return true;
  }

  // ============ Agents / 智能体 ============

  const agents = ref<AgentItem[]>([]);
  const agentsLoading = ref(false);
  const selectedAgentId = ref<null | number>(null);

  const selectedAgent = computed(
    () => agents.value.find((a) => a.id === selectedAgentId.value) ?? null,
  );

  /**
   * Load agents list and auto-select one / 加载智能体列表并自动选中一个
   * @param overrideAgentId - If provided, takes priority over options.initialAgentId
   */
  async function loadAgents(overrideAgentId?: number) {
    agentsLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix) as string;
      const res = await getChatAgentsApi<AgentItem>(prefix);
      agents.value = res.items.map((agent) => {
        const avatar = toAvatarDisplayUrl(agent.avatar ?? undefined);
        return {
          ...agent,
          avatar: avatar || null,
        };
      });
      const firstAgent = res.items[0];
      if (firstAgent && !selectedAgentId.value) {
        const initId = overrideAgentId ?? unref(options.initialAgentId);
        selectedAgentId.value =
          initId && res.items.some((a) => a.id === initId)
            ? initId
            : firstAgent.id;
      }
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      agentsLoading.value = false;
    }
  }

  function selectAgent(agentId: number) {
    if (selectedAgentId.value === agentId) return;
    abortActiveStream();
    clearConsents();
    selectedAgentId.value = agentId;
    conversationsRequestSeq += 1;
    messagesRequestSeq += 1;
    activeConversationId.value = null;
    activeConversationAgentId.value = null;
    clearConversationAnchor();
    chatMessages.value = [];
    conversationContextDiagnostics.value = null;
    lastRunSummary.value = null;
    clearPendingAttachments();
    clearMentionDraft();
    // Clear cached variables when switching agents / 切换智能体时清空缓存变量
    // (they'll be re-initialized via watch + openVarsModal in the page component) / 由页面 watch 与弹窗再初始化
  }

  // ============ Conversations / 会话 ============

  const conversations = ref<ConversationItem[]>([]);
  const conversationsLoading = ref(false);
  const activeConversationId = ref<null | number>(null);
  const activeConversationAgentId = ref<null | number>(null);
  const conversationContextDiagnostics = ref<null | Record<string, unknown>>(
    null,
  );
  const clearingMemory = ref(false);
  const lastRunSummary = ref<null | Record<string, unknown>>(null);
  const memoryState = ref<MemoryState | null>(null);
  const memoryLoading = ref(false);
  const lastMemoryUpdated = ref(false);
  let conversationAnchorId: null | number = null;
  let conversationAnchorAgentId: null | number = null;

  /** Request sequence guard: prevents stale async responses from overriding latest state / 请求序号防护：避免旧异步响应覆盖最新状态 */
  let conversationsRequestSeq = 0;
  let messagesRequestSeq = 0;
  let clientMessageSeq = 0;
  const INTERRUPTED_HISTORY_SYNC_ATTEMPTS = 3;
  const INTERRUPTED_HISTORY_SYNC_RETRY_DELAY_MS = 300;

  function nextClientKey(prefix: string) {
    clientMessageSeq += 1;
    return `${prefix}-${Date.now()}-${clientMessageSeq}`;
  }

  function rememberConversationAnchor(
    conversationId: null | number,
    agentId?: null | number,
  ) {
    if (typeof conversationId === 'number' && Number.isFinite(conversationId)) {
      conversationAnchorId = conversationId;
    }
    if (agentId !== undefined) {
      conversationAnchorAgentId = agentId ?? null;
    }
  }

  function clearConversationAnchor() {
    conversationAnchorId = null;
    conversationAnchorAgentId = null;
  }

  async function loadConversations() {
    const reqSeq = ++conversationsRequestSeq;
    conversationsLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix) as string;
      const res = await getGlobalConversationsApi<ConversationItem>(prefix);
      if (reqSeq !== conversationsRequestSeq) {
        return;
      }
      conversations.value = res.items.filter(
        (conversation) =>
          (conversation.message_count ?? 0) > 0 ||
          conversation.id === activeConversationId.value,
      );

      // Auto-load initial conversation (only once) / 仅一次自动加载初始会话
      const initConvId = unref(options.initialConversationId);
      if (
        initConvId &&
        !_initialConvRestored &&
        conversations.value.some((c) => c.id === initConvId)
      ) {
        _initialConvRestored = true;
        await loadConversationMessages(initConvId);
      }
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      if (reqSeq === conversationsRequestSeq) {
        conversationsLoading.value = false;
      }
    }
  }

  function applyConversationDetailState(
    convId: number,
    res: ConversationDetailResponse,
    mergedMessages = mergeMessagesForDisplay(res.message_list ?? []),
  ) {
    const resolvedAgentId =
      res.agent_id ??
      activeConversationAgentId.value ??
      conversationAnchorAgentId ??
      selectedAgentId.value;
    if (resolvedAgentId) {
      selectedAgentId.value = resolvedAgentId;
      activeConversationAgentId.value = resolvedAgentId;
    }
    rememberConversationAnchor(convId, resolvedAgentId ?? null);

    const agentId = selectedAgentId.value;
    if (agentId) {
      ensureAgentVarsLoaded(agentId);
    }

    chatMessages.value = mergedMessages;
    conversationContextDiagnostics.value =
      (res.context_diagnostics as null | Record<string, unknown> | undefined) ??
      null;
    lastRunSummary.value =
      (res.last_run_summary as null | Record<string, unknown> | undefined) ??
      null;
    lastMemoryUpdated.value = mergedMessages.some((m) => m.memoryUpdated);
    interactionMode.value = res.interaction_mode_effective ?? 'confirm';
    scrollToBottom(true);
  }

  async function syncConversationAfterInterrupt(
    convId: number,
    minimumMessageCount: number,
  ) {
    await loadConversations();
    if (activeConversationId.value !== convId) {
      return;
    }

    const prefix = unref(options.apiPrefix) as string;
    let fallbackMerged: ChatMessage[] | null = null;
    let fallbackResponse: ConversationDetailResponse | null = null;

    for (
      let attempt = 0;
      attempt < INTERRUPTED_HISTORY_SYNC_ATTEMPTS;
      attempt++
    ) {
      const res = await getChatConversationMessagesApi(prefix, convId);
      if (activeConversationId.value !== convId) {
        return;
      }

      const merged = mergeMessagesForDisplay(res.message_list ?? []);
      fallbackResponse = res;
      fallbackMerged = merged;

      if (minimumMessageCount <= 0 || merged.length >= minimumMessageCount) {
        applyConversationDetailState(convId, res, merged);
        return;
      }

      if (attempt < INTERRUPTED_HISTORY_SYNC_ATTEMPTS - 1) {
        await new Promise<void>((resolve) => {
          setTimeout(resolve, INTERRUPTED_HISTORY_SYNC_RETRY_DELAY_MS);
        });
      }
    }

    if (
      !fallbackResponse ||
      !fallbackMerged ||
      activeConversationId.value !== convId
    ) {
      return;
    }

    if (
      minimumMessageCount > 0 &&
      fallbackMerged.length < minimumMessageCount &&
      chatMessages.value.length >= minimumMessageCount
    ) {
      return;
    }

    applyConversationDetailState(convId, fallbackResponse, fallbackMerged);
  }

  /**
   * Reset chat state / 重置对话状态
   * @param keepVars - When true (panel open/reopen), session vars are preserved.
   *                   When false (explicit "+" new chat), session vars are cleared.
   */
  function startNewConversation(keepVars = false) {
    abortActiveStream();
    clearConsents();
    messagesRequestSeq += 1;
    if (debounceTimerId) {
      clearTimeout(debounceTimerId);
      debounceTimerId = null;
    }
    pendingMessages.value = [];
    activeConversationId.value = null;
    activeConversationAgentId.value = null;
    clearConversationAnchor();
    chatMessages.value = [];
    conversationContextDiagnostics.value = null;
    lastRunSummary.value = null;
    clearMentionDraft();
    memoryState.value = null;
    lastMemoryUpdated.value = false;
    if (!keepVars) {
      allAgentsVariables.value = {};
    }
  }

  async function deleteConversation(convId: number) {
    try {
      const prefix = unref(options.apiPrefix) as string;
      await deleteChatConversationApi(prefix, convId);
      if (activeConversationId.value === convId) {
        clearConsents();
        messagesRequestSeq += 1;
        activeConversationId.value = null;
        activeConversationAgentId.value = null;
        clearConversationAnchor();
        chatMessages.value = [];
      }
      await loadConversations();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  async function updateConversationTitle(convId: number, title: string) {
    try {
      const prefix = unref(options.apiPrefix) as string;
      await updateChatConversationTitleApi(prefix, convId, title);
      const conv = conversations.value.find((c) => c.id === convId);
      if (conv) conv.title = title || null;
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  async function loadConversationMessages(convId: number) {
    abortActiveStream();
    clearConsents();
    const reqSeq = ++messagesRequestSeq;
    if (debounceTimerId) {
      clearTimeout(debounceTimerId);
      debounceTimerId = null;
    }
    pendingMessages.value = [];
    activeConversationId.value = convId;
    clearMentionDraft();
    const currentConversation = conversations.value.find(
      (c) => c.id === convId,
    );
    if (currentConversation?.agent_id) {
      selectedAgentId.value = currentConversation.agent_id;
      activeConversationAgentId.value = currentConversation.agent_id;
      rememberConversationAnchor(convId, currentConversation.agent_id);
    } else {
      activeConversationAgentId.value = null;
      rememberConversationAnchor(convId);
    }
    try {
      const prefix = unref(options.apiPrefix) as string;
      const res = await getChatConversationMessagesApi(prefix, convId);
      if (
        reqSeq !== messagesRequestSeq ||
        activeConversationId.value !== convId
      ) {
        return;
      }
      applyConversationDetailState(convId, res);
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

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

  function resolveToolCallStatus(
    response: undefined | { success: boolean },
    persistedTc: Record<string, unknown>,
  ): ToolCallEvent['status'] {
    if (response) {
      return response.success ? 'success' : 'error';
    }
    if (persistedTc.pending_confirmation || persistedTc.pending_consent) {
      return 'running';
    }
    if (persistedTc.success === true) {
      return 'success';
    }
    return 'error';
  }

  function normalizeStringList(value: unknown): string[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((item) => String(item ?? '').trim())
      .filter((item) => item.length > 0);
  }

  function normalizeOptionalString(value: unknown): string | undefined {
    if (typeof value !== 'string') {
      return undefined;
    }
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : undefined;
  }

  function normalizeContextSources(value: unknown): TurnContextSourcePayload[] {
    if (!Array.isArray(value)) {
      return [];
    }
    const normalized: TurnContextSourcePayload[] = [];
    for (const item of value) {
      if (!item || typeof item !== 'object') {
        continue;
      }
      const payload = item as Record<string, unknown>;
      const source: TurnContextSourcePayload = {};
      const kind = normalizeOptionalString(payload.kind);
      const name = normalizeOptionalString(payload.name);
      if (kind) {
        source.kind = kind;
      }
      if (name) {
        source.name = name;
      }
      if (typeof payload.active === 'boolean') {
        source.active = payload.active;
      }
      if (payload.metadata && typeof payload.metadata === 'object') {
        source.metadata = payload.metadata as Record<string, unknown>;
      }
      normalized.push(source);
    }
    return normalized;
  }

  function normalizeTurnRecord(value: unknown): null | TurnRecordPayload {
    if (!value || typeof value !== 'object') {
      return null;
    }
    const payload = value as Record<string, unknown>;
    const turnOutcome = normalizeOptionalString(payload.turn_outcome);
    const terminationReason = normalizeOptionalString(
      payload.termination_reason,
    );
    const protocolPath = normalizeOptionalString(payload.protocol_path);
    const selectedToolNames = normalizeStringList(payload.selected_tool_names);
    const selectedSkillNames = normalizeStringList(
      payload.selected_skill_names,
    );
    const contextSources = normalizeContextSources(payload.context_sources);
    const fallbackHistory = Array.isArray(payload.fallback_history)
      ? payload.fallback_history
          .filter((item): item is Record<string, unknown> => {
            return !!item && typeof item === 'object';
          })
          .map((item) => ({ ...item }))
      : [];
    const metadata =
      payload.metadata && typeof payload.metadata === 'object'
        ? ({ ...(payload.metadata as Record<string, unknown>) } as Record<
            string,
            unknown
          >)
        : undefined;
    return {
      turn_outcome: turnOutcome,
      termination_reason: terminationReason,
      protocol_path: protocolPath,
      selected_tool_names: selectedToolNames,
      selected_skill_names: selectedSkillNames,
      context_sources: contextSources,
      ...(fallbackHistory.length > 0
        ? { fallback_history: fallbackHistory }
        : {}),
      ...(metadata ? { metadata } : {}),
    };
  }

  function isTurnFailure(
    turnOutcome?: string,
    terminationReason?: string,
  ): boolean {
    const normalizedOutcome = normalizeOptionalString(turnOutcome);
    const normalizedTermination = normalizeOptionalString(terminationReason);
    const failureOutcomes = new Set(['error', 'failed', 'tool_round_failed']);
    const failureTerminations = new Set(['error', 'failed', 'tool_error']);
    return (
      (normalizedOutcome ? failureOutcomes.has(normalizedOutcome) : false) ||
      (normalizedTermination
        ? failureTerminations.has(normalizedTermination)
        : false)
    );
  }

  /**
   * Merge raw DB messages into display ChatMessages / 将原始 DB 消息合并为展示用 ChatMessages
   *
   * During streaming, all tool call rounds are accumulated into a single
   * assistant ChatMessage. But the DB stores each round as separate messages:
   *   assistant (tool_calls) → tool → assistant (tool_calls) → tool → ... → assistant (final content)
   *
   * This function groups consecutive non-user messages between user messages
   * into a single ChatMessage with toolCalls reconstructed.
   */
  function mergeMessagesForDisplay(
    rawMessages: RawMessageItem[],
  ): ChatMessage[] {
    // Filter out system messages / 过滤 system 消息
    const filtered = rawMessages.filter((m) => m.role !== 'system');
    if (filtered.length === 0) return [];

    const result: ChatMessage[] = [];

    // Collect tool responses keyed by tool_call_id for quick lookup / 按 tool_call_id 索引 tool 回包
    const toolResponseMap = new Map<
      string,
      {
        content: string;
        displayName?: string;
        error?: string;
        errorType?: string;
        name?: string;
        resultLink?: string;
        success: boolean;
        summary?: string;
        summaryPayload?: Record<string, unknown>;
      }
    >();
    for (const m of filtered) {
      if (m.role === 'tool' && m.tool_call_id) {
        const meta = (m.metadata ?? {}) as Record<string, unknown>;
        const toolSuccess = meta.tool_success !== false; // default true for legacy data
        toolResponseMap.set(m.tool_call_id, {
          content: m.content ?? '',
          success: toolSuccess,
          error: (meta.tool_error as string) || undefined,
          errorType: (meta.tool_error_type as string) || undefined,
          name: m.tool_name ?? undefined,
          displayName: (meta.tool_display_name as string) || undefined,
          summary: (meta.tool_summary as string) || undefined,
          summaryPayload:
            (meta.tool_summary_payload as Record<string, unknown>) || undefined,
          resultLink: (meta.tool_result_link as string) || undefined,
        });
      }
    }

    // Group consecutive non-user messages into assistant turns / 合并连续非 user 为助手轮次
    let i = 0;
    while (i < filtered.length) {
      const msg = filtered[i];
      if (!msg) break;

      if (msg.role === 'user') {
        result.push({
          clientKey: `persisted-user-${i}-${msg.created_at ?? ''}`,
          role: 'user',
          content: msg.content ?? '',
          attachments: msg.metadata?.attachments,
          ...(msg.created_at ? { created_at: msg.created_at } : {}),
        });
        i++;
        continue;
      }

      // Collect all consecutive non-user messages as one assistant turn / 单轮助手合并多条消息
      const toolCalls: ToolCallEvent[] = [];
      const contentParts: string[] = [];
      const thinkingContentParts: string[] = [];
      let hasMemoryUpdated = false;
      let hasPartial = false;
      let hasInterrupted = false;
      let turnCompletionReason: string | undefined;
      let turnTerminationReason: string | undefined;
      let turnOutcome: string | undefined;
      let turnProtocolPath: string | undefined;
      let turnSelectedSkillNames: string[] = [];
      let turnSelectedToolNames: string[] = [];
      let turnContextSources: TurnContextSourcePayload[] = [];
      let turnRecordPayload: null | TurnRecordPayload = null;
      let turnAgentId: null | number = null;
      let turnAgentName: null | string = null;
      let turnAgentAvatar: null | string = null;
      let turnAgentDescription: null | string = null;
      let turnModelName: null | string = null;
      let turnRouteSource: null | string = null;
      let turnCreatedAt: null | string = null;
      let turnRagSources: RagSource[] | undefined;
      let turnActionButtons: ActionButton[] | undefined;
      let turnActionButtonsUsed = false;
      let turnPendingConfirmation: PendingConfirmation | undefined;
      let turnPendingConsent: PendingConsent | undefined;
      const startIdx = i;

      while (i < filtered.length) {
        const current = filtered[i];
        if (!current || current.role === 'user') {
          break;
        }
        const cur = current;

        if (cur.role === 'assistant') {
          if (cur.created_at) turnCreatedAt = cur.created_at;
          // Capture agent info from the first assistant message in this turn / 本轮首条 assistant 取 agent 信息
          if (turnAgentId === null && cur.agent_id) {
            turnAgentId = cur.agent_id;
            turnAgentName = cur.agent_name ?? null;
            turnAgentAvatar = cur.agent_avatar ?? null;
            // Enrich from agents list / 从已加载 agents 列表补全描述等
            const agentInfo = agents.value.find((a) => a.id === cur.agent_id);
            if (agentInfo) {
              turnAgentDescription = agentInfo.description ?? null;
              if (!turnModelName) {
                turnModelName = agentInfo.model_name ?? null;
              }
              if (!turnAgentAvatar && agentInfo.avatar) {
                turnAgentAvatar = agentInfo.avatar;
              }
            }
          }
          if (turnModelName === null) {
            turnModelName =
              cur.model_name ??
              (typeof cur.metadata?.model_name === 'string'
                ? cur.metadata.model_name
                : null);
          }
          if (
            turnRouteSource === null &&
            typeof cur.metadata?.route_source === 'string'
          ) {
            turnRouteSource = cur.metadata.route_source;
          }
          if (Array.isArray(cur.metadata?.action_buttons)) {
            turnActionButtons = cur.metadata.action_buttons as ActionButton[];
          }
          if (cur.metadata?.action_buttons_used === true) {
            turnActionButtonsUsed = true;
          }
          if (
            !turnPendingConfirmation &&
            cur.metadata?.pending_confirmation &&
            typeof cur.metadata.pending_confirmation === 'object'
          ) {
            const pending = cur.metadata.pending_confirmation as Record<
              string,
              unknown
            >;
            turnPendingConfirmation = {
              action: String(pending.action || ''),
              table: String(pending.table || ''),
              preview: pending.preview as Record<string, unknown> | undefined,
              resolved: pending.resolved as boolean | undefined,
            };
          }
          if (
            !turnPendingConsent &&
            cur.metadata?.pending_consent &&
            typeof cur.metadata.pending_consent === 'object'
          ) {
            const pending = cur.metadata.pending_consent as Record<
              string,
              unknown
            >;
            turnPendingConsent = {
              toolName: String(pending.tool_name || pending.toolName || ''),
              arguments: pending.arguments as
                | Record<string, unknown>
                | undefined,
              skillName: (pending.skill_name as string) || undefined,
              skillType: (pending.package_name as string) || undefined,
              resolved: pending.resolved as boolean | undefined,
              rejected: pending.rejected as boolean | undefined,
              autoApproved:
                (pending.auto_approved as boolean | undefined) ??
                (pending.autoApproved as boolean | undefined),
            };
          }
          // Extract tool calls from this assistant message / 解析本条的 tool_calls
          if (cur.tool_calls && cur.tool_calls.length > 0) {
            for (const tc of cur.tool_calls) {
              const tcId = tc.id ?? '';
              const funcName = tc.function?.name ?? 'unknown';
              const persistedTc = tc as Record<string, unknown>;
              let parsedArgs: Record<string, unknown> | undefined;
              try {
                parsedArgs = tc.function?.arguments
                  ? JSON.parse(tc.function.arguments)
                  : undefined;
              } catch {
                parsedArgs = tc.function?.arguments
                  ? { raw: tc.function.arguments }
                  : undefined;
              }

              // Match with tool response (use metadata.tool_success for status) / 与 tool 回包对齐状态
              const response = tcId ? toolResponseMap.get(tcId) : undefined;

              if (
                !turnPendingConfirmation &&
                persistedTc.pending_confirmation &&
                typeof persistedTc.pending_confirmation === 'object'
              ) {
                const pending = persistedTc.pending_confirmation as Record<
                  string,
                  unknown
                >;
                turnPendingConfirmation = {
                  action: String(pending.action || ''),
                  table: String(pending.table || ''),
                  preview: pending.preview as
                    | Record<string, unknown>
                    | undefined,
                };
              }
              if (
                !turnPendingConsent &&
                persistedTc.pending_consent &&
                typeof persistedTc.pending_consent === 'object'
              ) {
                const pending = persistedTc.pending_consent as Record<
                  string,
                  unknown
                >;
                turnPendingConsent = {
                  toolName: String(
                    pending.tool_name || pending.toolName || funcName,
                  ),
                  arguments:
                    (pending.arguments as
                      | Record<string, unknown>
                      | undefined) ?? parsedArgs,
                  skillName: (pending.skill_name as string) || undefined,
                  skillType: (pending.package_name as string) || undefined,
                };
              }

              toolCalls.push({
                id: tcId || undefined,
                name: funcName,
                status: resolveToolCallStatus(response, persistedTc),
                arguments: parsedArgs,
                output: response?.success
                  ? response.content
                  : (persistedTc.output as string | undefined),
                error:
                  response && !response.success
                    ? response.error || response.content
                    : (persistedTc.error as string | undefined) ||
                      response?.error,
                durationMs: persistedTc.duration_ms as number | undefined,
                displayName:
                  (persistedTc.display_name as string) ?? response?.displayName,
                summary: (persistedTc.summary as string) ?? response?.summary,
                summaryPayload:
                  (persistedTc.summary_payload as Record<string, unknown>) ??
                  response?.summaryPayload,
                resultLink:
                  (persistedTc.result_link as string) ?? response?.resultLink,
                errorType:
                  (persistedTc.error_type as string) ?? response?.errorType,
                skillName:
                  (persistedTc.skill_name as string) ??
                  (persistedTc.package_name as string) ??
                  undefined,
              });
            }
          }

          // Check memory_updated flag in metadata / 检查 metadata 记忆更新标记
          if (cur.metadata?.memory_updated) {
            hasMemoryUpdated = true;
          }
          const turnRecord = normalizeTurnRecord(cur.metadata?.turn_record);
          if (turnRecord) {
            turnRecordPayload = turnRecord;
          }
          const metadataTurnOutcome = normalizeOptionalString(
            cur.metadata?.turn_outcome,
          );
          if (!turnOutcome && metadataTurnOutcome) {
            turnOutcome = metadataTurnOutcome;
          }
          if (!turnOutcome && turnRecord?.turn_outcome) {
            turnOutcome = turnRecord.turn_outcome;
          }
          const metadataTerminationReason = normalizeOptionalString(
            cur.metadata?.termination_reason,
          );
          if (!turnTerminationReason && metadataTerminationReason) {
            turnTerminationReason = metadataTerminationReason;
          }
          if (!turnTerminationReason && turnRecord?.termination_reason) {
            turnTerminationReason = turnRecord.termination_reason;
          }
          const metadataProtocolPath = normalizeOptionalString(
            cur.metadata?.protocol_path,
          );
          if (!turnProtocolPath && metadataProtocolPath) {
            turnProtocolPath = metadataProtocolPath;
          }
          if (!turnProtocolPath && turnRecord?.protocol_path) {
            turnProtocolPath = turnRecord.protocol_path;
          }
          const metadataSelectedToolNames = normalizeStringList(
            cur.metadata?.selected_tool_names,
          );
          if (metadataSelectedToolNames.length > 0) {
            turnSelectedToolNames = metadataSelectedToolNames;
          } else if (
            turnSelectedToolNames.length === 0 &&
            (turnRecord?.selected_tool_names?.length ?? 0) > 0
          ) {
            turnSelectedToolNames = [
              ...(turnRecord?.selected_tool_names ?? []),
            ];
          }
          const metadataSelectedSkillNames = normalizeStringList(
            cur.metadata?.selected_skill_names,
          );
          if (metadataSelectedSkillNames.length > 0) {
            turnSelectedSkillNames = metadataSelectedSkillNames;
          } else if (
            turnSelectedSkillNames.length === 0 &&
            (turnRecord?.selected_skill_names?.length ?? 0) > 0
          ) {
            turnSelectedSkillNames = [
              ...(turnRecord?.selected_skill_names ?? []),
            ];
          }
          const metadataContextSources = normalizeContextSources(
            cur.metadata?.context_sources,
          );
          if (metadataContextSources.length > 0) {
            turnContextSources = metadataContextSources;
          } else if (
            turnContextSources.length === 0 &&
            (turnRecord?.context_sources?.length ?? 0) > 0
          ) {
            turnContextSources = [...(turnRecord?.context_sources ?? [])];
          }
          if (cur.metadata?.partial || turnOutcome === 'partial') {
            hasPartial = true;
          }
          if (
            cur.metadata?.interrupted ||
            turnTerminationReason === 'interrupted'
          ) {
            hasInterrupted = true;
          }
          if (hasInterrupted) {
            hasPartial = true;
          }
          if (cur.metadata?.completion_reason) {
            turnCompletionReason = cur.metadata.completion_reason;
          }
          if (!turnCompletionReason && turnTerminationReason) {
            turnCompletionReason = turnTerminationReason;
          }
          const persistedThinking =
            typeof cur.metadata?.thinking_content === 'string'
              ? cur.metadata.thinking_content
              : '';
          if (persistedThinking.trim()) {
            thinkingContentParts.push(persistedThinking.trim());
          }

          // Accumulate content from all assistant messages in this turn / 拼接本轮所有 assistant 正文
          // (matches streaming behavior where all deltas are concatenated) / 与流式增量拼接行为一致
          if (cur.content && cur.content.trim()) {
            // Backward-compat: recover thinking from assistant.content when metadata lacks thinking_content / 向后兼容：旧轮次将思考写入 content，此处恢复为思考块以便历史展示
            if (cur.tool_calls?.length) {
              if (!persistedThinking.trim()) {
                thinkingContentParts.push(cur.content);
              }
            } else {
              contentParts.push(cur.content);
            }
          }
          const rs = cur.metadata?.rag_sources;
          if (Array.isArray(rs) && rs.length > 0) {
            turnRagSources = rs as RagSource[];
          }
        }
        // tool messages are already handled via toolResponseMap / tool 行已由 Map 处理
        i++;
      }

      // Only add if we actually processed something / 确有内容再推入助手消息
      if (i > startIdx) {
        const assistantMsg: ChatMessage = {
          clientKey: `persisted-assistant-${startIdx}-${turnCreatedAt ?? ''}`,
          role: 'assistant',
          content: contentParts.join('\n\n'),
          toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
          agent_id: turnAgentId,
          agent_name: turnAgentName,
          agent_avatar: turnAgentAvatar,
          agent_description: turnAgentDescription,
          model_name: turnModelName,
          routeSource: turnRouteSource,
        };
        if (turnRouteSource === 'rich_text_ai') {
          assistantMsg.source = 'rich_text_ai';
        }
        if (turnCreatedAt) assistantMsg.created_at = turnCreatedAt;
        if (hasMemoryUpdated) {
          assistantMsg.memoryUpdated = true;
        }
        if (hasPartial) {
          assistantMsg.partial = true;
        }
        if (hasInterrupted) {
          assistantMsg.interrupted = true;
        }
        if (turnOutcome) {
          assistantMsg.turnOutcome = turnOutcome;
        }
        if (turnTerminationReason) {
          assistantMsg.terminationReason = turnTerminationReason;
        }
        if (turnProtocolPath) {
          assistantMsg.protocolPath = turnProtocolPath;
        }
        if (turnSelectedToolNames.length > 0) {
          assistantMsg.selectedToolNames = turnSelectedToolNames;
        }
        if (turnSelectedSkillNames.length > 0) {
          assistantMsg.selectedSkillNames = turnSelectedSkillNames;
        }
        if (turnContextSources.length > 0) {
          assistantMsg.contextSources = turnContextSources;
        }
        if (turnRecordPayload) {
          assistantMsg.turnRecord = turnRecordPayload;
        }
        if (turnCompletionReason) {
          assistantMsg.completionReason = turnCompletionReason;
        }
        if (
          isTurnFailure(
            turnOutcome,
            turnTerminationReason ?? turnCompletionReason,
          )
        ) {
          assistantMsg.requestFailedRetry = true;
        }
        if (thinkingContentParts.length > 0) {
          assistantMsg.thinkingContent = thinkingContentParts.join('\n\n');
        }
        if (turnRagSources?.length) {
          assistantMsg.ragSources = turnRagSources;
        }
        if (turnActionButtons?.length) {
          assistantMsg.actionButtons = turnActionButtons;
        }
        if (turnActionButtonsUsed === true) {
          assistantMsg.actionButtonsUsed = true;
        }
        if (turnPendingConfirmation) {
          assistantMsg.pendingConfirmation = turnPendingConfirmation;
        }
        if (turnPendingConsent) {
          assistantMsg.pendingConsent = turnPendingConsent;
        }
        result.push(assistantMsg);
      }
    }

    return result;
  }

  // ============ Chat Messages / 消息区 ============

  /** Guard: only restore initialConversationId once / 仅恢复一次 initialConversationId */
  let _initialConvRestored = false;

  const chatMessages = ref<ChatMessage[]>([]);
  const inputMessage = ref('');
  const pendingInteractionUpdates = ref<
    Array<{
      action?: string;
      auto_approved?: boolean;
      kind: 'action_buttons' | 'pending_confirmation' | 'pending_consent';
      rejected?: boolean;
      table?: string;
      tool_name?: string;
      value?: string;
    }>
  >([]);
  const mentionQuery = ref('');
  const mentionActiveIndex = ref(0);
  const selectedKBIds = ref<number[]>([]);
  const agentKBBindings = ref<ChatKBBindingInfo[]>([]);
  /** @ 候选：仅当前智能体已绑定知识库 / Only KBs bound to the current agent */
  const mentionCandidates = computed<MentionCandidate[]>(() => {
    const draft = extractLeadingAgentMentionDraft(inputMessage.value);
    if (draft === null) {
      return [];
    }
    const kbMatches = filterKnowledgeBasesByMentionQuery(
      agentKBBindings.value,
      draft,
    );
    const out: MentionCandidate[] = [];
    for (const binding of kbMatches) {
      out.push({ kind: 'knowledge_base', binding });
    }
    return out;
  });
  const mentionOpen = computed(
    () => extractLeadingAgentMentionDraft(inputMessage.value) !== null,
  );

  watch(inputMessage, (value) => {
    const draft = extractLeadingAgentMentionDraft(value);
    if (draft === null) {
      mentionQuery.value = '';
      mentionActiveIndex.value = 0;
      return;
    }
    mentionQuery.value = draft;
  });

  watch(mentionCandidates, (candidates) => {
    if (candidates.length === 0) {
      mentionActiveIndex.value = 0;
      return;
    }
    if (mentionActiveIndex.value >= candidates.length) {
      mentionActiveIndex.value = candidates.length - 1;
    }
  });

  function selectMentionKnowledgeBase(
    binding: Pick<ChatKBBindingInfo, 'knowledge_base_id'>,
  ) {
    const id = binding.knowledge_base_id;
    if (!selectedKBIds.value.includes(id)) {
      selectedKBIds.value = [...selectedKBIds.value, id];
    }
    mentionQuery.value = '';
    mentionActiveIndex.value = 0;
    inputMessage.value = '';
  }

  function removeSelectedKnowledgeBase(knowledgeBaseId: number) {
    selectedKBIds.value = selectedKBIds.value.filter(
      (k) => k !== knowledgeBaseId,
    );
  }

  function clearMentionDraft() {
    mentionQuery.value = '';
    mentionActiveIndex.value = 0;
  }

  // ============ Input Variables / 输入变量 ============

  /** Per-agent variables: agentId → { varName: value } / 各智能体变量 */
  const allAgentsVariables = ref<Record<number, Record<string, string>>>({});

  function _varsLocalKey(agentId: number): string {
    return `ai-vars:${agentId}`;
  }

  function _saveVarsToStorage(agentId: number, vars: Record<string, string>) {
    try {
      localStorage.setItem(_varsLocalKey(agentId), JSON.stringify(vars));
    } catch {
      /* quota exceeded or private mode / 配额超限或隐私模式 */
    }
  }

  function _loadVarsFromStorage(
    agentId: number,
  ): null | Record<string, string> {
    try {
      const raw = localStorage.getItem(_varsLocalKey(agentId));
      return raw ? (JSON.parse(raw) as Record<string, string>) : null;
    } catch {
      return null;
    }
  }

  /**
   * Ensure session vars are initialized for an agent / 确保智能体的会话变量已初始化
   * If not yet in session, checks localStorage (for agents the user previously persisted).
   */
  function ensureAgentVarsLoaded(agentId: number) {
    if (!(agentId in allAgentsVariables.value)) {
      const stored = _loadVarsFromStorage(agentId);
      allAgentsVariables.value[agentId] = stored ?? {};
    }
  }

  /**
   * Save variables for an agent / 保存某智能体的变量
   * Always updates session vars (in-memory).
   * @param agentId - agent id to update
   * @param values - variable values for the agent
   * @param persist - if true, also writes to localStorage (long-term, auto-injected every session)
   *                  if false, only in-memory for this browser session
   */
  function applyVariables(
    agentId: number,
    values: Record<string, string>,
    persist = false,
  ) {
    allAgentsVariables.value[agentId] = { ...values };
    if (persist) {
      _saveVarsToStorage(agentId, { ...values });
    }
  }

  function resetVariables() {
    allAgentsVariables.value = {};
  }

  function clearConversationVarsCache() {
    // no-op: variables are now persisted per-agent, not per-conversation / 变量已按智能体持久化，此接口空操作
  }

  /** Agents that have appeared in the conversation AND have input_variables / 对话中出现且含 input_variables 的智能体 */
  const agentsWithVarsInConversation = computed(() => {
    const agentIdsInChat = new Set<number>(
      chatMessages.value.flatMap((message) =>
        message.role === 'assistant' && typeof message.agent_id === 'number'
          ? [message.agent_id]
          : [],
      ),
    );
    return agents.value.filter(
      (a) => agentIdsInChat.has(a.id) && getAgentInputVariables(a).length > 0,
    );
  });

  async function loadAgentKBBindings(agentId: number) {
    try {
      const prefix = unref(options.apiPrefix) as string;
      const items = await getChatAgentKBBindingsApi(prefix, agentId);
      agentKBBindings.value = items.filter((b) => b.enabled);
    } catch {
      agentKBBindings.value = [];
    }
  }

  /**
   * KB 绑定随当前选中智能体加载。
   * Bindings follow the currently selected agent.
   */
  const effectiveKbAgentId = computed(() => selectedAgentId.value ?? null);

  watch(
    effectiveKbAgentId,
    async (id) => {
      if (!id) {
        agentKBBindings.value = [];
        return;
      }
      await loadAgentKBBindings(id);
      const allowed = new Set(
        agentKBBindings.value.map((b) => b.knowledge_base_id),
      );
      selectedKBIds.value = selectedKBIds.value.filter((kid) =>
        allowed.has(kid),
      );
    },
    { immediate: true },
  );
  const sending = ref(false);
  const streaming = ref(false);

  /** 发送前 800ms 防抖：多条消息合并为一次请求 */
  const SEND_DEBOUNCE_MS = 800;
  const pendingMessages = ref<{ text: string }[]>([]);
  let debounceTimerId: null | ReturnType<typeof setTimeout> = null;
  const messagesContainer = ref<HTMLElement | null>(null);

  let streamAbortController: AbortController | null = null;
  type StreamAbortReason = 'context_switch' | 'none' | 'user';
  let activeStreamLifecycle: null | { abortReason: StreamAbortReason } = null;

  /**
   * Abort active SSE stream; call before switching agent/conversation or closing panel.
   * 终止当前 SSE 流；在切换 agent/对话或关闭面板前调用。
   */
  function abortActiveStream(markStoppedByUser = false): void {
    if (streamAbortController) {
      if (activeStreamLifecycle) {
        activeStreamLifecycle.abortReason = markStoppedByUser
          ? 'user'
          : 'context_switch';
      }
      streamAbortController.abort();
      streamAbortController = null;
    }
    sending.value = false;
    streaming.value = false;
    userScrolledUp.value = false;
    const last = chatMessages.value.at(-1);
    if (last?.streaming) {
      last.streaming = false;
      if (last.role === 'assistant' && markStoppedByUser) {
        last.stoppedByUser = true;
      }
    }
  }

  /** Deferred auto-confirm flag: set when trusted_auto auto-approves during active stream / 延迟自动确认标志 */
  let _deferredAutoConfirm = false;

  /** Whether user has manually scrolled up / 用户是否手动向上滚动 */
  const userScrolledUp = ref(false);
  /** Whether user has scrolled down from top (show scroll-to-top button) / 用户是否从顶部向下滚动 */
  const userNotAtTop = ref(false);

  /**
   * Smart scroll: only auto-scroll to bottom if user hasn't scrolled up / 智能滚动：仅当用户未上滑时自动滚到底部
   * @param force - if true, always scroll regardless of user position
   */
  function scrollToBottom(force = false) {
    nextTick(() => {
      const el = messagesContainer.value;
      if (!el) return;
      if (force || !userScrolledUp.value) {
        el.scrollTop = el.scrollHeight;
      }
    });
  }

  function scrollToTop() {
    nextTick(() => {
      const el = messagesContainer.value;
      if (!el) return;
      el.scrollTop = 0;
    });
  }

  /** Check if the user is near the bottom of the scroll container / 是否接近滚动容器底部 */
  function isNearBottom(): boolean {
    const el = messagesContainer.value;
    if (!el) return true;
    const threshold = 80;
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }

  /** Handle scroll events to detect manual user scroll-up / 处理滚动以检测用户手动上滑 */
  function handleMessagesScroll() {
    const el = messagesContainer.value;
    if (!el) return;
    userScrolledUp.value = !isNearBottom();
    userNotAtTop.value = el.scrollTop > 80;
  }

  async function copyMessage(content: string) {
    try {
      await navigator.clipboard.writeText(content);
      message.success($t('common.globalAiChat.copySuccess'));
    } catch {
      // fallback silently / 剪贴板失败则静默
    }
  }

  function handleInputKeyDown(e: KeyboardEvent): boolean {
    if (!mentionOpen.value) {
      return false;
    }
    const candidates = mentionCandidates.value;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (candidates.length > 0) {
        mentionActiveIndex.value =
          (mentionActiveIndex.value + 1) % candidates.length;
      }
      return true;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (candidates.length > 0) {
        mentionActiveIndex.value =
          (mentionActiveIndex.value - 1 + candidates.length) %
          candidates.length;
      }
      return true;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      inputMessage.value = '';
      clearMentionDraft();
      return true;
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      const target = candidates[mentionActiveIndex.value] ?? candidates[0];
      if (target) {
        selectMentionKnowledgeBase(target.binding as ChatKBBindingInfo);
      }
      return true;
    }
    return false;
  }

  // ============ Model Capabilities / 模型能力 ============

  /** 仅当后端明确 supports_vision=false 时禁止传图；未返回能力时保持兼容允许上传 */
  const supportsVision = computed(
    () => selectedAgent.value?.model_capabilities?.supports_vision !== false,
  );

  const totalTokensUsed = computed(() =>
    chatMessages.value.reduce((sum, m) => sum + (m.tokenUsage || 0), 0),
  );

  const imageParams = ref<{
    n: number;
    quality: string;
    size: string;
    style: string;
  }>({
    size: '1024x1024',
    quality: 'standard',
    style: 'vivid',
    n: 1,
  });

  const maxImageCount = computed(
    () => selectedAgent.value?.model_capabilities?.max_image_count ?? 5,
  );

  const maxImageSizeMb = computed(
    () => selectedAgent.value?.model_capabilities?.max_image_size_mb ?? 10,
  );

  /**
   * Validate a file before upload (images + non-images) / 上传前校验文件（图片与非图片）
   * Uses the unified useFileUpload composable.
   */
  function validateUpload(file: File): boolean {
    const currentImageCount = pendingAttachments.value.filter(
      (a) => a.type === 'image',
    ).length;
    const result = validateChatFile(file, {
      supportsVision: supportsVision.value,
      maxImageCount: maxImageCount.value,
      currentImageCount,
      maxImageSizeMb: maxImageSizeMb.value,
    });
    return result.valid;
  }

  // ============ File Uploads / 附件上传 ============

  const pendingAttachments = ref<ChatAttachment[]>([]);
  const uploading = ref(false);
  const fileInput = ref<HTMLInputElement | null>(null);
  /** Pre-built accept attribute for file input / 文件选择 accept 属性 */
  const chatAcceptAttribute = CHAT_ACCEPT_ATTRIBUTE;

  /**
   * Compress an image file using Canvas API / 使用 Canvas API 压缩图片
   * Returns the original file if compression is not possible or not needed.
   */
  async function compressImage(
    file: File,
    maxDimension = 2048,
    quality = 0.85,
  ): Promise<File> {
    return new Promise((resolve) => {
      const img = new Image();
      img.addEventListener('load', () => {
        URL.revokeObjectURL(img.src);
        let { width, height } = img;
        if (
          width <= maxDimension &&
          height <= maxDimension &&
          file.size < 1024 * 1024
        ) {
          resolve(file);
          return;
        }
        if (width > maxDimension || height > maxDimension) {
          const ratio = Math.min(maxDimension / width, maxDimension / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          resolve(file);
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);
        canvas.toBlob(
          (blob) => {
            if (!blob || blob.size >= file.size) {
              resolve(file);
              return;
            }
            resolve(
              new File([blob], file.name, {
                type: 'image/jpeg',
                lastModified: Date.now(),
              }),
            );
          },
          'image/jpeg',
          quality,
        );
      });
      img.addEventListener('error', () => {
        URL.revokeObjectURL(img.src);
        resolve(file);
      });
      img.src = URL.createObjectURL(file);
    });
  }

  /**
   * Determine extra upload form data based on API prefix / 根据 API 前缀确定上传表单额外字段
   * Admin endpoint needs tenant_id=0 for platform attachments.
   */
  function getUploadExtraData(): Record<string, string> | undefined {
    const prefix = unref(options.apiPrefix) as string;
    if (prefix.includes('/admin')) {
      return { tenant_id: '0' };
    }
    return undefined;
  }

  async function uploadFile(file: File): Promise<ChatAttachment | null> {
    uploading.value = true;
    try {
      const isImage = file.type.startsWith('image/');
      const fileToUpload = isImage ? await compressImage(file) : file;
      const data = await uploadChatFileApi(
        unref(options.uploadUrl) as string,
        fileToUpload,
        getUploadExtraData(),
      );
      const uploadedAttachment = buildChatAttachmentFromUpload(
        fileToUpload,
        data,
      );
      return {
        ...uploadedAttachment,
        preview: isImage ? URL.createObjectURL(fileToUpload) : undefined,
      };
    } catch (error: unknown) {
      showRequestError(error, 'common.uploadValidation.uploadFailed');
      return null;
    } finally {
      uploading.value = false;
    }
  }

  async function handleFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.length) return;
    for (const file of input.files) {
      if (!validateUpload(file)) continue;
      const att = await uploadFile(file);
      if (att) pendingAttachments.value.push(att);
    }
    input.value = '';
  }

  async function handlePaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;

    const imageFiles: File[] = [];
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) imageFiles.push(file);
      }
    }
    if (imageFiles.length === 0) return;

    e.preventDefault();

    for (const file of imageFiles) {
      if (!validateUpload(file)) continue;
      const att = await uploadFile(file);
      if (att) pendingAttachments.value.push(att);
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
  }

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (!files?.length) return;
    for (const file of files) {
      if (!validateUpload(file)) continue;
      const att = await uploadFile(file);
      if (att) pendingAttachments.value.push(att);
    }
  }

  function removePendingAttachment(idx: number) {
    const att = pendingAttachments.value[idx];
    if (att?.preview) URL.revokeObjectURL(att.preview);
    pendingAttachments.value.splice(idx, 1);
  }

  /** Clear pending attachments and revoke all preview URLs / 清空待上传附件并撤销预览 URL */
  function clearPendingAttachments() {
    revokePreviewUrls(pendingAttachments.value);
    pendingAttachments.value = [];
  }

  // ============ SSE Streaming / SSE 流式 ============

  /**
   * 解析 SSE 行。对 message/thinking 在 handler 后 await nextTick，避免同一次 fetch chunk
   * 内多次同步改内容被 Vue 批成一次渲染（表现为「突然全文出现」）。
   */
  async function parseSSEEvents(
    rawChunk: string,
    buffer: { value: string },
    handler: (data: string) => void,
  ) {
    buffer.value += rawChunk;
    const lines = buffer.value.split('\n');
    buffer.value = lines.pop() ?? '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('data: ')) {
        const data = trimmed.slice(6);
        handler(data);
        if (data === '[DONE]') continue;
        let needFlush = false;
        try {
          const ev = JSON.parse(data) as { event?: string };
          needFlush = ev.event === 'message' || ev.event === 'thinking';
        } catch {
          needFlush = true;
        }
        if (needFlush) await nextTick();
      }
    }
  }

  async function sendMessage(opts?: {
    agentId?: number;
    pageContext?: null | PageContext;
    routeSource?: null | string;
    silent?: boolean;
  }): Promise<boolean> {
    const silent = opts?.silent ?? false;
    const explicitAgentSelection =
      opts?.agentId !== null && opts?.agentId !== undefined;
    const anchoredConversationId =
      !explicitAgentSelection &&
      activeConversationId.value === null &&
      chatMessages.value.length > 0
        ? conversationAnchorId
        : null;
    const effectiveConversationId =
      activeConversationId.value ?? anchoredConversationId;
    const effectiveConversationAgentId =
      effectiveConversationId === null
        ? null
        : (activeConversationAgentId.value ?? conversationAnchorAgentId);
    const maybeTargetAgentId =
      opts?.agentId ?? effectiveConversationAgentId ?? selectedAgentId.value;
    const routeSource = opts?.routeSource ?? null;
    const pageContext =
      opts?.pageContext === undefined
        ? (options.pageContextResolver?.() ?? null)
        : opts.pageContext;
    const hasText = inputMessage.value.trim().length > 0;
    const hasAttachments = pendingAttachments.value.length > 0;
    const hasInteractionUpdates = pendingInteractionUpdates.value.length > 0;
    if (
      (!hasText && !hasAttachments && !hasInteractionUpdates) ||
      maybeTargetAgentId === null ||
      maybeTargetAgentId === undefined ||
      sending.value
    ) {
      return false;
    }
    const targetAgentId = maybeTargetAgentId;

    if (
      !explicitAgentSelection &&
      effectiveConversationId !== null &&
      activeConversationId.value === null
    ) {
      activeConversationId.value = effectiveConversationId;
    }
    if (
      !explicitAgentSelection &&
      effectiveConversationAgentId !== null &&
      activeConversationAgentId.value === null
    ) {
      activeConversationAgentId.value = effectiveConversationAgentId;
    }
    if (
      !explicitAgentSelection &&
      effectiveConversationAgentId !== null &&
      selectedAgentId.value !== effectiveConversationAgentId
    ) {
      // Follow conversation-bound agent unless user started a new route/switch turn / 除非显式新开路由或切换智能体，否则跟随会话绑定智能体
      selectedAgentId.value = effectiveConversationAgentId;
    }

    // Block sending if required input variables are not filled / 必填变量未填则拦截发送
    const agent = agents.value.find((a) => a.id === targetAgentId);
    const requiredVars = getAgentInputVariables(agent).filter(
      (v) => v.required,
    );
    if (requiredVars.length > 0) {
      ensureAgentVarsLoaded(targetAgentId);
      const agentVars = allAgentsVariables.value[targetAgentId] ?? {};
      const missingVars = requiredVars.filter(
        (v) => !agentVars[v.name]?.trim(),
      );
      if (missingVars.length > 0) {
        message.warning(
          $t('user.aiChat.varsModal.fillRequired', {
            fields: missingVars.map((v) => v.label || v.name).join('、'),
          }),
        );
        options.onVariablesMissing?.();
        return false;
      }
    }

    const conversationRequestState = resolveConversationRequestState({
      activeConversationAgentId:
        effectiveConversationAgentId ?? activeConversationAgentId.value,
      activeConversationId: effectiveConversationId,
      targetAgentId,
    });
    if (conversationRequestState.shouldForkConversation) {
      messagesRequestSeq += 1;
      activeConversationId.value = null;
      activeConversationAgentId.value = null;
      clearConversationAnchor();
      memoryState.value = null;
      lastMemoryUpdated.value = false;
    } else if (conversationRequestState.conversationId !== null) {
      rememberConversationAnchor(
        conversationRequestState.conversationId,
        effectiveConversationAgentId ?? targetAgentId,
      );
    }

    const userMsg = inputMessage.value.trim();
    const msgAttachments = [...pendingAttachments.value];
    /** 气泡展示用附件：去掉 preview，避免 clearPending 撤销 blob 后仍引用失效 URL */
    const displayAttachments =
      msgAttachments.length > 0
        ? msgAttachments.map(
            ({ attachment_id, type, url, name, mime_type }) => ({
              attachment_id,
              type,
              url,
              name,
              mime_type,
            }),
          )
        : undefined;

    const useDebounce =
      !silent &&
      !hasAttachments &&
      msgAttachments.length === 0 &&
      userMsg.length > 0 &&
      !routeSource;

    if (useDebounce) {
      if (!silent) {
        chatMessages.value.push({
          clientKey: nextClientKey('user'),
          role: 'user',
          content: userMsg,
          created_at: new Date().toISOString(),
        });
      }
      pendingMessages.value.push({ text: userMsg });
      inputMessage.value = '';
      clearPendingAttachments();
      userScrolledUp.value = false;
      scrollToBottom(true);

      if (debounceTimerId) clearTimeout(debounceTimerId);
      debounceTimerId = setTimeout(() => {
        debounceTimerId = null;
        flushPendingAndSend({
          targetAgentId,
          pageContext,
        });
      }, SEND_DEBOUNCE_MS);
      return true;
    }

    if (!silent) {
      chatMessages.value.push({
        clientKey: nextClientKey('user'),
        role: 'user',
        content: userMsg,
        attachments: displayAttachments,
        created_at: new Date().toISOString(),
      });
    }
    const targetAgent = agents.value.find((a) => a.id === targetAgentId);
    chatMessages.value.push({
      clientKey: nextClientKey('assistant'),
      role: 'assistant',
      content: '',
      streaming: true,
      agent_id: targetAgentId,
      agent_name: targetAgent?.name ?? null,
      agent_avatar: targetAgent?.avatar ?? null,
      agent_description: targetAgent?.description ?? null,
      model_name: targetAgent?.model_name ?? null,
      routeSource,
      created_at: new Date().toISOString(),
      ...(routeSource === 'rich_text_ai'
        ? { source: 'rich_text_ai' as const }
        : {}),
    });
    userScrolledUp.value = false;
    scrollToBottom(true);

    inputMessage.value = '';
    clearPendingAttachments();
    await nextTick();

    await doStreamRequest({
      texts: [userMsg],
      apiAttachments:
        msgAttachments.length > 0
          ? msgAttachments.map(
              ({ attachment_id, type, url, name, mime_type }) => ({
                attachment_id,
                type,
                url,
                name,
                mime_type,
              }),
            )
          : undefined,
      targetAgentId,
      pageContext,
      routeSource,
    });
    return true;
  }

  async function flushPendingAndSend(opts: {
    pageContext: null | PageContext;
    targetAgentId: number;
  }) {
    const msgs = [...pendingMessages.value];
    pendingMessages.value = [];
    if (msgs.length === 0) return;
    if (sending.value) return;

    const { targetAgentId, pageContext } = opts;
    const targetAgent = agents.value.find((a) => a.id === targetAgentId);
    chatMessages.value.push({
      clientKey: nextClientKey('assistant'),
      role: 'assistant',
      content: '',
      streaming: true,
      agent_id: targetAgentId,
      agent_name: targetAgent?.name ?? null,
      agent_avatar: targetAgent?.avatar ?? null,
      agent_description: targetAgent?.description ?? null,
      model_name: targetAgent?.model_name ?? null,
      created_at: new Date().toISOString(),
    });
    userScrolledUp.value = false;
    scrollToBottom(true);
    await nextTick();

    await doStreamRequest({
      texts: msgs.map((m) => m.text),
      apiAttachments: undefined,
      targetAgentId,
      pageContext,
    });
  }

  async function doStreamRequest(params: {
    apiAttachments?:
      | Pick<ChatAttachment, 'mime_type' | 'name' | 'type' | 'url'>[]
      | undefined;
    pageContext: null | PageContext;
    routeSource?: null | string;
    targetAgentId: number;
    texts: string[];
  }) {
    const { texts, apiAttachments, targetAgentId, pageContext, routeSource } =
      params;
    sending.value = true;
    streaming.value = true;
    const sseBuffer = { value: '' };
    streamAbortController = new AbortController();
    const requestAbortController = streamAbortController;
    const streamLifecycle = { abortReason: 'none' as StreamAbortReason };
    activeStreamLifecycle = streamLifecycle;
    const assistantIdx = chatMessages.value.length - 1;
    const interruptedHistoryBaseline = chatMessages.value.length;
    let doneAbortTimer: null | ReturnType<typeof setTimeout> = null;
    let didReceiveDoneEvent = false;
    let didSseEnd = false;
    let hasReceivedStreamPayload = false;
    let shouldSyncInterruptedConversation = false;
    let streamConversationId =
      activeConversationId.value ?? conversationAnchorId;

    function finalizeMessage() {
      const msg = chatMessages.value[assistantIdx];
      if (msg) {
        msg.streaming = false;
        if (msg.toolCalls) {
          const orphaned = msg.toolCalls.filter(
            (tc) => tc.status === 'running',
          );
          if (orphaned.length > 0) {
            console.warn(
              '[use-ai-chat] finalizeMessage: orphaned running tool(s), marking as error',
              orphaned.map((t) => ({ name: t.name, id: t.id })),
            );
          }
          for (const tc of msg.toolCalls) {
            if (tc.status === 'running') {
              tc.status = 'error';
            }
          }
        }
      }
    }

    function promoteToolRoundContent() {
      const msg = chatMessages.value[assistantIdx];
      if (!msg || msg.role !== 'assistant') {
        return;
      }
      moveStreamingContentToThinking(msg);
    }

    function applyAssistantError(
      msg: ChatMessage | undefined,
      appError: AppErrorInfo,
    ) {
      if (!msg) return;
      msg.error = appError;
      msg.requestFailedRetry = true;
      if (msg.content.trim().length > 0) {
        msg.partial = true;
      }
      msg.terminationReason = msg.terminationReason || 'error';
      msg.turnOutcome = msg.turnOutcome || 'failed';
      msg.completionReason = msg.completionReason || 'error';
    }

    function handleSsePayload(data: string) {
      if (data === '[DONE]') return;
      try {
        hasReceivedStreamPayload = true;
        const event = JSON.parse(data) as Record<string, unknown> & {
          delta?: string;
          event?: string;
        };
        const msg = chatMessages.value[assistantIdx];
        if (!msg) return;

        switch (event.event) {
          case 'optimizing_tools': {
            msg.optimizingTools = {
              total: (event.total as number) || 0,
              selected: (event.selected as number) || 0,
            };
            scrollToBottom();

            break;
          }
          case 'thinking': {
            if (event.delta) {
              msg.thinkingContent = `${msg.thinkingContent || ''}${event.delta}`;
              scrollToBottom();
            }

            break;
          }
          case 'tool_call': {
            promoteToolRoundContent();
            if (!msg.toolCalls) msg.toolCalls = [];
            let existing = msg.toolCalls.findLast(
              (tc) => tc.name === event.name && tc.status === 'running',
            );
            if (!existing) {
              existing = msg.toolCalls.findLast(
                (tc) => tc.status === 'running',
              );
            }
            if (existing) {
              existing.status = event.success ? 'success' : 'error';
              existing.durationMs = event.duration_ms as number | undefined;
              existing.output = event.output as string | undefined;
              existing.error = event.error as string | undefined;
              existing.errorType = event.error_type as string | undefined;
              if (event.skill_name)
                existing.skillName = event.skill_name as string;
              if (event.skill_type)
                existing.skillType = event.skill_type as string;
              if (event.display_name)
                existing.displayName = event.display_name as string;
              if (event.summary) existing.summary = event.summary as string;
              if (event.summary_payload) {
                existing.summaryPayload = event.summary_payload as Record<
                  string,
                  unknown
                >;
              }
              if (event.result_link)
                existing.resultLink = event.result_link as string;
            } else {
              msg.toolCalls.push({
                name: event.name as string,
                status: event.success ? 'success' : 'error',
                durationMs: event.duration_ms as number | undefined,
                output: event.output as string | undefined,
                error: event.error as string | undefined,
                errorType: event.error_type as string | undefined,
                skillName: (event.skill_name as string) || undefined,
                skillType: (event.skill_type as string) || undefined,
                displayName: (event.display_name as string) || undefined,
                summary: (event.summary as string) || undefined,
                summaryPayload:
                  (event.summary_payload as Record<string, unknown>) ||
                  undefined,
                resultLink: (event.result_link as string) || undefined,
              });
            }
            if (event.success && options.onToolCall) {
              options.onToolCall(
                event.name as string,
                (event.output as string) ?? '',
              );
            }
            scrollToBottom();

            break;
          }
          case 'tool_start': {
            promoteToolRoundContent();
            if (!msg.toolCalls) msg.toolCalls = [];
            msg.toolCalls.push({
              id: event.id as string,
              name: event.name as string,
              status: 'running',
              arguments: event.arguments as Record<string, unknown> | undefined,
              skillName: (event.skill_name as string) || undefined,
              skillType: (event.skill_type as string) || undefined,
              startedAt: Date.now(),
            });
            scrollToBottom();

            break;
          }
          default: {
            if (event.event === 'authorization_required' && event.consent_key) {
              addConsent(event.consent_key as string);
            } else if (event.event === 'confirmation_request') {
              promoteToolRoundContent();
              msg.pendingConfirmation = {
                action: (event.action as string) || '',
                table: (event.table as string) || '',
                preview: event.preview as Record<string, unknown> | undefined,
              };
            } else if (event.event === 'tool_consent_request') {
              promoteToolRoundContent();
              if (interactionMode.value === 'trusted_auto') {
                msg.pendingConsent = {
                  toolName: (event.name as string) || '',
                  arguments: event.arguments as
                    | Record<string, unknown>
                    | undefined,
                  skillName: (event.skill_name as string) || undefined,
                  skillType: (event.skill_type as string) || undefined,
                  resolved: true,
                  autoApproved: true,
                };
                pendingInteractionUpdates.value.push({
                  kind: 'pending_consent',
                  auto_approved: true,
                  rejected: false,
                  tool_name: (event.name as string) || '',
                });
                _deferredAutoConfirm = true;
              } else {
                msg.pendingConsent = {
                  toolName: (event.name as string) || '',
                  arguments: event.arguments as
                    | Record<string, unknown>
                    | undefined,
                  skillName: (event.skill_name as string) || undefined,
                  skillType: (event.skill_type as string) || undefined,
                };
              }
              scrollToBottom();
            } else if (
              event.event === 'knowledge_base_feedback' &&
              (event.dropped_knowledge_base_ids ||
                event.effective_knowledge_base_ids)
            ) {
              const effective = Array.isArray(
                event.effective_knowledge_base_ids,
              )
                ? (event.effective_knowledge_base_ids as number[])
                : [];
              const dropped = Array.isArray(event.dropped_knowledge_base_ids)
                ? (event.dropped_knowledge_base_ids as number[])
                : [];
              selectedKBIds.value = effective;
              if (dropped.length > 0) {
                const droppedLabels = dropped.map((kid) => {
                  return (
                    agentKBBindings.value.find(
                      (item) => item.knowledge_base_id === kid,
                    )?.kb_name || `KB#${kid}`
                  );
                });
                message.warning(
                  $t('common.globalAiChat.knowledgeBaseSelectionAdjusted', {
                    dropped: droppedLabels.join('、'),
                  }),
                );
              }
            } else if (
              event.event === 'conversation' &&
              event.conversation_id
            ) {
              streamConversationId = event.conversation_id as number;
              activeConversationId.value = streamConversationId;
              activeConversationAgentId.value = targetAgentId;
              rememberConversationAnchor(streamConversationId, targetAgentId);
            } else if (event.event === 'action_buttons' && event.buttons) {
              msg.actionButtons = event.buttons as typeof msg.actionButtons;
              scrollToBottom();
            } else if (event.event === 'image_result' && event.url) {
              if (!msg.imageResults) msg.imageResults = [];
              msg.imageResults.push({
                url: event.url as string,
                isBase64: Boolean(event.is_base64),
                revisedPrompt: (event.revised_prompt as string) || undefined,
              });
              scrollToBottom();
            } else if (event.event === 'rag_sources' && event.sources) {
              msg.ragSources = event.sources as typeof msg.ragSources;
            } else if (event.event === 'message' && event.delta) {
              msg.content += event.delta as string;
              scrollToBottom();
            } else if (event.event === 'done') {
              didReceiveDoneEvent = true;
              msg.tokenUsage = (event.total_tokens as number) || 0;
              msg.durationMs = (event.duration_ms as number) || 0;
              msg.contextCompacted = Boolean(event.context_compacted);
              msg.memoryFlushTriggered = Boolean(event.memory_flush_triggered);
              msg.memoryRecalled = Boolean(event.memory_recalled);
              msg.pruneStats =
                (event.prune_stats as Record<string, unknown> | undefined) ??
                undefined;
              msg.ragSourceKinds = Array.isArray(event.rag_source_kinds)
                ? (event.rag_source_kinds as string[])
                : undefined;
              const turnRecord = normalizeTurnRecord(event.turn_record);
              const turnOutcome =
                normalizeOptionalString(event.turn_outcome) ??
                turnRecord?.turn_outcome;
              const terminationReason =
                normalizeOptionalString(event.termination_reason) ??
                turnRecord?.termination_reason;
              const completionReason =
                terminationReason ??
                normalizeOptionalString(event.completion_reason);
              const interruptedTurn =
                terminationReason === 'interrupted' ||
                completionReason === 'interrupted';
              const protocolPath =
                normalizeOptionalString(event.protocol_path) ??
                turnRecord?.protocol_path;
              const selectedToolNamesFromEvent = normalizeStringList(
                event.selected_tool_names,
              );
              const selectedToolNames =
                selectedToolNamesFromEvent.length > 0
                  ? selectedToolNamesFromEvent
                  : (turnRecord?.selected_tool_names ?? []);
              const selectedSkillNamesFromEvent = normalizeStringList(
                event.selected_skill_names,
              );
              const selectedSkillNames =
                selectedSkillNamesFromEvent.length > 0
                  ? selectedSkillNamesFromEvent
                  : (turnRecord?.selected_skill_names ?? []);
              const contextSourcesFromEvent = normalizeContextSources(
                event.context_sources,
              );
              const contextSources =
                contextSourcesFromEvent.length > 0
                  ? contextSourcesFromEvent
                  : (turnRecord?.context_sources ?? []);

              if (completionReason) {
                msg.completionReason = completionReason;
              }
              if (turnOutcome) {
                msg.turnOutcome = turnOutcome;
              }
              if (turnRecord) {
                msg.turnRecord = turnRecord;
              }
              if (terminationReason) {
                msg.terminationReason = terminationReason;
              }
              if (interruptedTurn) {
                msg.interrupted = true;
                msg.partial = true;
              }
              if (protocolPath) {
                msg.protocolPath = protocolPath;
              }
              if (selectedToolNames.length > 0) {
                msg.selectedToolNames = selectedToolNames;
              }
              if (selectedSkillNames.length > 0) {
                msg.selectedSkillNames = selectedSkillNames;
              }
              if (contextSources.length > 0) {
                msg.contextSources = contextSources;
              }
              if (turnOutcome === 'partial') {
                msg.partial = true;
              }
              if (
                isTurnFailure(
                  turnOutcome,
                  terminationReason ?? completionReason,
                )
              ) {
                msg.requestFailedRetry = true;
              }

              const nextContextDiagnostics: Record<string, unknown> = {
                context_compacted: Boolean(event.context_compacted),
                estimated_tokens: (event.total_tokens as number) || 0,
                interaction_mode_effective: interactionMode.value,
                last_interrupted: interruptedTurn,
                memory_flush_triggered: Boolean(event.memory_flush_triggered),
                memory_recalled: Boolean(event.memory_recalled),
                prune_stats:
                  (event.prune_stats as Record<string, unknown> | undefined) ??
                  null,
                rag_source_kinds: Array.isArray(event.rag_source_kinds)
                  ? (event.rag_source_kinds as string[])
                  : [],
              };
              if (turnOutcome) {
                nextContextDiagnostics.turn_outcome = turnOutcome;
              }
              if (terminationReason) {
                nextContextDiagnostics.termination_reason = terminationReason;
              }
              if (protocolPath) {
                nextContextDiagnostics.protocol_path = protocolPath;
              }
              if (selectedToolNames.length > 0) {
                nextContextDiagnostics.selected_tool_names = selectedToolNames;
              }
              if (selectedSkillNames.length > 0) {
                nextContextDiagnostics.selected_skill_names =
                  selectedSkillNames;
              }
              if (contextSources.length > 0) {
                nextContextDiagnostics.context_sources = contextSources;
              }
              conversationContextDiagnostics.value = nextContextDiagnostics;

              const nextLastRunSummary: Record<string, unknown> = {
                duration_ms: (event.duration_ms as number) || 0,
                interaction_mode_effective: interactionMode.value,
                total_tokens: (event.total_tokens as number) || 0,
              };
              if (completionReason) {
                nextLastRunSummary.completion_reason = completionReason;
              }
              if (interruptedTurn) {
                nextLastRunSummary.interrupted = true;
              }
              if (terminationReason) {
                nextLastRunSummary.termination_reason = terminationReason;
              }
              if (turnOutcome) {
                nextLastRunSummary.turn_outcome = turnOutcome;
              }
              if (protocolPath) {
                nextLastRunSummary.protocol_path = protocolPath;
              }
              if (selectedToolNames.length > 0) {
                nextLastRunSummary.selected_tool_names = selectedToolNames;
              }
              if (selectedSkillNames.length > 0) {
                nextLastRunSummary.selected_skill_names = selectedSkillNames;
              }
              if (contextSources.length > 0) {
                nextLastRunSummary.context_sources = contextSources;
              }
              lastRunSummary.value = nextLastRunSummary;
              if (event.conversation_id) {
                streamConversationId = event.conversation_id as number;
                activeConversationId.value = streamConversationId;
                activeConversationAgentId.value = targetAgentId;
                rememberConversationAnchor(streamConversationId, targetAgentId);
              }
              if (event.memory_updated) {
                lastMemoryUpdated.value = true;
                msg.memoryUpdated = true;
              }
              if (options.onStreamComplete) {
                options.onStreamComplete();
              }
              finalizeMessage();
              streaming.value = false;
              sending.value = false;
              loadConversations();
              if (doneAbortTimer) {
                clearTimeout(doneAbortTimer);
              }
              doneAbortTimer = setTimeout(() => {
                streamAbortController?.abort();
              }, 2000);
            } else if (event.error) {
              if (event.conversation_id) {
                streamConversationId = event.conversation_id as number;
                activeConversationId.value = streamConversationId;
                activeConversationAgentId.value = targetAgentId;
                rememberConversationAnchor(streamConversationId, targetAgentId);
              }
              shouldSyncInterruptedConversation =
                shouldSyncInterruptedConversation ||
                hasReceivedStreamPayload ||
                streamConversationId !== null;
              applyAssistantError(msg, normalizeSseEventError(event, $t));
            }
          }
        }
      } catch (error: unknown) {
        console.warn('[AI Chat] SSE parse error:', error);
      }
    }

    let panelInteractionUpdates: Array<{
      action?: string;
      auto_approved?: boolean;
      kind: 'action_buttons' | 'pending_confirmation' | 'pending_consent';
      rejected?: boolean;
      table?: string;
      tool_name?: string;
      value?: string;
    }> = [];
    let localInteractionUpdates: Array<{
      action?: string;
      auto_approved?: boolean;
      kind: 'action_buttons' | 'pending_confirmation' | 'pending_consent';
      rejected?: boolean;
      table?: string;
      tool_name?: string;
      value?: string;
    }> = [];

    try {
      const prefix = unref(options.apiPrefix) as string;
      // Ensure page operation channel is connected before sending page-aware chat requests /
      // 在发送页面感知请求前确保 page operation 通道已连接并完成入房，避免 pageop 在后端等待 60s 后超时
      const pageChannelReady = await ensurePageOperationChannelReady(
        prefix,
        pageContext,
      );
      if (!pageChannelReady && hasPageOperations(pageContext)) {
        const reconnectError = {
          message: $t('shared.common.connectionLost'),
          raw: { name: 'PageOperationChannelUnavailable' },
        } as AppErrorInfo;
        message.warning(reconnectError.message);
        applyAssistantError(chatMessages.value[assistantIdx], reconnectError);
        finalizeMessage();
        return;
      }
      const singleText = texts.length === 1 ? (texts[0] ?? '') : null;
      panelInteractionUpdates = aiPanelStore.consumeInteractionUpdates();
      localInteractionUpdates = [...pendingInteractionUpdates.value];
      const mergedInteractionUpdates = [
        ...panelInteractionUpdates,
        ...localInteractionUpdates,
      ];
      const requestBody: AgentChatRequestBody = {
        ...(singleText === null
          ? { messages: texts }
          : { message: singleText }),
        conversation_id: streamConversationId,
        ...(mergedInteractionUpdates.length > 0
          ? { interaction_updates: mergedInteractionUpdates }
          : {}),
        ...(selectedKBIds.value.length > 0
          ? { knowledge_base_ids: selectedKBIds.value }
          : {}),
        ...(Object.keys(allAgentsVariables.value[targetAgentId] ?? {}).length >
        0
          ? { variables: allAgentsVariables.value[targetAgentId] }
          : {}),
        consented_actions: getConsentedActions(),
        ...(apiAttachments ? { attachments: apiAttachments } : {}),
        ...(imageParams.value.size !== '1024x1024' ||
        imageParams.value.quality !== 'standard' ||
        imageParams.value.style !== 'vivid' ||
        imageParams.value.n !== 1
          ? { image_params: imageParams.value }
          : {}),
        ...(pageContext ? { page_context: pageContext } : {}),
        ...(routeSource ? { route_source: routeSource } : {}),
        interaction_mode: interactionMode.value,
        ...(options.pageSessionIdGetter
          ? { page_session_id: options.pageSessionIdGetter() || null }
          : {}),
      };
      pendingInteractionUpdates.value = [];
      await sendChatStreamApi(prefix, targetAgentId, requestBody, {
        abortController: streamAbortController,
        async onMessage(rawChunk: string) {
          await parseSSEEvents(rawChunk, sseBuffer, handleSsePayload);
        },
        async onEnd() {
          didSseEnd = true;
          if (doneAbortTimer) {
            clearTimeout(doneAbortTimer);
            doneAbortTimer = null;
          }
          await parseSSEEvents('\n', sseBuffer, handleSsePayload);
          loadConversations();
        },
        onError(error: AppErrorInfo | Error) {
          const appError = normalizeSseTransportError(error, $t);
          if (
            (appError.raw as undefined | { name?: string })?.name ===
            'AbortError'
          ) {
            return;
          }
          shouldSyncInterruptedConversation =
            shouldSyncInterruptedConversation || hasReceivedStreamPayload;
          const msg = chatMessages.value[assistantIdx];
          applyAssistantError(msg, appError);
          finalizeMessage();
        },
      });
    } catch (error: unknown) {
      aiPanelStore.restoreInteractionUpdates(panelInteractionUpdates);
      pendingInteractionUpdates.value = [
        ...localInteractionUpdates,
        ...pendingInteractionUpdates.value,
      ];
      // sendChatStreamApi throws on non-2xx; sse.ts does not call onError for HTTP errors / 非 2xx 抛错，sse 层未必走 onError
      const normalizedError = normalizeSseTransportError(error, $t);
      shouldSyncInterruptedConversation =
        (normalizedError.raw as undefined | { name?: string })?.name ===
        'AbortError'
          ? shouldSyncInterruptedConversation ||
            streamLifecycle.abortReason === 'user'
          : shouldSyncInterruptedConversation || hasReceivedStreamPayload;
      const msg = chatMessages.value[assistantIdx];
      if (
        (normalizedError.raw as undefined | { name?: string })?.name !==
        'AbortError'
      ) {
        applyAssistantError(msg, normalizedError);
        finalizeMessage();
      }
    } finally {
      if (doneAbortTimer) {
        clearTimeout(doneAbortTimer);
        doneAbortTimer = null;
      }
      sending.value = false;
      streaming.value = false;
      if (streamAbortController === requestAbortController) {
        streamAbortController = null;
      }
      if (activeStreamLifecycle === streamLifecycle) {
        activeStreamLifecycle = null;
      }
      userScrolledUp.value = false;
      finalizeMessage();

      const interruptedConversationId = streamConversationId;
      const shouldSyncConversationHistory =
        !didReceiveDoneEvent &&
        interruptedConversationId !== null &&
        (streamLifecycle.abortReason === 'user' ||
          shouldSyncInterruptedConversation ||
          didSseEnd);
      if (shouldSyncConversationHistory) {
        await syncConversationAfterInterrupt(
          interruptedConversationId,
          interruptedHistoryBaseline,
        );
      }

      if (_deferredAutoConfirm && pendingInteractionUpdates.value.length > 0) {
        _deferredAutoConfirm = false;
        await nextTick();
        sendMessage({ silent: true });
      }
    }
  }

  function confirmAction(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConfirmation || msg.pendingConfirmation.resolved) return;
    msg.pendingConfirmation.resolved = true;
    pendingInteractionUpdates.value.push({
      action: msg.pendingConfirmation.action,
      kind: 'pending_confirmation',
      rejected: false,
      table: msg.pendingConfirmation.table,
    });
    sendMessage({ silent: true });
  }

  function rejectAction(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConfirmation || msg.pendingConfirmation.resolved) return;
    msg.pendingConfirmation.resolved = true;
    pendingInteractionUpdates.value.push({
      action: msg.pendingConfirmation.action,
      kind: 'pending_confirmation',
      rejected: true,
      table: msg.pendingConfirmation.table,
    });
    sendMessage({ silent: true });
  }

  function confirmConsent(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConsent || msg.pendingConsent.resolved) return;
    msg.pendingConsent.resolved = true;
    pendingInteractionUpdates.value.push({
      kind: 'pending_consent',
      rejected: false,
      tool_name: msg.pendingConsent.toolName,
    });
    sendMessage({ silent: true });
  }

  function rejectConsent(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConsent || msg.pendingConsent.resolved) return;
    msg.pendingConsent.resolved = true;
    msg.pendingConsent.rejected = true;
    pendingInteractionUpdates.value.push({
      kind: 'pending_consent',
      rejected: true,
      tool_name: msg.pendingConsent.toolName,
    });
    sendMessage({ silent: true });
  }

  function clickActionButton(msgIndex: number, value: string) {
    const msg = chatMessages.value[msgIndex];
    if (!msg || msg.actionButtonsUsed) return;
    msg.actionButtonsUsed = true;
    pendingInteractionUpdates.value.push({
      kind: 'action_buttons',
      value,
    });
    inputMessage.value = value;
    sendMessage();
  }

  function editAndResend(msgIndex: number) {
    if (sending.value || streaming.value) return;
    const msg = chatMessages.value[msgIndex];
    if (!msg || msg.role !== 'user') return;

    // Fill input with the user message content / 将用户原文填回输入框
    inputMessage.value = msg.content;

    // Remove this message and all subsequent messages / 删除本条及之后消息
    chatMessages.value.splice(msgIndex);

    // Fork to new conversation: edited message will create new conv, not append to old / 分叉新会话
    activeConversationId.value = null;
    activeConversationAgentId.value = null;
    clearConversationAnchor();
    messagesRequestSeq += 1;
  }

  function getExportAttachmentTypeLabel(type: ChatAttachment['type']): string {
    switch (type) {
      case 'file': {
        return $t('common.globalAiChat.file');
      }
      case 'image': {
        return $t('common.image');
      }
      default: {
        return type;
      }
    }
  }

  function buildExportAttachmentLines(
    attachments?: ChatAttachment[],
    format: 'markdown' | 'text' = 'markdown',
  ): string[] {
    if (!attachments?.length) return [];

    const lines = [
      format === 'markdown'
        ? `**${$t('common.globalAiChat.attachments')}:**`
        : `${$t('common.globalAiChat.attachments')}:`,
    ];

    for (const attachment of attachments) {
      const typeLabel = getExportAttachmentTypeLabel(attachment.type);
      const attachmentLabel = attachment.name || attachment.url || '-';
      lines.push(`- ${typeLabel}: ${attachmentLabel}`);
      if (attachment.attachment_id) {
        lines.push(
          `  ${$t('common.globalAiChat.attachmentId')}: ${attachment.attachment_id}`,
        );
      }
      if (attachment.url) {
        lines.push(`  URL: ${attachment.url}`);
      }
    }

    lines.push('');
    return lines;
  }

  function exportAsMarkdown() {
    if (chatMessages.value.length === 0) return;
    const agentName =
      selectedAgent.value?.name || $t('common.globalAiChat.assistant');
    const userLabel = $t('common.globalAiChat.user');
    const lines: string[] = [
      `# ${agentName} - ${$t('common.globalAiChat.history')}`,
      '',
    ];
    for (const msg of chatMessages.value) {
      const role =
        msg.role === 'user' ? `**${userLabel}**` : `**${agentName}**`;
      lines.push(`### ${role}`, '');
      if (msg.content) lines.push(msg.content);
      lines.push(...buildExportAttachmentLines(msg.attachments, 'markdown'));
      if (msg.toolCalls?.length) {
        lines.push('');
        for (const tc of msg.toolCalls) {
          const duration = tc.durationMs
            ? ` (${(tc.durationMs / 1000).toFixed(1)}s)`
            : '';
          const skill = tc.skillName ? `${tc.skillName} › ` : '';
          lines.push(
            `> 🔧 ${skill}${tc.displayName || tc.name} — ${tc.status}${duration}`,
          );
          if (tc.arguments && Object.keys(tc.arguments).length > 0) {
            lines.push(`> **Args:** \`${JSON.stringify(tc.arguments)}\``);
          }
          if (tc.output) {
            lines.push(
              `> **Output:** ${tc.output.slice(0, 500)}${tc.output.length > 500 ? '...' : ''}`,
            );
          }
          if (tc.error) {
            lines.push(`> **Error:** ${tc.error}`);
          }
        }
      }
      lines.push('');
    }
    const blob = new Blob([lines.join('\n')], {
      type: 'text/markdown;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${activeConversationId.value || 'new'}-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportAsPlainText() {
    if (chatMessages.value.length === 0) return;
    const agentName =
      selectedAgent.value?.name || $t('common.globalAiChat.assistant');
    const lines: string[] = [];
    for (const msg of chatMessages.value) {
      const label =
        msg.role === 'user' ? $t('common.globalAiChat.user') : agentName;
      lines.push(`${label}:`);
      if (msg.content) lines.push(msg.content);
      lines.push(...buildExportAttachmentLines(msg.attachments, 'text'), '');
    }
    const blob = new Blob([lines.join('\n')], {
      type: 'text/plain;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${activeConversationId.value || 'new'}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function regenerateMessage(msgIndex: number) {
    if (sending.value || streaming.value) return;
    const msg = chatMessages.value[msgIndex];
    if (!msg || msg.role !== 'assistant') return;

    // Find the preceding user message / 向前查找最近一条 user
    let userMsgIndex = -1;
    for (let i = msgIndex - 1; i >= 0; i--) {
      if (chatMessages.value[i]?.role === 'user') {
        userMsgIndex = i;
        break;
      }
    }
    if (userMsgIndex < 0) return;

    const userMessage = chatMessages.value[userMsgIndex];
    if (!userMessage || userMessage.role !== 'user') return;

    const userContent = userMessage.content;
    const userAttachments = userMessage.attachments;

    // Remove the assistant message (and any messages after it) / 移除该 assistant 及之后消息
    chatMessages.value.splice(msgIndex);

    // Fork to new conversation: regenerate creates new branch, not overwrite in same conv / 分叉新会话
    activeConversationId.value = null;
    activeConversationAgentId.value = null;
    clearConversationAnchor();
    messagesRequestSeq += 1;

    // Re-send the user message / 用原 user 内容再次发送
    inputMessage.value = userContent;
    clearPendingAttachments();
    if (userAttachments?.length) {
      pendingAttachments.value = [...userAttachments];
    }
    sendMessage({ silent: true });
  }

  function stopGeneration() {
    abortActiveStream(true);
  }

  /**
   * Retry after SSE error: remove the failed assistant message, restore last user message to input, and send again / SSE 错误后重试：移除失败助手消息并重新发送
   * (silent = do not push user message again).
   */
  function retryLastMessage() {
    abortActiveStream();
    const messages = chatMessages.value;
    if (messages.length < 2) return;
    const last = messages.at(-1);
    if (last?.role !== 'assistant' || !last.requestFailedRetry) return;
    const prev = messages.at(-2);
    if (prev?.role !== 'user') return;
    chatMessages.value = messages.slice(0, -1);
    inputMessage.value = prev.content;
    if (prev.attachments?.length) {
      pendingAttachments.value = [...prev.attachments];
    }
    sendMessage({ silent: true });
  }

  function cleanup() {
    abortActiveStream();
  }

  // ============ Helpers / 对外 API ============

  return {
    // Agents / 智能体
    agents,
    agentsLoading,
    selectedAgentId,
    selectedAgent,
    loadAgents,
    selectAgent,

    // Conversations / 会话
    conversations,
    conversationsLoading,
    activeConversationId,
    conversationContextDiagnostics,
    loadConversations,
    startNewConversation,
    deleteConversation,
    updateConversationTitle,
    clearConversationMemory,
    clearingMemory,
    fetchConversationMemory,
    memoryState,
    memoryLoading,
    lastMemoryUpdated,
    loadConversationMessages,

    // Chat / 对话与发送
    chatMessages,
    inputMessage,
    mentionOpen,
    mentionCandidates,
    mentionActiveIndex,
    selectedKBIds,
    agentKBBindings,
    loadAgentKBBindings,
    allAgentsVariables,
    ensureAgentVarsLoaded,
    agentsWithVarsInConversation,
    applyVariables,
    resetVariables,
    clearConversationVarsCache,
    sending,
    streaming,
    messagesContainer,
    sendMessage,
    stopGeneration,
    scrollToBottom,
    scrollToTop,
    handleMessagesScroll,
    showScrollToBottom: userScrolledUp,
    showScrollToTop: userNotAtTop,
    copyMessage,
    handleInputKeyDown,
    selectMentionKnowledgeBase,
    removeSelectedKnowledgeBase,
    confirmAction,
    rejectAction,
    confirmConsent,
    rejectConsent,
    interactionMode,
    clickActionButton,
    regenerateMessage,
    editAndResend,
    retryLastMessage,
    cleanup,

    // Model capabilities / 模型能力
    supportsVision,
    imageParams,
    exportAsMarkdown,
    exportAsPlainText,
    lastRunSummary,
    totalTokensUsed,

    // Attachments / 附件
    pendingAttachments,
    uploading,
    fileInput,
    chatAcceptAttribute,
    uploadFile,
    handleFileSelect,
    handlePaste,
    handleDrop,
    handleDragOver,
    removePendingAttachment,
    clearPendingAttachments,
  };
}
