import type { AIInteractionUpdate } from '#/store/shared/ai-panel';
import type { ChatMessage } from '../types';

// @vitest-environment happy-dom
import { flushPromises } from '@vue/test-utils';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getOptimizingToolsForDisplay,
  getRagSourcesForDisplay,
  getThinkingContentForDisplay,
  getToolCallsForDisplay,
  getTurnFlowForDisplay,
} from '../chat-message-turn-flow';
import { shouldDisplayConversationInHistory, useAIChat } from '../use-ai-chat';
import {
  applyStreamingToolResultToTurnFlow,
  applyStreamingToolStartToTurnFlow,
} from '../use-ai-chat-turn-flow';
import {
  baseChatOptions,
  buildAgentList,
  buildAssistantMessage,
  buildConversation,
  buildConversationDetail,
  buildConversationList,
  buildNativeSearchDiagnosticsMessages,
  buildNativeSearchInterruptedMessages,
  buildNativeSearchProgressHistoryMessages,
  buildRichToolHistoryMessages,
  buildThinkingDedupHistoryMessages,
  buildUserMessage,
  sseEvent,
} from './fixtures/ai-chat-fixtures';
import { registerUseAIChatHistoryCases } from './use-ai-chat-history-cases';

const apiMocks = vi.hoisted(() => ({
  getChatAgentKBBindingsApi: vi.fn(),
  getChatAgentsApi: vi.fn(),
  getChatConversationMemoryApi: vi.fn(),
  getChatConversationMessagesApi: vi.fn(),
  getGlobalConversationsApi: vi.fn(),
  sendChatStreamApi: vi.fn(),
}));

const aiPanelStoreMocks = vi.hoisted(() => ({
  consumeInteractionUpdates: vi.fn<() => AIInteractionUpdate[]>(() => []),
  restoreInteractionUpdates: vi.fn(),
}));
const socketStoreMocks = vi.hoisted(() => ({
  connect: vi.fn(),
  emit: vi.fn(),
  isConnected: false,
}));

vi.mock('ant-design-vue', () => ({
  message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock('#/api/shared/ai-chat', () => ({
  buildChatAttachmentFromUpload: vi.fn(),
  clearChatConversationMemoryApi: vi.fn(),
  deleteChatConversationApi: vi.fn(),
  getChatAgentKBBindingsApi: apiMocks.getChatAgentKBBindingsApi,
  getChatAgentsApi: apiMocks.getChatAgentsApi,
  getChatConversationMemoryApi: apiMocks.getChatConversationMemoryApi,
  getChatConversationMessagesApi: apiMocks.getChatConversationMessagesApi,
  getGlobalConversationsApi: apiMocks.getGlobalConversationsApi,
  normalizeChatAttachments: vi.fn((attachments) => attachments),
  sendChatStreamApi: apiMocks.sendChatStreamApi,
  updateChatConversationTitleApi: vi.fn(),
  uploadChatFileApi: vi.fn(),
}));

vi.mock('#/components/business/ai-runtime/page-key-utils', () => ({
  normalizePageKey: (value: string) => value,
}));

vi.mock('#/composables/use-file-upload', () => ({
  useFileUpload: () => ({
    revokePreviewUrls: vi.fn(),
    validateChatFile: vi.fn(() => true),
  }),
}));

vi.mock('#/composables/use-ui-action-channel', () => ({
  waitForPageSessionJoin: vi.fn(() => Promise.resolve(true)),
}));

vi.mock('#/constants/upload', () => ({
  CHAT_ACCEPT_ATTRIBUTE: '',
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/store', () => ({
  useSocketIOStore: () => ({
    connect: socketStoreMocks.connect,
    emit: socketStoreMocks.emit,
    isConnected: socketStoreMocks.isConnected,
  }),
}));

vi.mock('#/store/shared/ai-panel', () => ({
  useAIPanelStore: () => aiPanelStoreMocks,
}));

vi.mock('#/utils/ai-consent', () => ({
  addConsent: vi.fn(),
  clearConsents: vi.fn(),
  getConsentedActions: vi.fn(() => []),
}));

vi.mock('#/utils/error-helpers', () => ({
  showRequestError: vi.fn(),
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: null | string | undefined) => value ?? '',
}));

vi.mock('#/utils/request', () => ({
  normalizeSseEventError: (event: Record<string, unknown>) => ({
    message: String(event.error ?? 'stream error'),
    raw: event,
  }),
  normalizeSseTransportError: (error: Error | { name?: string }) => ({
    message: error instanceof Error ? error.message : 'stream error',
    raw: error,
  }),
}));

type UseAIChatOptions = Parameters<typeof useAIChat>[0];

const createChat = (overrides: Partial<UseAIChatOptions> = {}) =>
  useAIChat({
    ...baseChatOptions,
    ...overrides,
  });

describe('useAIChat interrupted stream recovery', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    apiMocks.getChatAgentsApi.mockReset();
    apiMocks.getChatAgentKBBindingsApi.mockReset();
    apiMocks.getChatConversationMemoryApi.mockReset();
    apiMocks.getChatConversationMessagesApi.mockReset();
    apiMocks.getGlobalConversationsApi.mockReset();
    apiMocks.sendChatStreamApi.mockReset();
    aiPanelStoreMocks.consumeInteractionUpdates.mockReset();
    aiPanelStoreMocks.consumeInteractionUpdates.mockReturnValue([]);
    aiPanelStoreMocks.restoreInteractionUpdates.mockReset();
    socketStoreMocks.connect.mockReset();
    socketStoreMocks.emit.mockReset();
    socketStoreMocks.isConnected = false;

    apiMocks.getChatAgentsApi.mockResolvedValue(buildAgentList());
    apiMocks.getGlobalConversationsApi.mockResolvedValue(
      buildConversationList([buildConversation()]),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  registerUseAIChatHistoryCases({
    apiMocks,
    createChat,
  });

  it('resyncs persisted history after the user manually stops generation', async () => {
    apiMocks.getChatConversationMessagesApi
      .mockResolvedValueOnce({
        agent_id: 1,
        message_list: [],
      })
      .mockResolvedValueOnce({
        agent_id: 1,
        message_list: [
          {
            content: 'hello',
            created_at: '2024-01-01T00:00:00Z',
            role: 'user',
          },
          {
            agent_id: 1,
            agent_name: 'Agent One',
            content: 'partial answer',
            created_at: '2024-01-01T00:00:01Z',
            metadata: {
              completion_reason: 'interrupted',
              interrupted: true,
              partial: true,
            },
            model_name: 'gpt-test',
            role: 'assistant',
          },
        ],
      });

    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          abortController: AbortController;
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: 'partial answer' }),
        );
        await new Promise<void>((resolve) => {
          options.abortController.signal.addEventListener(
            'abort',
            () => resolve(),
            { once: true },
          );
        });
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = 'hello';

    const sendPromise = chat.sendMessage({ routeSource: 'manual-stop-test' });
    await flushPromises();

    expect(chat.activeConversationId.value).toBe(42);
    expect(chat.chatMessages.value).toHaveLength(2);
    expect(chat.chatMessages.value[1]?.content).toBe('partial answer');

    chat.stopGeneration();
    await flushPromises();

    expect(chat.chatMessages.value[1]?.stoppedByUser).toBe(true);
    expect(apiMocks.getChatConversationMessagesApi).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(300);
    await sendPromise;
    await flushPromises();

    expect(apiMocks.getChatConversationMessagesApi).toHaveBeenCalledTimes(2);
    expect(chat.chatMessages.value).toHaveLength(2);
    expect(chat.chatMessages.value[1]?.content).toBe('partial answer');
    expect(chat.chatMessages.value[1]?.partial).toBe(true);
    expect(chat.chatMessages.value[1]?.interrupted).toBe(true);
    expect(chat.chatMessages.value[1]?.stoppedByUser).toBeUndefined();
  });

  it('recovers a newly created conversation from history when the stream fails before conversation event', async () => {
    const recoveredConversation = buildConversation({
      created_at: '2026-04-07T12:00:00Z',
      id: 1044,
      title: '查今天AI新闻',
      updated_at: '2026-04-07T12:00:01Z',
    });
    const closedRecoveredConversation = buildConversation({ status: 'closed' });

    apiMocks.getGlobalConversationsApi
      .mockResolvedValueOnce(buildConversationList([buildConversation()]))
      .mockResolvedValueOnce(
        buildConversationList([
          recoveredConversation,
          closedRecoveredConversation,
        ]),
      )
      .mockResolvedValueOnce(
        buildConversationList([
          recoveredConversation,
          closedRecoveredConversation,
        ]),
      );
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(
        [
          buildUserMessage('查今天AI新闻', {
            created_at: '2026-04-07T12:00:00Z',
          }),
          buildAssistantMessage(
            '并发 Session 超限：当前 3 个（限制：3 个）。',
            {
              created_at: '2026-04-07T12:00:01Z',
              metadata: {
                error: true,
                error_debug_message:
                  '并发 Session 超限：当前 3 个（限制：3 个）。',
                error_message: '并发 Session 超限：当前 3 个（限制：3 个）。',
                error_only: true,
                error_trace_id: 'trace-stream-1044',
                error_type: 'stream_execution_error',
              },
            },
          ),
        ],
        {
          context_diagnostics: {
            failure_kind: 'stream_execution_error',
            persistence_error: true,
          },
          last_run_summary: {
            error_message: '并发 Session 超限：当前 3 个（限制：3 个）。',
            turn_outcome: 'failed',
          },
        },
      ),
    );
    apiMocks.sendChatStreamApi.mockRejectedValue(
      new Error('upstream exploded'),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversations();
    chat.inputMessage.value = '查今天AI新闻';

    await chat.sendMessage({ routeSource: 'stream-failure-recovery-test' });
    await flushPromises();

    expect(apiMocks.getGlobalConversationsApi).toHaveBeenCalledTimes(3);
    expect(apiMocks.getChatConversationMessagesApi).toHaveBeenCalledWith(
      '/tenant',
      1044,
    );
    expect(chat.activeConversationId.value).toBe(1044);
    expect(chat.conversations.value.map((item) => item.id)).toEqual([1044, 42]);
    expect(chat.chatMessages.value.map((item) => item.content)).toEqual([
      '查今天AI新闻',
      '',
    ]);
    expect(chat.chatMessages.value[1]?.error).toMatchObject({
      debugMessage: '并发 Session 超限：当前 3 个（限制：3 个）。',
      message: '并发 Session 超限：当前 3 个（限制：3 个）。',
      traceId: 'trace-stream-1044',
    });
  });

  it('refreshes persisted conversation detail immediately after done when persistence is committed', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(
        [
          buildUserMessage('查今天AI新闻', {
            created_at: '2026-04-07T04:38:30Z',
          }),
          buildAssistantMessage('这里是已持久化的最终答复', {
            created_at: '2026-04-07T04:38:31Z',
            metadata: {
              completion_reason: 'completed',
              protocol_path: 'responses',
              termination_reason: 'completed',
              turn_outcome: 'success',
            },
          }),
        ],
        { interaction_mode_effective: 'trusted_auto' },
      ),
    );
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '这里是流式中的答复' }),
        );
        await options.onMessage(
          sseEvent({
            event: 'done',
            conversation_id: 42,
            persistence_committed: true,
            persisted_message_count: 2,
            total_tokens: 18,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '查今天AI新闻';
    await chat.sendMessage({ routeSource: 'persistence-commit-test' });
    await flushPromises();

    expect(apiMocks.getChatConversationMessagesApi).toHaveBeenCalledWith(
      '/tenant',
      42,
    );
    expect(chat.chatMessages.value.at(-1)?.content).toBe(
      '这里是已持久化的最终答复',
    );
    expect(chat.chatMessages.value.at(-1)?.streaming).toBeFalsy();
  });

  it('refreshes persisted conversation detail after done when conversation id is known even without persistence flags', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(
        [
          buildUserMessage('查今天AI新闻', {
            created_at: '2026-04-07T04:38:30Z',
          }),
          buildAssistantMessage('这里是 done 后回拉的持久化答复', {
            created_at: '2026-04-07T04:38:31Z',
            metadata: {
              completion_reason: 'completed',
              protocol_path: 'responses',
              termination_reason: 'completed',
              turn_outcome: 'success',
            },
          }),
        ],
        { interaction_mode_effective: 'trusted_auto' },
      ),
    );
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 43 }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '这里是流式中的答复' }),
        );
        await options.onMessage(
          sseEvent({ event: 'done', conversation_id: 43, total_tokens: 21 }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '查今天AI新闻';
    await chat.sendMessage({ routeSource: 'done-conversation-id-sync-test' });
    await flushPromises();

    expect(apiMocks.getChatConversationMessagesApi).toHaveBeenCalledWith(
      '/tenant',
      43,
    );
    expect(chat.chatMessages.value.at(-1)?.content).toBe(
      '这里是 done 后回拉的持久化答复',
    );
    expect(chat.chatMessages.value.at(-1)?.streaming).toBeFalsy();
  });

  it('uses updated_at as the recency signal for empty conversations', () => {
    expect(
      shouldDisplayConversationInHistory(
        {
          agent_id: 1,
          created_at: '2026-03-01T12:00:00Z',
          id: 3001,
          message_count: 0,
          status: 'closed',
          title: null,
          updated_at: '2026-04-07T11:30:00Z',
        },
        {
          nowMs: Date.parse('2026-04-07T12:00:00Z'),
        },
      ),
    ).toBe(true);
  });

  it('restores trusted_auto interactionMode from backend conversation detail', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([buildUserMessage('hello')], {
        interaction_mode_effective: 'trusted_auto',
      }),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    expect(chat.interactionMode.value).toBe('trusted_auto');
  });

  it('sends auto_approved interaction update when trusted_auto auto-approves tool consent', async () => {
    let streamCallCount = 0;
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        streamCallCount += 1;
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        if (streamCallCount === 1) {
          await options.onMessage(
            sseEvent({
              event: 'tool_consent_request',
              name: 'web_search',
              arguments: { query: 'latest news' },
            }),
          );
        }
        await options.onMessage(
          sseEvent({ event: 'done', conversation_id: 42, total_tokens: 5 }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.interactionMode.value = 'trusted_auto';
    chat.inputMessage.value = '查一下';

    const sendPromise = chat.sendMessage({
      routeSource: 'native-search-status-test',
    });
    await vi.advanceTimersByTimeAsync(1000);
    await sendPromise;
    await flushPromises();
    await flushPromises();
    expect(apiMocks.sendChatStreamApi).toHaveBeenCalledTimes(2);

    const autoApproveBody = apiMocks.sendChatStreamApi.mock.calls.at(
      -1,
    )?.[2] as Record<string, unknown> | undefined;
    expect(autoApproveBody?.interaction_updates).toEqual([
      {
        kind: 'pending_consent',
        auto_approved: true,
        rejected: false,
        tool_name: 'web_search',
      },
    ]);
    expect(autoApproveBody).not.toHaveProperty('interaction_mode');
  });

  it('auto-approves consent resend without surfacing pending consent state', async () => {
    let streamCallCount = 0;
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(
        [
          buildUserMessage('请查一下北京今天的天气。'),
          buildAssistantMessage('', {
            metadata: {
              pending_consent: {
                arguments: { city: '北京' },
                tool_name: 'get_current_weather',
              },
            },
          }),
        ],
        {
          interaction_mode_effective: 'trusted_auto',
        },
      ),
    );
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        streamCallCount += 1;
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        if (streamCallCount === 1) {
          await options.onMessage(
            sseEvent({
              event: 'tool_consent_request',
              interaction_mode_effective: 'trusted_auto',
              name: 'get_current_weather',
              arguments: { city: '北京' },
            }),
          );
        }
        await options.onMessage(
          sseEvent({ event: 'done', conversation_id: 42, total_tokens: 5 }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.interactionMode.value = 'trusted_auto';
    chat.inputMessage.value = '请查一下北京今天的天气。';

    const firstSendPromise = chat.sendMessage({
      routeSource: 'trusted-auto-consent-resend-test',
    });
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1000);
    await firstSendPromise;
    await flushPromises();

    expect(chat.interactionMode.value).toBe('trusted_auto');
    expect(chat.interactionModeEffective.value).toBe('trusted_auto');
    expect(chat.chatMessages.value.at(-1)?.pendingConsent).toBeUndefined();

    const consentBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(apiMocks.sendChatStreamApi).toHaveBeenCalledTimes(2);
    expect(consentBody).not.toHaveProperty('interaction_mode');
    expect(consentBody?.interaction_updates).toEqual([
      {
        kind: 'pending_consent',
        auto_approved: true,
        rejected: false,
        tool_name: 'get_current_weather',
      },
    ]);
  });

  it('stores summary_payload from tool_call SSE events for tool cards', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({
            arguments: { question: '统计今天调用情况' },
            event: 'tool_start',
            id: 'tc_query_records',
            name: 'query_records',
          }),
        );
        await options.onMessage(
          sseEvent({
            duration_ms: 120,
            event: 'tool_call',
            id: 'tc_query_records',
            name: 'query_records',
            success: true,
            summary: '按今天范围统计调用并按租户分组',
            summary_payload: {
              filters: ['today'],
              group_by: ['t.name'],
              metrics: ['COUNT(acl.id)'],
              tables: ['ai_call_logs', 'tenants'],
              tool_kind: 'query_records',
            },
          }),
        );
        await options.onMessage(sseEvent({ event: 'done', total_tokens: 18 }));
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '统计今天调用情况';

    await chat.sendMessage({ routeSource: 'tool-summary-test' });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.toolCalls).toBeUndefined();
    expect(
      getToolCallsForDisplay(assistantMessage!)?.[0]?.summaryPayload,
    ).toEqual({
      filters: ['today'],
      group_by: ['t.name'],
      metrics: ['COUNT(acl.id)'],
      tables: ['ai_call_logs', 'tenants'],
      tool_kind: 'query_records',
    });
  });

  it('parses canonical turn flow SSE events and keeps legacy fallback fields usable', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_stage',
            id: 'thinking-1',
            status: 'running',
            summary: '先理解用户问题',
            title: 'Thinking',
            type: 'thinking',
          }),
        );
        await options.onMessage(
          sseEvent({
            detail_lines: ['先识别上下文', '再决定工具路径'],
            event: 'turn_stage_update',
            id: 'thinking-1',
            status: 'completed',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_stage',
            id: 'tool-selection-1',
            metrics: { selected: 0, total: 15 },
            status: 'skipped',
            type: 'tool_selection',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_evidence',
            id: 'source-kb-1',
            kind: 'knowledge_base',
            snippet: '命中知识库政策条目',
            title: '企业知识库',
          }),
        );
        await options.onMessage(
          sseEvent({
            answer_card: {
              sections: [
                { body: '可执行方案如下', id: 'section-1', title: '结论' },
              ],
              source_chip_ids: ['source-kb-1'],
              summary: '建议先走标准流程',
            },
            event: 'turn_answer_card',
          }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '最终答复。' }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'completed',
            event: 'done',
            final_stage_status: 'completed',
            total_tokens: 16,
            trace_id: 'trace-turn-flow-canonical',
            turn_flow_complete: true,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '请给出执行方案';
    await chat.sendMessage({ routeSource: 'turn-flow-canonical-test' });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(
      assistantMessage.turnFlow?.timeline?.map((stage) => stage.type),
    ).toEqual(
      expect.arrayContaining(['thinking', 'tool_selection', 'completed']),
    );
    expect(assistantMessage.turnFlow?.answerCard?.summary).toBe(
      '建议先走标准流程',
    );
    expect(assistantMessage.turnFlow?.traceId).toBe(
      'trace-turn-flow-canonical',
    );
    expect(assistantMessage.optimizingTools).toBeUndefined();
    expect(getOptimizingToolsForDisplay(assistantMessage)).toEqual({
      selected: 0,
      total: 15,
    });
    expect(assistantMessage.thinkingContent).toBeUndefined();
    expect(getThinkingContentForDisplay(assistantMessage)).toBe(
      '先识别上下文\n\n再决定工具路径',
    );
    expect(getRagSourcesForDisplay(assistantMessage)?.[0]?.doc_name).toBe(
      '企业知识库',
    );
  });

  it('suppresses legacy semantic duplicates when canonical turn stages exist', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_stage',
            id: 'thinking-stage-1',
            status: 'running',
            summary: '先判断问题范围',
            type: 'thinking',
          }),
        );
        await options.onMessage(
          sseEvent({
            detail_lines: ['内部细节 1', '内部细节 2'],
            event: 'turn_stage_update',
            id: 'thinking-stage-1',
            status: 'completed',
            type: 'thinking',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_stage',
            id: 'tool-selection-stage-1',
            metrics: { selected: 0, total: 9 },
            status: 'skipped',
            type: 'tool_selection',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_stage',
            id: 'tool-execution-stage-1',
            metrics: { running: 1, total: 1 },
            status: 'running',
            type: 'tool_execution',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'optimizing_tools',
            selected: 0,
            total: 9,
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'tool_start',
            id: 'tc-dedupe-1',
            name: 'query_records',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'tool_call',
            id: 'tc-dedupe-1',
            name: 'query_records',
            success: true,
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_stage_update',
            id: 'tool-execution-stage-1',
            metrics: { running: 0, total: 1 },
            status: 'completed',
            type: 'tool_execution',
          }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '最终答复。' }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'completed',
            event: 'done',
            final_stage_status: 'completed',
            total_tokens: 9,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '请继续';
    await chat.sendMessage({ routeSource: 'turn-flow-dedupe-semantics-test' });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    const timeline = assistantMessage.turnFlow?.timeline ?? [];
    expect(timeline.filter((stage) => stage.type === 'thinking')).toHaveLength(
      1,
    );
    expect(
      timeline.filter((stage) => stage.type === 'tool_selection'),
    ).toHaveLength(1);
    expect(
      timeline.filter((stage) => stage.type === 'tool_execution'),
    ).toHaveLength(1);
    expect(
      timeline.some((stage) =>
        [
          'legacy-thinking',
          'legacy-tool-execution',
          'legacy-tool-selection',
        ].includes(stage.id ?? ''),
      ),
    ).toBe(false);
    expect(assistantMessage.thinkingContent).toBeUndefined();
    expect(getThinkingContentForDisplay(assistantMessage)).toBe(
      '内部细节 1\n\n内部细节 2',
    );
  });

  it('does not synthesize tool_selection display stages from legacy optimizingTools when turnFlow exists', () => {
    const assistantMessage = buildAssistantMessage('最终答复。', {
      clientKey: 'assistant-turn-flow-without-selection-stage',
      optimizingTools: {
        selected: 0,
        total: 9,
      },
      turnFlow: {
        timeline: [
          {
            id: 'thinking-stage',
            status: 'completed',
            summary: '先判断问题范围',
            type: 'thinking',
          },
          {
            id: 'completed-stage',
            status: 'completed',
            type: 'completed',
          },
        ],
      },
    }) as ChatMessage;

    expect(
      getTurnFlowForDisplay(assistantMessage).timeline.map((stage) => stage.id),
    ).toEqual(['thinking-stage', 'completed-stage']);
    expect(getOptimizingToolsForDisplay(assistantMessage)).toEqual({
      selected: 0,
      total: 9,
    });
  });

  it('projects provider_failure_after_partial_progress as failed/error terminal state', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '这是已生成的部分答复。' }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'provider_failure_after_partial_progress',
            event: 'done',
            failure_kind: 'provider_error',
            final_stage_status: 'completed',
            total_tokens: 11,
            turn_outcome: 'partial',
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '总结一下';
    await chat.sendMessage({ routeSource: 'turn-flow-provider-failure-test' });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    const timeline = assistantMessage?.turnFlow?.timeline ?? [];
    expect(assistantMessage?.turnFlow?.finalStageStatus).toBe('error');
    expect(assistantMessage?.turnFlow?.completionReason).toBe(
      'provider_failure_after_partial_progress',
    );
    expect(
      timeline.some(
        (stage) => stage.type === 'failed' && stage.status === 'error',
      ),
    ).toBe(true);
    expect(timeline.some((stage) => stage.status === 'running')).toBe(false);
  });

  it('clears stale running turn stages after lifecycle finalization marks orphaned tools as error', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_stage',
            id: 'tool-execution-running-stage',
            metrics: { running: 1, total: 1 },
            status: 'running',
            type: 'tool_execution',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'tool_start',
            id: 'tc-orphan-1',
            name: 'query_records',
          }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'provider_timeout',
            event: 'done',
            final_stage_status: 'error',
            total_tokens: 5,
            turn_flow_complete: true,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '开始执行';
    await chat.sendMessage({ routeSource: 'turn-flow-finalize-orphan-test' });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    const timeline = assistantMessage?.turnFlow?.timeline ?? [];
    expect(assistantMessage?.toolCalls).toBeUndefined();
    expect(getToolCallsForDisplay(assistantMessage!)?.[0]?.status).toBe(
      'error',
    );
    expect(
      timeline.find((stage) => stage.id === 'tool-execution-running-stage')
        ?.status,
    ).toBe('error');
    expect(assistantMessage?.turnFlow?.finalStageStatus).toBe('error');
    expect(
      timeline.some(
        (stage) => stage.type === 'failed' && stage.status === 'error',
      ),
    ).toBe(true);
    expect(timeline.some((stage) => stage.status === 'running')).toBe(false);
  });

  it('surfaces native web search progress as a visible tool card', async () => {
    let releaseDone = () => {};
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(buildNativeSearchProgressHistoryMessages()),
    );
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'status', status: 'web_search_in_progress' }),
        );
        await new Promise<void>((resolve) => {
          releaseDone = resolve;
        });
        await options.onMessage(
          sseEvent({
            conversation_id: 42,
            event: 'done',
            selected_tool_names: ['web_search', 'fetch_url'],
            total_tokens: 12,
            turn_record: {
              auto_fetch_gate_reason: 'native_search_completed',
              metadata: {
                stream_progress_kinds: ['web_search_in_progress'],
              },
            },
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '搜索一下';

    const sendPromise = chat.sendMessage({
      routeSource: 'native-search-status-test',
    });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.toolCalls).toBeUndefined();
    expect(getToolCallsForDisplay(assistantMessage!)?.[0]).toMatchObject({
      displayName: 'common.globalAiChat.toolNativeSearch',
      name: 'native_web_search',
      status: 'running',
    });

    releaseDone();
    await sendPromise;
    await flushPromises();

    expect(getToolCallsForDisplay(assistantMessage!)?.[0]).toMatchObject({
      displayName: 'common.globalAiChat.toolNativeSearch',
      name: 'native_web_search',
      status: 'success',
    });
  });

  it('restores persisted rich tool contract and interaction state from conversation history', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(buildRichToolHistoryMessages()),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.toolCalls?.[0]?.displayName).toBe('数据查询');
    expect(assistantMessage?.toolCalls?.[0]?.summaryPayload).toEqual({
      filters: ['today'],
      tables: ['ai_call_logs'],
      tool_kind: 'query_records',
    });
    expect(assistantMessage?.pendingConfirmation?.table).toBe('ai_call_logs');
    expect(assistantMessage?.pendingConfirmation?.toolName).toBe(
      'query_records',
    );
    expect(assistantMessage?.pendingConsent?.toolName).toBe('query_records');
    expect(assistantMessage?.actionButtons?.[0]?.label).toBe('查看明细');
  });

  it('restores native web search cards from persisted turn diagnostics', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(buildNativeSearchDiagnosticsMessages()),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.toolCalls?.[0]).toMatchObject({
      displayName: 'common.globalAiChat.toolNativeSearch',
      name: 'native_web_search',
      status: 'success',
    });
  });

  it('deduplicates repeated persisted thinking blocks inside one merged assistant turn', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(buildThinkingDedupHistoryMessages()),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.thinkingContent).toBe(
      '**Considering tool responses** I have the weather details now.',
    );
    expect(assistantMessage?.content).toBe(
      '广州今天多云，气温 24 到 29 摄氏度。',
    );
    expect(assistantMessage?.turnFlow).toBeUndefined();
  });

  it('keeps legacy persisted metadata visible without rebuilding a synthetic turnFlow', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('查一下企业知识库策略'),
        buildAssistantMessage('可以按规范执行。', {
          metadata: {
            completion_reason: 'completed',
            context_sources: [{ kind: 'knowledge_base', name: 'policy_kb' }],
            rag_sources: [
              {
                doc_id: 11,
                doc_name: '合规流程文档',
                score: 0.92,
                snippet: '流程要求先审计后执行',
                source_kind: 'formal_kb',
              },
            ],
            selected_tool_names: ['query_records'],
            thinking_content: '先检查可用上下文，再输出最终建议。',
            turn_outcome: 'success',
          },
          tool_calls: [
            {
              function: { name: 'query_records' },
              id: 'tc_legacy_flow_1',
              success: true,
              summary: '查询到匹配记录',
            },
          ],
        }),
      ]),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.turnFlow).toBeUndefined();
    expect(assistantMessage?.completionReason).toBe('completed');
    expect(assistantMessage?.thinkingContent).toContain('先检查可用上下文');
    expect(assistantMessage?.toolCalls?.[0]?.name).toBe('query_records');
    expect(assistantMessage?.ragSources?.[0]?.doc_name).toBe('合规流程文档');
  });

  it('keeps persisted turn_flow during history merge and exposes legacy fallbacks', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('给我一份回放摘要'),
        buildAssistantMessage('历史答复。', {
          turn_flow: {
            answer_card: {
              summary: '历史结构化摘要',
            },
            completion_reason: 'completed',
            evidence: [
              {
                id: 'kb-source-1',
                kind: 'knowledge_base',
                snippet: '来自知识库条目',
                title: '知识库 A',
              },
            ],
            timeline: [
              {
                detail_lines: ['先读取上下文', '再输出答复'],
                id: 'thinking-legacy',
                status: 'completed',
                type: 'thinking',
              },
              {
                id: 'tool-select-legacy',
                metrics: { selected: 0, total: 12 },
                status: 'skipped',
                type: 'tool_selection',
              },
            ],
          },
        }),
      ]),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(assistantMessage.turnFlow?.completionReason).toBe('completed');
    expect(assistantMessage.turnFlow?.answerCard?.summary).toBe(
      '历史结构化摘要',
    );
    expect(
      assistantMessage.turnFlow?.timeline?.map((stage) => stage.id),
    ).toEqual(
      expect.arrayContaining(['thinking-legacy', 'tool-select-legacy']),
    );
    expect(assistantMessage.thinkingContent).toBeUndefined();
    expect(assistantMessage.optimizingTools).toBeUndefined();
    expect(getOptimizingToolsForDisplay(assistantMessage)).toEqual({
      selected: 0,
      total: 12,
    });
    expect(getRagSourcesForDisplay(assistantMessage)?.[0]?.doc_name).toBe(
      '知识库 A',
    );
  });

  it('deduplicates repeated persisted assistant content blocks inside one merged turn', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('总结一下'),
        buildAssistantMessage('这是同一段总结。'),
        buildAssistantMessage('这是同一段总结。', {
          created_at: '2024-01-01T00:00:02Z',
        }),
      ]),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.content).toBe('这是同一段总结。');
  });

  it('keeps terminal assistant content stable when late clear_content/message chunks arrive', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '可信最终答复' }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'completed',
            event: 'done',
            total_tokens: 9,
            turn_flow_complete: true,
          }),
        );
        await options.onMessage(sseEvent({ event: 'clear_content' }));
        await options.onMessage(
          sseEvent({ event: 'message', delta: '污染片段' }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '测试终态污染';
    await chat.sendMessage({
      routeSource: 'terminal-clear-content-guard-test',
    });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.content).toBe('可信最终答复');
    expect(assistantMessage?.streaming).toBeFalsy();
  });

  it('terminalizes immediately on SSE event.error and ignores late deltas', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('测试 event.error'),
        buildAssistantMessage('部分输出', {
          metadata: {
            completion_reason: 'error',
            turn_outcome: 'failed',
          },
        }),
      ]),
    );
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onEnd?: () => Promise<void>;
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '部分输出' }),
        );
        await options.onMessage(
          sseEvent({
            conversation_id: 42,
            error: 'upstream exploded',
            error_type: 'stream_execution_error',
          }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '晚到增量' }),
        );
        if (options.onEnd) {
          await options.onEnd();
        }
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '测试 event.error';
    await chat.sendMessage({ routeSource: 'event-error-terminalize-test' });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.content).toBe('部分输出');
    expect(assistantMessage?.requestFailedRetry).toBe(true);
    expect(assistantMessage?.streaming).toBeFalsy();
    expect(
      (assistantMessage?.turnFlow?.timeline ?? []).some(
        (stage) => stage.status === 'running',
      ),
    ).toBe(false);
  });

  it('matches tool_call completion by tool_call_id for duplicate tool names', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({
            event: 'tool_start',
            id: 'tc-id-1',
            name: 'query_records',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'tool_start',
            id: 'tc-id-2',
            name: 'query_records',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'tool_call',
            id: 'tc-id-1',
            name: 'query_records',
            output: 'first result',
            success: true,
          }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'completed',
            event: 'done',
            total_tokens: 7,
            turn_flow_complete: true,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '测试 tool_call_id 匹配';
    await chat.sendMessage({ routeSource: 'tool-call-id-match-test' });
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.toolCalls).toBeUndefined();
    const toolCallById = new Map(
      (getToolCallsForDisplay(assistantMessage!) ?? []).map((toolCall) => [
        toolCall.id,
        toolCall,
      ]),
    );
    expect(toolCallById.get('tc-id-1')?.status).toBe('success');
    expect(toolCallById.get('tc-id-1')?.output).toBe('first result');
    expect(toolCallById.get('tc-id-2')?.status).toBe('error');
  });

  it('does not merge idless tool_call completion onto same-name running evidence', () => {
    const assistantMessage = {
      ...buildAssistantMessage(''),
      clientKey: 'assistant-idless-tool-call-test',
    } as ChatMessage;

    applyStreamingToolStartToTurnFlow(assistantMessage, {
      id: 'tc-id-1',
      name: 'query_records',
    });
    applyStreamingToolStartToTurnFlow(assistantMessage, {
      id: 'tc-id-2',
      name: 'query_records',
    });
    applyStreamingToolResultToTurnFlow(assistantMessage, {
      name: 'query_records',
      output: 'fallback result',
      success: true,
    });

    const toolCalls = getToolCallsForDisplay(assistantMessage) ?? [];
    expect(toolCalls).toHaveLength(3);
    expect(
      toolCalls.filter((toolCall) => toolCall.status === 'running'),
    ).toHaveLength(2);
    expect(
      toolCalls.filter((toolCall) => toolCall.status === 'success'),
    ).toHaveLength(1);
    expect(
      toolCalls.find((toolCall) => toolCall.id === 'tc-id-1'),
    ).toMatchObject({
      id: 'tc-id-1',
      name: 'query_records',
      status: 'running',
    });
    expect(
      toolCalls.find((toolCall) => toolCall.id === 'tc-id-2'),
    ).toMatchObject({
      id: 'tc-id-2',
      name: 'query_records',
      status: 'running',
    });
    expect(
      toolCalls.find((toolCall) => toolCall.output === 'fallback result'),
    ).toMatchObject({
      name: 'query_records',
      output: 'fallback result',
      status: 'success',
    });
  });

  it('prefers trusted final assistant content over concatenated intermediate history parts', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('总结一下过程'),
        buildAssistantMessage('中间步骤片段'),
        buildAssistantMessage('可信最终答复', {
          metadata: {
            completion_reason: 'completed',
            turn_outcome: 'success',
          },
        }),
      ]),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.content).toBe('可信最终答复');
  });

  it('marks persisted native web search progress cards as error when the turn ended early', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(buildNativeSearchInterruptedMessages()),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.toolCalls?.[0]).toMatchObject({
      displayName: 'common.globalAiChat.toolNativeSearch',
      name: 'native_web_search',
      status: 'error',
    });
  });

  it('applies knowledge base feedback from SSE to selectedKBIds', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({
            dropped_knowledge_base_ids: [20],
            effective_knowledge_base_ids: [10],
            event: 'knowledge_base_feedback',
          }),
        );
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(sseEvent({ event: 'done', total_tokens: 18 }));
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.selectedKBIds.value = [10, 20];
    chat.inputMessage.value = '统计今天调用情况';

    await chat.sendMessage({ routeSource: 'kb-feedback-test' });
    await flushPromises();

    expect(chat.selectedKBIds.value).toEqual([10]);
  });

  it('builds KB-only mention candidates and selects a knowledge base on Enter', async () => {
    apiMocks.getChatAgentKBBindingsApi.mockResolvedValue([
      {
        enabled: true,
        kb_name: 'Operations KB',
        knowledge_base_id: 10,
      },
    ]);

    const chat = createChat();

    await chat.loadAgents();
    await flushPromises();

    chat.inputMessage.value = '@oper';
    await flushPromises();

    expect(chat.mentionCandidates.value).toEqual([
      {
        binding: expect.objectContaining({
          kb_name: 'Operations KB',
          knowledge_base_id: 10,
        }),
        kind: 'knowledge_base',
      },
    ]);

    const handled = chat.handleInputKeyDown(
      new KeyboardEvent('keydown', { key: 'Enter' }),
    );

    expect(handled).toBe(true);
    expect(chat.selectedKBIds.value).toEqual([10]);
    expect(chat.inputMessage.value).toBe('');
  });

  it('does not tag debounced assistant placeholders as rich text drafts', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: 'debounced answer' }),
        );
        await options.onMessage(sseEvent({ event: 'done', total_tokens: 12 }));
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = 'debounced question';

    await chat.sendMessage();
    await flushPromises();

    expect(chat.chatMessages.value).toHaveLength(1);
    expect(chat.chatMessages.value[0]?.role).toBe('user');

    await vi.advanceTimersByTimeAsync(1000);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.content).toBe('debounced answer');
    expect(assistantMessage?.routeSource).toBeUndefined();
    expect(assistantMessage?.source).toBeUndefined();

    const requestBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(requestBody?.route_source).toBeUndefined();
  });

  it('short-circuits page operation chat when socket channel is unavailable', async () => {
    const chat = createChat({
      pageContextResolver: () => ({
        active_surface_id: 'page:tenant.dashboard',
        page_key: 'tenant.dashboard',
        suggested_tools: {
          primary: ['ui_get_snapshot', 'ui_list_interactables'],
          secondary: ['ui_click'],
        },
        surface_stack: [
          {
            kind: 'page',
            surface_id: 'page:tenant.dashboard',
            title: 'Tenant Dashboard',
          },
        ],
        ui_epoch: 1,
      }),
      pageSessionIdGetter: () => 'page-session-1',
    });

    await chat.loadAgents();
    chat.inputMessage.value = '请帮我打开智能体页面';

    const sendPromise = chat.sendMessage();
    await vi.advanceTimersByTimeAsync(3200);
    await sendPromise;
    await flushPromises();

    expect(socketStoreMocks.connect).toHaveBeenCalledOnce();
    expect(apiMocks.sendChatStreamApi).not.toHaveBeenCalled();
  });

  it('sends interaction_updates when user resolves confirmation/consent/button state', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(sseEvent({ event: 'done', total_tokens: 18 }));
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.chatMessages.value = [
      {
        clientKey: 'assistant-confirm-message',
        role: 'assistant',
        content: '需要处理',
        pendingConfirmation: {
          action: 'query',
          table: 'ai_call_logs',
          toolName: 'ui_get_snapshot',
        },
      },
      {
        clientKey: 'assistant-consent-message',
        role: 'assistant',
        content: '需要授权',
        pendingConsent: {
          toolName: 'query_records',
        },
      },
      {
        clientKey: 'assistant-action-message',
        role: 'assistant',
        actionButtons: [{ label: '查看明细', value: '查看明细' }],
        content: '请选择',
      },
    ];
    chat.confirmAction(0);
    await flushPromises();
    const confirmBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(confirmBody?.interaction_updates).toEqual([
      {
        action: 'query',
        kind: 'pending_confirmation',
        rejected: false,
        table: 'ai_call_logs',
        tool_name: 'ui_get_snapshot',
      },
    ]);
    expect(confirmBody?.message).toBe('');

    chat.interactionMode.value = 'trusted_auto';
    chat.confirmConsent(1);
    await flushPromises();
    const consentBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(consentBody?.interaction_updates).toEqual([
      {
        kind: 'pending_consent',
        rejected: false,
        tool_name: 'query_records',
      },
    ]);
    expect(consentBody).not.toHaveProperty('interaction_mode');
    expect(consentBody?.message).toBe('');

    chat.inputMessage.value = '查看明细';
    chat.clickActionButton(2, '查看明细');
    await vi.advanceTimersByTimeAsync(1000);
    await flushPromises();
    const actionBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(actionBody?.interaction_updates).toEqual([
      {
        kind: 'action_buttons',
        value: '查看明细',
      },
    ]);
  });

  it('sends tool_name-first pending confirmation updates without empty legacy fields', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(sseEvent({ event: 'done', total_tokens: 18 }));
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.chatMessages.value = [
      {
        clientKey: 'assistant-confirm-message',
        role: 'assistant',
        content: '需要继续打开表面',
        pendingConfirmation: {
          toolName: 'ui_open_surface',
        },
      },
    ];

    chat.confirmAction(0);
    await flushPromises();

    const confirmBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;

    expect(confirmBody?.interaction_updates).toEqual([
      {
        kind: 'pending_confirmation',
        rejected: false,
        tool_name: 'ui_open_surface',
      },
    ]);
  });

  it('merges queued ai-panel interaction updates into the next request body', async () => {
    apiMocks.sendChatStreamApi.mockImplementation(
      async (
        _prefix: string,
        _agentId: number,
        _body: Record<string, unknown>,
        options: {
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'done', conversation_id: 42, total_tokens: 5 }),
        );
      },
    );

    aiPanelStoreMocks.consumeInteractionUpdates.mockReturnValue([
      {
        kind: 'pending_confirmation',
        rejected: false,
        tool_name: 'ui_open_surface',
      },
    ] as AIInteractionUpdate[]);

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '继续创建';
    const sendPromise = chat.sendMessage();
    await vi.advanceTimersByTimeAsync(1000);
    await sendPromise;
    await flushPromises();

    const requestBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;

    expect(requestBody?.interaction_updates).toEqual([
      {
        kind: 'pending_confirmation',
        rejected: false,
        tool_name: 'ui_open_surface',
      },
    ]);
    expect(aiPanelStoreMocks.restoreInteractionUpdates).not.toHaveBeenCalled();
  });
});
