/**
 * AI Chat Composable
 *
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

import { nextTick, ref, computed, unref } from 'vue';

import {
  deleteChatConversationApi,
  getChatAgentsApi,
  getChatConversationMessagesApi,
  getChatConversationsApi,
  sendChatStreamApi,
  uploadChatFileApi,
} from '#/api/shared/ai-chat';
import { $t } from '#/locales';
import { addConsent, getConsentedActions } from '#/utils/ai-consent';

export interface UseAIChatOptions {
  /** API prefix: '/admin' or '/tenant' */
  apiPrefix: Ref<string> | string;
  /** Upload endpoint */
  uploadUrl: Ref<string> | string;
  /** Initial agent ID to auto-select after loading agents */
  initialAgentId?: Ref<number | undefined> | number;
  /** Callback when a tool call completes successfully */
  onToolCall?: (toolName: string, output: string) => void;
}

export function useAIChat(options: UseAIChatOptions) {
  // ============ Agents ============

  const agents = ref<AgentItem[]>([]);
  const agentsLoading = ref(false);
  const selectedAgentId = ref<number | null>(null);

  const selectedAgent = computed(() =>
    agents.value.find((a) => a.id === selectedAgentId.value) ?? null,
  );

  /**
   * Load agents list and auto-select one.
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
        if (initId && res.items.some((a) => a.id === initId)) {
          selectedAgentId.value = initId;
        } else {
          selectedAgentId.value = res.items[0]!.id;
        }
      }
    } catch {
      // handled by interceptor
    } finally {
      agentsLoading.value = false;
    }
  }

  function selectAgent(agentId: number) {
    if (selectedAgentId.value === agentId) return;
    selectedAgentId.value = agentId;
    activeConversationId.value = null;
    chatMessages.value = [];
  }

  // ============ Conversations ============

  const conversations = ref<ConversationItem[]>([]);
  const conversationsLoading = ref(false);
  const activeConversationId = ref<number | null>(null);

  async function loadConversations() {
    if (!selectedAgentId.value) return;
    conversationsLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix) as string;
      const res = await getChatConversationsApi<ConversationItem>(prefix, selectedAgentId.value);
      conversations.value = res.items;
    } catch {
      // handled by interceptor
    } finally {
      conversationsLoading.value = false;
    }
  }

  function startNewConversation() {
    activeConversationId.value = null;
    chatMessages.value = [];
  }

  async function deleteConversation(convId: number) {
    try {
      const prefix = unref(options.apiPrefix) as string;
      await deleteChatConversationApi(prefix, selectedAgentId.value!, convId);
      if (activeConversationId.value === convId) {
        activeConversationId.value = null;
        chatMessages.value = [];
      }
      await loadConversations();
    } catch {
      // handled by interceptor
    }
  }

  async function loadConversationMessages(convId: number) {
    activeConversationId.value = convId;
    try {
      const prefix = unref(options.apiPrefix) as string;
      const res = await getChatConversationMessagesApi(prefix, selectedAgentId.value!, convId);

      chatMessages.value = mergeMessagesForDisplay(res.message_list ?? []);
      scrollToBottom(true);
    } catch {
      // handled by interceptor
    }
  }

  /**
   * Merge raw DB messages into display ChatMessages.
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
      role: string;
      content: string | null;
      tool_calls?: Array<{
        id?: string;
        function?: { name?: string; arguments?: string };
      }> | null;
      tool_call_id?: string | null;
      tool_name?: string | null;
      metadata?: { attachments?: ChatAttachment[] } | null;
    }>,
  ): ChatMessage[] {
    // Filter out system messages
    const filtered = rawMessages.filter((m) => m.role !== 'system');
    if (filtered.length === 0) return [];

    const result: ChatMessage[] = [];

    // Collect tool responses keyed by tool_call_id for quick lookup
    const toolResponseMap = new Map<
      string,
      { content: string; success: boolean; error?: string; name?: string }
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
        });
        i++;
        continue;
      }

      // Collect all consecutive non-user messages as one assistant turn
      const toolCalls: ToolCallEvent[] = [];
      const contentParts: string[] = [];
      const startIdx = i;

      while (i < filtered.length && filtered[i]!.role !== 'user') {
        const cur = filtered[i]!;

        if (cur.role === 'assistant') {
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
                status: response ? (response.success ? 'success' : 'error') : 'error',
                arguments: parsedArgs,
                output: response?.success ? response.content : undefined,
                error: response && !response.success
                  ? (response.error || response.content)
                  : undefined,
              });
            }
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
        result.push({
          role: 'assistant',
          content: contentParts.join('\n\n'),
          toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
        });
      }
    }

    return result;
  }

  // ============ Chat Messages ============

  const chatMessages = ref<ChatMessage[]>([]);
  const inputMessage = ref('');
  const selectedKBIds = ref<number[]>([]);
  const sending = ref(false);
  const streaming = ref(false);
  const messagesContainer = ref<HTMLElement | null>(null);

  let streamAbortController: AbortController | null = null;

  /** Whether user has manually scrolled up during streaming */
  let userScrolledUp = false;

  /**
   * Smart scroll: only auto-scroll to bottom if user hasn't scrolled up.
   * @param force - if true, always scroll regardless of user position
   */
  function scrollToBottom(force = false) {
    nextTick(() => {
      const el = messagesContainer.value;
      if (!el) return;
      if (force || !userScrolledUp) {
        el.scrollTop = el.scrollHeight;
      }
    });
  }

  /** Check if the user is near the bottom of the scroll container */
  function isNearBottom(): boolean {
    const el = messagesContainer.value;
    if (!el) return true;
    const threshold = 80;
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }

  /** Handle scroll events to detect manual user scroll-up */
  function handleMessagesScroll() {
    if (!streaming.value) return;
    userScrolledUp = !isNearBottom();
  }

  async function copyMessage(content: string) {
    try {
      await navigator.clipboard.writeText(content);
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

  // ============ File Uploads ============

  const pendingAttachments = ref<ChatAttachment[]>([]);
  const uploading = ref(false);
  const fileInput = ref<HTMLInputElement | null>(null);

  async function uploadFile(file: File): Promise<ChatAttachment | null> {
    try {
      uploading.value = true;
      const data = await uploadChatFileApi(unref(options.uploadUrl) as string, file);
      const isImage = file.type.startsWith('image/');
      return {
        type: isImage ? 'image' : 'file',
        url: data.url,
        name: file.name,
        mime_type: file.type,
        preview: isImage ? URL.createObjectURL(file) : undefined,
      };
    } catch {
      return null;
    } finally {
      uploading.value = false;
    }
  }

  async function handleFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.length) return;
    for (const file of Array.from(input.files)) {
      const att = await uploadFile(file);
      if (att) pendingAttachments.value.push(att);
    }
    input.value = '';
  }

  async function handlePaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) {
          const att = await uploadFile(file);
          if (att) pendingAttachments.value.push(att);
        }
      }
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
  }

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      const att = await uploadFile(file);
      if (att) pendingAttachments.value.push(att);
    }
  }

  function removePendingAttachment(idx: number) {
    const att = pendingAttachments.value[idx];
    if (att?.preview) URL.revokeObjectURL(att.preview);
    pendingAttachments.value.splice(idx, 1);
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

  async function sendMessage(opts?: { silent?: boolean }) {
    const silent = opts?.silent ?? false;
    const hasText = inputMessage.value.trim().length > 0;
    const hasAttachments = pendingAttachments.value.length > 0;
    if ((!hasText && !hasAttachments) || !selectedAgentId.value || sending.value)
      return;

    const userMsg = inputMessage.value.trim();
    const msgAttachments = [...pendingAttachments.value];

    if (!silent) {
      chatMessages.value.push({
        role: 'user',
        content: userMsg,
        attachments: msgAttachments.length > 0 ? msgAttachments : undefined,
      });
    }
    chatMessages.value.push({ role: 'assistant', content: '', streaming: true });
    userScrolledUp = false;
    scrollToBottom(true);

    inputMessage.value = '';
    pendingAttachments.value = [];
    await nextTick();

    sending.value = true;
    streaming.value = true;
    const sseBuffer = { value: '' };
    streamAbortController = new AbortController();
    const assistantIdx = chatMessages.value.length - 1;

    const apiAttachments = msgAttachments.length > 0
      ? msgAttachments.map(({ type, url, name, mime_type }) => ({
          type,
          url,
          name,
          mime_type,
        }))
      : undefined;

    try {
      const prefix = unref(options.apiPrefix) as string;
      await sendChatStreamApi(
        prefix,
        selectedAgentId.value!,
        {
          message: userMsg || ' ',
          conversation_id: activeConversationId.value,
          ...(selectedKBIds.value.length > 0
            ? { knowledge_base_ids: selectedKBIds.value }
            : {}),
          consented_actions: getConsentedActions(),
          ...(apiAttachments ? { attachments: apiAttachments } : {}),
        },
        {
          abortController: streamAbortController,
          onMessage(rawChunk: string) {
            parseSSEEvents(rawChunk, sseBuffer, (data) => {
              if (data === '[DONE]') return;
              try {
                const event = JSON.parse(data);
                const msg = chatMessages.value[assistantIdx];
                if (!msg) return;

                if (event.event === 'optimizing_tools') {
                  msg.optimizingTools = {
                    total: event.total || 0,
                    selected: event.selected || 0,
                  };
                  scrollToBottom();
                } else if (event.event === 'thinking') {
                  // frontend already shows loading via streaming + !content
                } else if (event.event === 'tool_start') {
                  if (!msg.toolCalls) msg.toolCalls = [];
                  msg.toolCalls.push({
                    name: event.name,
                    status: 'running',
                    arguments: event.arguments,
                    skillName: event.skill_name || undefined,
                    skillType: event.skill_type || undefined,
                  });
                  scrollToBottom();
                } else if (event.event === 'tool_call') {
                  if (!msg.toolCalls) msg.toolCalls = [];
                  // Find matching running tool and update it
                  const existing = msg.toolCalls.findLast(
                    (tc) => tc.name === event.name && tc.status === 'running',
                  );
                  if (existing) {
                    existing.status = event.success ? 'success' : 'error';
                    existing.durationMs = event.duration_ms;
                    existing.output = event.output;
                    existing.error = event.error;
                    if (event.skill_name) existing.skillName = event.skill_name;
                    if (event.skill_type) existing.skillType = event.skill_type;
                  } else {
                    msg.toolCalls.push({
                      name: event.name,
                      status: event.success ? 'success' : 'error',
                      durationMs: event.duration_ms,
                      output: event.output,
                      error: event.error,
                      skillName: event.skill_name || undefined,
                      skillType: event.skill_type || undefined,
                    });
                  }
                  // Dispatch successful tool calls to external handler
                  if (event.success && options.onToolCall) {
                    options.onToolCall(event.name, event.output ?? '');
                  }
                  scrollToBottom();
                } else if (
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
                  msg.pendingConsent = {
                    toolName: event.name || '',
                    arguments: event.arguments,
                    skillName: event.skill_name || undefined,
                    skillType: event.skill_type || undefined,
                  };
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
                    activeConversationId.value = event.conversation_id;
                  }
                } else if (event.error) {
                  msg.content =
                    '\u26A0\uFE0F ' +
                    (event.message || $t('common.requestFailed'));
                }
              } catch {
                // ignore unparseable lines
              }
            });
          },
          onEnd() {
            const msg = chatMessages.value[assistantIdx];
            if (msg) {
              msg.streaming = false;
              // Clean up any tool calls still stuck in 'running' status
              if (msg.toolCalls) {
                for (const tc of msg.toolCalls) {
                  if (tc.status === 'running') {
                    tc.status = 'error';
                  }
                }
              }
            }
            loadConversations();
          },
          onError(error: Error) {
            if (error.name === 'AbortError') return;
            const msg = chatMessages.value[assistantIdx];
            if (msg) {
              if (!msg.content)
                msg.content =
                  '\u26A0\uFE0F ' + $t('common.requestFailed');
              msg.streaming = false;
              if (msg.toolCalls) {
                for (const tc of msg.toolCalls) {
                  if (tc.status === 'running') {
                    tc.status = 'error';
                  }
                }
              }
            }
          },
        },
      );
    } catch {
      // postSSE handles errors internally via onError
    } finally {
      sending.value = false;
      streaming.value = false;
      streamAbortController = null;
      userScrolledUp = false;
      const msg = chatMessages.value[assistantIdx];
      if (msg) {
        msg.streaming = false;
        if (msg.toolCalls) {
          for (const tc of msg.toolCalls) {
            if (tc.status === 'running') {
              tc.status = 'error';
            }
          }
        }
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
    inputMessage.value = $t('common.globalAiChat.rejectExecute');
    sendMessage({ silent: true });
  }

  function stopGeneration() {
    if (streamAbortController) {
      streamAbortController.abort();
      streamAbortController = null;
    }
    sending.value = false;
    streaming.value = false;
    userScrolledUp = false;
    const last = chatMessages.value.at(-1);
    if (last?.streaming) last.streaming = false;
  }

  function cleanup() {
    if (streamAbortController) {
      streamAbortController.abort();
    }
  }

  // ============ Helpers ============

  function getAgentInitial(agent: AgentItem | null): string {
    if (!agent) return '?';
    return agent.name.charAt(0).toUpperCase();
  }

  function openUrl(url: string) {
    globalThis.open(url, '_blank');
  }

  return {
    // Agents
    agents,
    agentsLoading,
    selectedAgentId,
    selectedAgent,
    loadAgents,
    selectAgent,
    getAgentInitial,

    // Conversations
    conversations,
    conversationsLoading,
    activeConversationId,
    loadConversations,
    startNewConversation,
    deleteConversation,
    loadConversationMessages,

    // Chat
    chatMessages,
    inputMessage,
    selectedKBIds,
    sending,
    streaming,
    messagesContainer,
    sendMessage,
    stopGeneration,
    scrollToBottom,
    handleMessagesScroll,
    copyMessage,
    handleInputKeyDown,
    confirmAction,
    rejectAction,
    confirmConsent,
    rejectConsent,
    cleanup,
    openUrl,

    // Attachments
    pendingAttachments,
    uploading,
    fileInput,
    uploadFile,
    handleFileSelect,
    handlePaste,
    handleDrop,
    handleDragOver,
    removePendingAttachment,
  };
}
