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
  AgentItem,
  ChatAttachment,
  ChatMessage,
  ConversationItem,
  ToolCallEvent,
} from './types';

import { computed, nextTick, ref, unref, watch } from 'vue';

import { message } from 'ant-design-vue';

import type {
  AgentChatRequestBody,
  ChatKBBindingInfo,
  MemoryState,
  PageContext,
} from '#/api/shared/ai-chat';

import {
  clearChatConversationMemoryApi,
  deleteChatConversationApi,
  updateChatConversationTitleApi,
  getChatAgentKBBindingsApi,
  getChatAgentsApi,
  getChatConversationMemoryApi,
  getChatConversationMessagesApi,
  getGlobalConversationsApi,
  sendChatStreamApi,
  uploadChatFileApi,
} from '#/api/shared/ai-chat';
import { useFileUpload } from '#/composables/use-file-upload';
import { CHAT_ACCEPT_ATTRIBUTE } from '#/constants/upload';
import { $t } from '#/locales';
import { addConsent, getConsentedActions } from '#/utils/ai-consent';

export interface UseAIChatOptions {
  /** API prefix: '/admin' or '/tenant' / API 前缀 */
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

  const trustSession = ref(false);

  // ============ Agents ============

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
      agents.value = res.items;
      if (res.items.length > 0 && !selectedAgentId.value) {
        const initId = overrideAgentId ?? unref(options.initialAgentId);
        selectedAgentId.value =
          initId && res.items.some((a) => a.id === initId)
            ? initId
            : res.items[0]!.id;
      }
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      agentsLoading.value = false;
    }
  }

  function selectAgent(agentId: number) {
    if (selectedAgentId.value === agentId) return;
    selectedAgentId.value = agentId;
    conversationsRequestSeq += 1;
    messagesRequestSeq += 1;
    activeConversationId.value = null;
    chatMessages.value = [];
    clearPendingAttachments();
    // Clear cached variables when switching agents
    // (they'll be re-initialized via watch + openVarsModal in the page component)
  }

  // ============ Conversations ============

  const conversations = ref<ConversationItem[]>([]);
  const conversationsLoading = ref(false);
  const activeConversationId = ref<null | number>(null);
  const clearingMemory = ref(false);
  const memoryState = ref<MemoryState | null>(null);
  const memoryLoading = ref(false);
  const lastMemoryUpdated = ref(false);

  /** Request sequence guard: prevents stale async responses from overriding latest state / 请求序号防护：避免旧异步响应覆盖最新状态 */
  let conversationsRequestSeq = 0;
  let messagesRequestSeq = 0;

  async function loadConversations() {
    const reqSeq = ++conversationsRequestSeq;
    conversationsLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix) as string;
      const res = await getGlobalConversationsApi<ConversationItem>(prefix);
      if (reqSeq !== conversationsRequestSeq) {
        return;
      }
      conversations.value = res.items;

      // Auto-load initial conversation (only once)
      const initConvId = unref(options.initialConversationId);
      if (
        initConvId &&
        !_initialConvRestored &&
        res.items.some((c) => c.id === initConvId)
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

  /**
   * Reset chat state / 重置对话状态
   * @param keepVars - When true (panel open/reopen), session vars are preserved.
   *                   When false (explicit "+" new chat), session vars are cleared.
   */
  function startNewConversation(keepVars = false) {
    messagesRequestSeq += 1;
    if (debounceTimerId) {
      clearTimeout(debounceTimerId);
      debounceTimerId = null;
    }
    pendingMessages.value = [];
    activeConversationId.value = null;
    chatMessages.value = [];
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
        messagesRequestSeq += 1;
        activeConversationId.value = null;
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
      // handled by interceptor
    }
  }

  async function loadConversationMessages(convId: number) {
    const reqSeq = ++messagesRequestSeq;
    if (debounceTimerId) {
      clearTimeout(debounceTimerId);
      debounceTimerId = null;
    }
    pendingMessages.value = [];
    activeConversationId.value = convId;
    const currentConversation = conversations.value.find((c) => c.id === convId);
    if (currentConversation?.agent_id) {
      selectedAgentId.value = currentConversation.agent_id;
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

      if (res.agent_id) {
        selectedAgentId.value = res.agent_id;
      }

      // Pre-load variables for the agent from localStorage
      const agentId = selectedAgentId.value;
      if (agentId) {
        ensureAgentVarsLoaded(agentId);
      }

      const merged = mergeMessagesForDisplay(res.message_list ?? []);
      chatMessages.value = merged;
      // Restore lastMemoryUpdated from historical messages
      lastMemoryUpdated.value = merged.some((m) => m.memoryUpdated);
      // Restore trust-session preference for this conversation (persisted per convId)
      try {
        const stored = sessionStorage.getItem(`ai_trust_session_${convId}`);
        trustSession.value = stored === '1';
      } catch {
        trustSession.value = false;
      }
      scrollToBottom(true);
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  // Persist trustSession when it changes (per active conversation)
  watch(
    [trustSession, activeConversationId],
    ([trust, convId]) => {
      if (convId != null && typeof convId === 'number') {
        try {
          sessionStorage.setItem(
            `ai_trust_session_${convId}`,
            trust ? '1' : '0',
          );
        } catch {
          // ignore
        }
      }
    },
    { immediate: false },
  );

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
    rawMessages: Array<{
      agent_avatar?: null | string;
      agent_id?: null | number;
      agent_name?: null | string;
      content: null | string;
      created_at?: null | string;
      metadata?: null | { attachments?: ChatAttachment[]; memory_updated?: boolean };
      role: string;
      tool_call_id?: null | string;
      tool_calls?: Array<{
        function?: { arguments?: string; name?: string };
        id?: string;
      }> | null;
      tool_name?: null | string;
    }>,
  ): ChatMessage[] {
    // Filter out system messages
    const filtered = rawMessages.filter((m) => m.role !== 'system');
    if (filtered.length === 0) return [];

    const result: ChatMessage[] = [];

    // Collect tool responses keyed by tool_call_id for quick lookup
    const toolResponseMap = new Map<
      string,
      { content: string; error?: string; name?: string; success: boolean }
    >();
    for (const m of filtered) {
      if (m.role === 'tool' && m.tool_call_id) {
        const meta = (m.metadata ?? {}) as Record<string, unknown>;
        const toolSuccess = meta.tool_success !== false; // default true for legacy data
        toolResponseMap.set(m.tool_call_id, {
          content: m.content ?? '',
          success: toolSuccess,
          error: (meta.tool_error as string) || undefined,
          name: m.tool_name ?? undefined,
        });
      }
    }

    // Group consecutive non-user messages into assistant turns
    let i = 0;
    while (i < filtered.length) {
      const msg = filtered[i]!;

      if (msg.role === 'user') {
        result.push({
          role: 'user',
          content: msg.content ?? '',
          attachments: msg.metadata?.attachments,
          ...(msg.created_at ? { created_at: msg.created_at } : {}),
        });
        i++;
        continue;
      }

      // Collect all consecutive non-user messages as one assistant turn
      const toolCalls: ToolCallEvent[] = [];
      const contentParts: string[] = [];
      let hasMemoryUpdated = false;
      let turnAgentId: null | number = null;
      let turnAgentName: null | string = null;
      let turnAgentAvatar: null | string = null;
      let turnAgentDescription: null | string = null;
      let turnModelName: null | string = null;
      let turnCreatedAt: null | string = null;
      const startIdx = i;

      while (i < filtered.length && filtered[i]!.role !== 'user') {
        const cur = filtered[i]!;

          if (cur.role === 'assistant') {
          if (cur.created_at) turnCreatedAt = cur.created_at;
          // Capture agent info from the first assistant message in this turn
          if (turnAgentId === null && cur.agent_id) {
            turnAgentId = cur.agent_id;
            turnAgentName = cur.agent_name ?? null;
            turnAgentAvatar = cur.agent_avatar ?? null;
            // Enrich from agents list
            const agentInfo = agents.value.find((a) => a.id === cur.agent_id);
            if (agentInfo) {
              turnAgentDescription = agentInfo.description ?? null;
              turnModelName = agentInfo.model_name ?? null;
              if (!turnAgentAvatar && agentInfo.avatar) {
                turnAgentAvatar = agentInfo.avatar;
              }
            }
          }
          // Extract tool calls from this assistant message
          if (cur.tool_calls && cur.tool_calls.length > 0) {
            for (const tc of cur.tool_calls) {
              const tcId = tc.id ?? '';
              const funcName = tc.function?.name ?? 'unknown';
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

              // Match with tool response (use metadata.tool_success for status)
              const response = tcId ? toolResponseMap.get(tcId) : undefined;

              toolCalls.push({
                name: funcName,
                status: response
                  ? response.success
                    ? 'success'
                    : 'error'
                  : 'error',
                arguments: parsedArgs,
                output: response?.success ? response.content : undefined,
                error:
                  response && !response.success
                    ? response.error || response.content
                    : undefined,
              });
            }
          }

          // Check memory_updated flag in metadata
          if (cur.metadata?.memory_updated) {
            hasMemoryUpdated = true;
          }

          // Accumulate content from all assistant messages in this turn
          // (matches streaming behavior where all deltas are concatenated)
          if (cur.content && cur.content.trim()) {
            contentParts.push(cur.content);
          }
        }
        // tool messages are already handled via toolResponseMap
        i++;
      }

      // Only add if we actually processed something
      if (i > startIdx) {
        const assistantMsg: ChatMessage = {
          role: 'assistant',
          content: contentParts.join('\n\n'),
          toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
          agent_id: turnAgentId,
          agent_name: turnAgentName,
          agent_avatar: turnAgentAvatar,
          agent_description: turnAgentDescription,
          model_name: turnModelName,
        };
        if (turnCreatedAt) assistantMsg.created_at = turnCreatedAt;
        if (hasMemoryUpdated) {
          assistantMsg.memoryUpdated = true;
        }
        result.push(assistantMsg);
      }
    }

    return result;
  }

  // ============ Chat Messages ============

  /** Guard: only restore initialConversationId once / 仅恢复一次 initialConversationId */
  let _initialConvRestored = false;

  const chatMessages = ref<ChatMessage[]>([]);
  const inputMessage = ref('');
  /**
   * Auxiliary feature: user-manually selected additional knowledge base IDs (@ mentions).
   * Primary KB bindings have been migrated to Agent-level junction tables; this field serves as a supplement.
   * 辅助功能：用户手动选择的额外知识库 ID（@ 提及）。
   * 主要 KB 绑定已迁移至 Agent 级别中间表，此字段仅作为补充。
   */
  const selectedKBIds = ref<number[]>([]);
  const agentKBBindings = ref<ChatKBBindingInfo[]>([]);

  // ============ Input Variables ============

  /** Per-agent variables: agentId → { varName: value } / 各智能体变量 */
  const allAgentsVariables = ref<Record<number, Record<string, string>>>({});

  function _varsLocalKey(agentId: number): string {
    return `ai-vars:${agentId}`;
  }

  function _saveVarsToStorage(agentId: number, vars: Record<string, string>) {
    try {
      localStorage.setItem(_varsLocalKey(agentId), JSON.stringify(vars));
    } catch { /* quota exceeded or private mode / 配额超限或隐私模式 */ }
  }

  function _loadVarsFromStorage(agentId: number): Record<string, string> | null {
    try {
      const raw = localStorage.getItem(_varsLocalKey(agentId));
      return raw ? (JSON.parse(raw) as Record<string, string>) : null;
    } catch { return null; }
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
   * @param persist - if true, also writes to localStorage (long-term, auto-injected every session)
   *                  if false, only in-memory for this browser session
   */
  function applyVariables(agentId: number, values: Record<string, string>, persist = false) {
    allAgentsVariables.value[agentId] = { ...values };
    if (persist) {
      _saveVarsToStorage(agentId, { ...values });
    }
  }

  function resetVariables() {
    allAgentsVariables.value = {};
  }

  function clearConversationVarsCache() {
    // no-op: variables are now persisted per-agent, not per-conversation
  }

  /** Agents that have appeared in the conversation AND have input_variables / 对话中出现且含 input_variables 的智能体 */
  const agentsWithVarsInConversation = computed(() => {
    const agentIdsInChat = new Set<number>(
      chatMessages.value
        .filter((m) => m.role === 'assistant' && m.agent_id)
        .map((m) => m.agent_id!),
    );
    return agents.value.filter(
      (a) =>
        agentIdsInChat.has(a.id) &&
        a.input_variables &&
        a.input_variables.length > 0,
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
  const sending = ref(false);
  const streaming = ref(false);

  /** 发送前 800ms 防抖：多条消息合并为一次请求 */
  const SEND_DEBOUNCE_MS = 800;
  const pendingMessages = ref<{ text: string }[]>([]);
  let debounceTimerId: ReturnType<typeof setTimeout> | null = null;
  const messagesContainer = ref<HTMLElement | null>(null);

  let streamAbortController: AbortController | null = null;

  /** Deferred auto-confirm flag: set when trustSession auto-approves during active stream / 延迟自动确认标志 */
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
      // fallback silently
    }
  }

  function handleInputKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage();
    }
  }

  // ============ Model Capabilities ============

  const supportsVision = computed(
    () => selectedAgent.value?.model_capabilities?.supports_vision ?? false,
  );

  const supportsAudio = computed(
    () => selectedAgent.value?.model_capabilities?.supports_audio ?? false,
  );

  const supportsVideo = computed(
    () => selectedAgent.value?.model_capabilities?.supports_video ?? false,
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

  // ============ File Uploads ============

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
      img.onerror = () => {
        URL.revokeObjectURL(img.src);
        resolve(file);
      };
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
      const isAudio = file.type.startsWith('audio/');
      const isVideo = file.type.startsWith('video/');
      const attachmentType = isImage
        ? 'image'
        : isAudio
          ? 'audio'
          : isVideo
            ? 'video'
            : 'file';
      return {
        type: attachmentType,
        url: data.url,
        name: file.name,
        mime_type: fileToUpload.type,
        preview: isImage ? URL.createObjectURL(fileToUpload) : undefined,
      };
    } catch (error: unknown) {
      const errorMsg =
        error instanceof Error
          ? error.message
          : $t('common.uploadValidation.uploadFailed');
      message.error(errorMsg);
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

  // ============ SSE Streaming ============

  function parseSSEEvents(
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
        handler(trimmed.slice(6));
      }
    }
  }

  async function sendMessage(opts?: {
    agentId?: number;
    pageContext?: null | PageContext;
    silent?: boolean;
  }) {
    const silent = opts?.silent ?? false;
    const targetAgentId = opts?.agentId ?? selectedAgentId.value;
    const pageContext =
      opts?.pageContext === undefined
        ? (options.pageContextResolver?.() ?? null)
        : opts.pageContext;
    const hasText = inputMessage.value.trim().length > 0;
    const hasAttachments = pendingAttachments.value.length > 0;
    if (
      (!hasText && !hasAttachments) ||
      !targetAgentId ||
      sending.value
    )
      return;

    // Block sending if required input variables are not filled
    const agent = agents.value.find((a) => a.id === targetAgentId);
    const requiredVars = agent?.input_variables?.filter((v) => v.required) ?? [];
    if (requiredVars.length > 0) {
      ensureAgentVarsLoaded(targetAgentId);
      const agentVars = allAgentsVariables.value[targetAgentId] ?? {};
      const missingVars = requiredVars.filter((v) => !agentVars[v.name]?.trim());
      if (missingVars.length > 0) {
        message.warning(
          $t('user.aiChat.varsModal.fillRequired', {
            fields: missingVars.map((v) => v.label || v.name).join('、'),
          }),
        );
        options.onVariablesMissing?.();
        return;
      }
    }

    const userMsg = inputMessage.value.trim();
    const msgAttachments = [...pendingAttachments.value];

    const useDebounce =
      !silent &&
      !hasAttachments &&
      msgAttachments.length === 0 &&
      userMsg.length > 0;

    if (useDebounce) {
      if (!silent) {
        chatMessages.value.push({
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
          targetAgentId: targetAgentId!,
          pageContext,
        });
      }, SEND_DEBOUNCE_MS);
      return;
    }

    if (!silent) {
      chatMessages.value.push({
        role: 'user',
        content: userMsg,
        attachments: msgAttachments.length > 0 ? msgAttachments : undefined,
        created_at: new Date().toISOString(),
      });
    }
    const targetAgent = agents.value.find((a) => a.id === targetAgentId);
    chatMessages.value.push({
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

    inputMessage.value = '';
    clearPendingAttachments();
    await nextTick();

    await doStreamRequest({
      texts: [userMsg],
      apiAttachments:
        msgAttachments.length > 0
          ? msgAttachments.map(({ type, url, name, mime_type }) => ({
              type,
              url,
              name,
              mime_type,
            }))
          : undefined,
      targetAgentId: targetAgentId!,
      pageContext,
    });
  }

  async function flushPendingAndSend(opts: {
    targetAgentId: number;
    pageContext: null | PageContext;
  }) {
    const msgs = [...pendingMessages.value];
    pendingMessages.value = [];
    if (msgs.length === 0) return;
    if (sending.value) return;

    const { targetAgentId, pageContext } = opts;
    const targetAgent = agents.value.find((a) => a.id === targetAgentId);
    chatMessages.value.push({
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
    texts: string[];
    apiAttachments?:
      | { type: string; url: string; name?: string; mime_type?: string }[]
      | undefined;
    targetAgentId: number;
    pageContext: null | PageContext;
  }) {
    const { texts, apiAttachments, targetAgentId, pageContext } = params;
    sending.value = true;
    streaming.value = true;
    const sseBuffer = { value: '' };
    streamAbortController = new AbortController();
    const assistantIdx = chatMessages.value.length - 1;

    function finalizeMessage() {
      const msg = chatMessages.value[assistantIdx];
      if (msg) {
        msg.streaming = false;
        if (msg.toolCalls) {
          const orphaned = msg.toolCalls.filter((tc) => tc.status === 'running');
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

    try {
      const prefix = unref(options.apiPrefix) as string;
      const requestBody: AgentChatRequestBody = {
        ...(texts.length === 1
          ? { message: texts[0]! || ' ' }
          : { messages: texts }),
        conversation_id: activeConversationId.value,
        ...(selectedKBIds.value.length > 0
          ? { knowledge_base_ids: selectedKBIds.value }
          : {}),
        ...((Object.keys(allAgentsVariables.value[targetAgentId] ?? {}).length > 0)
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
        ...(options.pageSessionIdGetter
          ? { page_session_id: options.pageSessionIdGetter() || null }
          : {}),
      };
      await sendChatStreamApi(
        prefix,
        targetAgentId!,
        requestBody,
        {
          abortController: streamAbortController,
          onMessage(rawChunk: string) {
            parseSSEEvents(rawChunk, sseBuffer, (data) => {
              if (data === '[DONE]') return;
              try {
                const event = JSON.parse(data);
                const msg = chatMessages.value[assistantIdx];
                if (!msg) return;

                switch (event.event) {
                  case 'optimizing_tools': {
                    msg.optimizingTools = {
                      total: event.total || 0,
                      selected: event.selected || 0,
                    };
                    scrollToBottom();

                    break;
                  }
                  case 'thinking': {
                    // frontend already shows loading via streaming + !content

                    break;
                  }
                  case 'tool_call': {
                    if (!msg.toolCalls) msg.toolCalls = [];
                    // Find matching running tool by name first / 优先按 name 匹配
                    let existing = msg.toolCalls.findLast(
                      (tc) => tc.name === event.name && tc.status === 'running',
                    );
                    // Fallback: when name mismatch (e.g. sandbox redirect pageop_* -> invoke_page_operation)
                    // 兜底：name 不一致时（如 sandbox 重定向）匹配最后一个 running
                    if (!existing) {
                      existing = msg.toolCalls.findLast((tc) => tc.status === 'running');
                    }
                    if (existing) {
                      existing.status = event.success ? 'success' : 'error';
                      existing.durationMs = event.duration_ms;
                      existing.output = event.output;
                      existing.error = event.error;
                      existing.errorType = event.error_type;
                      if (event.skill_name)
                        existing.skillName = event.skill_name;
                      if (event.skill_type)
                        existing.skillType = event.skill_type;
                      if (event.display_name)
                        existing.displayName = event.display_name;
                      if (event.summary) existing.summary = event.summary;
                      if (event.result_link)
                        existing.resultLink = event.result_link;
                    } else {
                      msg.toolCalls.push({
                        name: event.name,
                        status: event.success ? 'success' : 'error',
                        durationMs: event.duration_ms,
                        output: event.output,
                        error: event.error,
                        errorType: event.error_type,
                        skillName: event.skill_name || undefined,
                        skillType: event.skill_type || undefined,
                        displayName: event.display_name || undefined,
                        summary: event.summary || undefined,
                        resultLink: event.result_link || undefined,
                      });
                    }
                    // Dispatch successful tool calls to external handler
                    if (event.success && options.onToolCall) {
                      options.onToolCall(event.name, event.output ?? '');
                    }
                    scrollToBottom();

                    break;
                  }
                  case 'tool_start': {
                    if (!msg.toolCalls) msg.toolCalls = [];
                    msg.toolCalls.push({
                      id: event.id,
                      name: event.name,
                      status: 'running',
                      arguments: event.arguments,
                      skillName: event.skill_name || undefined,
                      skillType: event.skill_type || undefined,
                      startedAt: Date.now(),
                    });
                    scrollToBottom();

                    break;
                  }
                  default: {
                    if (
                      event.event === 'authorization_required' &&
                      event.consent_key
                    ) {
                      addConsent(event.consent_key);
                    } else if (event.event === 'confirmation_request') {
                      msg.pendingConfirmation = {
                        action: event.action || '',
                        table: event.table || '',
                        preview: event.preview,
                      };
                    } else if (event.event === 'tool_consent_request') {
                      if (trustSession.value) {
                        msg.pendingConsent = {
                          toolName: event.name || '',
                          arguments: event.arguments,
                          skillName: event.skill_name || undefined,
                          skillType: event.skill_type || undefined,
                          resolved: true,
                          autoApproved: true,
                        };
                        // Defer auto-confirm: sendMessage is blocked during active stream (sending=true).
                        // Set the message and flag; it will be sent after the stream completes.
                        _deferredAutoConfirm = true;
                        inputMessage.value = $t('common.globalAiChat.confirmExecute');
                      } else {
                        msg.pendingConsent = {
                          toolName: event.name || '',
                          arguments: event.arguments,
                          skillName: event.skill_name || undefined,
                          skillType: event.skill_type || undefined,
                        };
                      }
                      scrollToBottom();
                    } else if (
                      event.event === 'action_buttons' &&
                      event.buttons
                    ) {
                      msg.actionButtons = event.buttons;
                      scrollToBottom();
                    } else if (event.event === 'image_result' && event.url) {
                      if (!msg.imageResults) msg.imageResults = [];
                      msg.imageResults.push({
                        url: event.url,
                        isBase64: event.is_base64 || false,
                        revisedPrompt: event.revised_prompt || undefined,
                      });
                      scrollToBottom();
                    } else if (event.event === 'rag_sources' && event.sources) {
                      msg.ragSources = event.sources;
                    } else if (event.event === 'message' && event.delta) {
                      msg.content += event.delta;
                      scrollToBottom();
                    } else if (event.event === 'done') {
                      msg.tokenUsage = event.total_tokens || 0;
                      msg.durationMs = event.duration_ms || 0;
                      if (event.conversation_id) {
                        activeConversationId.value = event.conversation_id as number;
                      }
                      if (event.memory_updated) {
                        lastMemoryUpdated.value = true;
                        msg.memoryUpdated = true;
                      }
                      if (options.onStreamComplete) {
                        options.onStreamComplete();
                      }
                    } else if (event.error) {
                      msg.content = `\u26A0\uFE0F ${
                        event.message || $t('common.requestFailed')
                      }`;
                    }
                  }
                }
              } catch (e: unknown) {
                console.warn('[AI Chat] SSE parse error:', e);
              }
            });
          },
          onEnd() {
            loadConversations();
          },
          onError(error: Error) {
            if (error.name === 'AbortError') return;
            const msg = chatMessages.value[assistantIdx];
            if (msg) {
              if (!msg.content) {
                msg.content = `\u26A0\uFE0F ${$t('common.requestFailed')}`;
              }
              msg.requestFailedRetry = true;
            }
            finalizeMessage();
          },
        },
      );
    } catch {
      // postSSE handles errors internally via onError
    } finally {
      sending.value = false;
      streaming.value = false;
      streamAbortController = null;
      userScrolledUp.value = false;
      finalizeMessage();

      // Send deferred auto-confirm (trustSession approved during active stream)
      if (_deferredAutoConfirm && inputMessage.value.trim()) {
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
    inputMessage.value = $t('common.globalAiChat.confirmExecute');
    sendMessage({ silent: true });
  }

  function rejectAction(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConfirmation || msg.pendingConfirmation.resolved) return;
    msg.pendingConfirmation.resolved = true;
    inputMessage.value = $t('common.globalAiChat.rejectExecute');
    sendMessage({ silent: true });
  }

  function confirmConsent(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConsent || msg.pendingConsent.resolved) return;
    msg.pendingConsent.resolved = true;
    inputMessage.value = $t('common.globalAiChat.confirmExecute');
    sendMessage({ silent: true });
  }

  function rejectConsent(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConsent || msg.pendingConsent.resolved) return;
    msg.pendingConsent.resolved = true;
    msg.pendingConsent.rejected = true;
    inputMessage.value = $t('common.globalAiChat.rejectExecute');
    sendMessage({ silent: true });
  }

  function clickActionButton(msgIndex: number, value: string) {
    const msg = chatMessages.value[msgIndex];
    if (!msg || msg.actionButtonsUsed) return;
    msg.actionButtonsUsed = true;
    inputMessage.value = value;
    sendMessage();
  }

  function editAndResend(msgIndex: number) {
    if (sending.value || streaming.value) return;
    const msg = chatMessages.value[msgIndex];
    if (!msg || msg.role !== 'user') return;

    // Fill input with the user message content
    inputMessage.value = msg.content;

    // Remove this message and all subsequent messages
    chatMessages.value.splice(msgIndex);
  }

  function exportAsMarkdown() {
    if (chatMessages.value.length === 0) return;
    const agentName = selectedAgent.value?.name || 'AI';
    const lines: string[] = [
      `# ${agentName} - ${$t('common.globalAiChat.history')}`,
      '',
    ];
    for (const msg of chatMessages.value) {
      const role = msg.role === 'user' ? '**User**' : `**${agentName}**`;
      lines.push(`### ${role}`, '');
      if (msg.content) lines.push(msg.content);
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
    const agentName = selectedAgent.value?.name || 'AI';
    const lines: string[] = [];
    for (const msg of chatMessages.value) {
      const label = msg.role === 'user' ? $t('common.globalAiChat.user') : agentName;
      lines.push(`${label}:`);
      if (msg.content) lines.push(msg.content);
      lines.push('');
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

    // Find the preceding user message
    let userMsgIndex = -1;
    for (let i = msgIndex - 1; i >= 0; i--) {
      if (chatMessages.value[i]?.role === 'user') {
        userMsgIndex = i;
        break;
      }
    }
    if (userMsgIndex < 0) return;

    const userContent = chatMessages.value[userMsgIndex]!.content;
    const userAttachments = chatMessages.value[userMsgIndex]!.attachments;

    // Remove the assistant message (and any messages after it)
    chatMessages.value.splice(msgIndex);

    // Re-send the user message
    inputMessage.value = userContent;
    clearPendingAttachments();
    if (userAttachments?.length) {
      pendingAttachments.value = [...userAttachments];
    }
    sendMessage({ silent: true });
  }

  function stopGeneration() {
    if (streamAbortController) {
      streamAbortController.abort();
      streamAbortController = null;
    }
    sending.value = false;
    streaming.value = false;
    userScrolledUp.value = false;
    const last = chatMessages.value.at(-1);
    if (last?.streaming) {
      last.streaming = false;
      if (last.role === 'assistant') {
        last.stoppedByUser = true;
      }
    }
  }

  /**
   * Retry after SSE error: remove the failed assistant message, restore last user message to input, and send again / SSE 错误后重试：移除失败助手消息并重新发送
   * (silent = do not push user message again).
   */
  function retryLastMessage() {
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
    if (streamAbortController) {
      streamAbortController.abort();
    }
  }

  // ============ Helpers ============

  return {
    // Agents
    agents,
    agentsLoading,
    selectedAgentId,
    selectedAgent,
    loadAgents,
    selectAgent,

    // Conversations
    conversations,
    conversationsLoading,
    activeConversationId,
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

    // Chat
    chatMessages,
    inputMessage,
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
    confirmAction,
    rejectAction,
    confirmConsent,
    rejectConsent,
    trustSession,
    clickActionButton,
    regenerateMessage,
    editAndResend,
    retryLastMessage,
    cleanup,

    // Model capabilities
    supportsVision,
    imageParams,
    exportAsMarkdown,
    exportAsPlainText,
    totalTokensUsed,

    // Attachments
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
