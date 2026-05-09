import type { ChatMessage } from '../types';

import type { AIInteractionUpdate } from '#/store/shared/ai-panel';

/**
 * Test type: behavioral
 * Verifies: AI chat streaming keeps canonical turnFlow authoritative and keeps legacy assistant fields out of process cards.
 * Mock strategy: only transport/store boundaries are mocked; turnFlow ingestion and display helpers run real.
 */
// @vitest-environment happy-dom
import { flushPromises } from '@vue/test-utils';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { buildTurnFlowState } from '../../ai-chat-kernel/TurnFlowState';
import {
  getOptimizingToolsForDisplay,
  getRagSourcesForDisplay,
  getThinkingContentForDisplay,
  getToolCallsForDisplay,
  getTurnFlowForDisplay,
} from '../chat-message-turn-flow';
import { shouldDisplayConversationInHistory, useAIChat } from '../use-ai-chat';
import { createStreamSseHandler } from '../use-ai-chat-streaming-request-sse';
import {
  baseChatOptions,
  buildAgentList,
  buildAssistantMessage,
  buildConversation,
  buildConversationDetail,
  buildConversationList,
  buildLegacyToolInterruptedMessages,
  buildRichToolHistoryMessages,
  buildThinkingDedupHistoryMessages,
  buildUserMessage,
  sseEvent,
} from './fixtures/ai-chat-fixtures';
import { registerUseAIChatHistoryCases } from './use-ai-chat-history-cases';

const apiMocks = vi.hoisted(() => ({
  getChatAgentKBBindingsApi: vi.fn(),
  getChatAgentSkillsApi: vi.fn(),
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
  getChatAgentSkillsApi: apiMocks.getChatAgentSkillsApi,
  getChatAgentsApi: apiMocks.getChatAgentsApi,
  getChatConversationMemoryApi: apiMocks.getChatConversationMemoryApi,
  getChatConversationMessagesApi: apiMocks.getChatConversationMessagesApi,
  getGlobalConversationsApi: apiMocks.getGlobalConversationsApi,
  normalizeChatAttachments: vi.fn((attachments) => attachments),
  sendChatStreamApi: apiMocks.sendChatStreamApi,
  updateChatConversationTitleApi: vi.fn(),
  uploadChatFileApi: vi.fn(),
}));

vi.mock('#/composables/use-file-upload', () => ({
  useFileUpload: () => ({
    revokePreviewUrls: vi.fn(),
    validateChatFile: vi.fn(() => true),
  }),
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

async function flushStreamSend() {
  await flushPromises();
  await vi.advanceTimersByTimeAsync(1000);
  await flushPromises();
}

describe('useAIChat interrupted stream recovery', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    apiMocks.getChatAgentsApi.mockReset();
    apiMocks.getChatAgentKBBindingsApi.mockReset();
    apiMocks.getChatAgentSkillsApi.mockReset();
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
    apiMocks.getChatAgentSkillsApi.mockResolvedValue([]);
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

    const sendPromise = chat.sendMessage();
    await flushStreamSend();

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

    await chat.sendMessage();
    await flushStreamSend();

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
    await chat.sendMessage();
    await flushStreamSend();

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
    await chat.sendMessage();
    await flushStreamSend();

    expect(apiMocks.getChatConversationMessagesApi).toHaveBeenCalledWith(
      '/tenant',
      43,
    );
    expect(chat.chatMessages.value.at(-1)?.content).toBe(
      '这里是 done 后回拉的持久化答复',
    );
    expect(chat.chatMessages.value.at(-1)?.streaming).toBeFalsy();
  });

  it('refreshes conversation memory after a stream reports memory_updated', async () => {
    apiMocks.getChatConversationMemoryApi.mockResolvedValue({
      constraints: [],
      preferences: [],
      task_states: [],
      verified_facts: ['用户名字是ix long'],
    });
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
          sseEvent({ event: 'message', delta: '已记住。' }),
        );
        await options.onMessage(
          sseEvent({
            conversation_id: 42,
            event: 'done',
            memory_updated: true,
            total_tokens: 0,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '我叫ix long 请记住';
    const sendPromise = chat.sendMessage();
    await vi.advanceTimersByTimeAsync(1000);
    await sendPromise;
    await flushPromises();
    await flushPromises();

    expect(apiMocks.getChatConversationMemoryApi).toHaveBeenCalledWith(
      '/tenant',
      42,
    );
    expect(chat.lastMemoryUpdated.value).toBe(true);
    expect(chat.memoryState.value?.verified_facts).toEqual([
      '用户名字是ix long',
    ]);
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
              name: 'query_records',
              arguments: { query: 'latest records' },
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

    const sendPromise = chat.sendMessage();
    await vi.advanceTimersByTimeAsync(1000);
    await sendPromise;
    await flushPromises();
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1000);
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
        tool_name: 'query_records',
      },
    ]);
    expect(autoApproveBody).not.toHaveProperty('interaction_mode');
  });

  it('auto-approves consent resend without surfacing pending consent state', async () => {
    let streamCallCount = 0;
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(
        [
          buildUserMessage('请生成今天的报表摘要。'),
          buildAssistantMessage('', {
            metadata: {
              pending_consent: {
                arguments: { report: 'daily' },
                tool_name: 'report_summary',
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
              name: 'report_summary',
              arguments: { report: 'daily' },
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
    chat.inputMessage.value = '请生成今天的报表摘要。';

    const firstSendPromise = chat.sendMessage();
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
        tool_name: 'report_summary',
      },
    ]);
  });

  it('stores summary_payload from canonical turn_evidence while ignoring legacy tool SSE events', async () => {
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
            summary: 'legacy tool_call summary must stay ignored',
            summary_payload: {
              source: 'legacy_tool_call',
            },
          }),
        );
        await options.onMessage(
          sseEvent({
            display_name: '数据查询',
            event: 'turn_evidence',
            id: 'canonical-tool-tc-query-records',
            kind: 'tool',
            snippet: '按今天范围统计调用并按租户分组',
            status: 'success',
            summary_payload: {
              filters: ['today'],
              group_by: ['t.name'],
              metrics: ['COUNT(acl.id)'],
              source: 'canonical_turn_evidence',
              tables: ['ai_call_logs', 'tenants'],
              tool_kind: 'query_records',
            },
            tool_call_id: 'tc_query_records',
            tool_name: 'query_records',
          }),
        );
        await options.onMessage(sseEvent({ event: 'done', total_tokens: 18 }));
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '统计今天调用情况';

    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    const toolCalls = getToolCallsForDisplay(assistantMessage) ?? [];
    expect(toolCalls).toHaveLength(1);
    expect(toolCalls[0]?.summaryPayload).toEqual({
      filters: ['today'],
      group_by: ['t.name'],
      metrics: ['COUNT(acl.id)'],
      source: 'canonical_turn_evidence',
      tables: ['ai_call_logs', 'tenants'],
      tool_kind: 'query_records',
    });
  });

  it('parses canonical turn flow SSE events and keeps canonical display helpers populated', async () => {
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
    await chat.sendMessage();
    await flushStreamSend();

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
    expect(getOptimizingToolsForDisplay(assistantMessage)).toEqual({
      selected: 0,
      total: 15,
    });
    expect(getThinkingContentForDisplay(assistantMessage)).toBe(
      '先识别上下文\n\n再决定工具路径',
    );
    expect(getRagSourcesForDisplay(assistantMessage)?.[0]?.doc_name).toBe(
      '企业知识库',
    );
  });

  it('drops retired web evidence kind from SSE instead of showing it as knowledge-base', async () => {
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
            event: 'turn_evidence',
            id: 'legacy-web-source',
            kind: 'web',
            title: 'Approved KB URL source',
            url: 'https://example.com/source',
          }),
        );
        await options.onMessage(sseEvent({ event: 'done', total_tokens: 9 }));
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '根据已授权资料回答';

    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(assistantMessage.turnFlow?.evidence).toEqual([]);
    expect(getToolCallsForDisplay(assistantMessage)).toBeUndefined();
    expect(getRagSourcesForDisplay(assistantMessage)).toBeUndefined();
  });

  it('ignores live legacy semantic SSE events on tenant streams while keeping canonical cards', async () => {
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
            event: 'optimizing_tools',
            selected: 1,
            total: 9,
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'thinking',
            delta: 'legacy thinking should stay hidden',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'rag_sources',
            sources: [
              {
                doc_id: 7,
                doc_name: 'Legacy KB',
                score: 0.82,
                snippet: 'legacy snippet',
              },
            ],
          }),
        );
        await options.onMessage(
          sseEvent({
            answer_card: {
              sections: [
                { body: 'canonical body', id: 'summary-1', title: 'Summary' },
              ],
              summary: 'Canonical answer card',
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
            total_tokens: 6,
            turn_flow_complete: true,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '请总结一下';
    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }

    const rawMessage = assistantMessage as ChatMessage &
      Record<string, unknown>;

    expect(assistantMessage.turnFlow?.answerCard?.summary).toBe(
      'Canonical answer card',
    );
    expect(getThinkingContentForDisplay(assistantMessage)).toBeUndefined();
    expect(getOptimizingToolsForDisplay(assistantMessage)).toBeUndefined();
    expect(getRagSourcesForDisplay(assistantMessage)).toBeUndefined();
    expect(rawMessage.thinkingContent).toBeUndefined();
    expect(rawMessage.optimizingTools).toBeUndefined();
    expect(rawMessage.ragSources).toBeUndefined();
  });

  it('ignores live legacy semantic SSE events on admin streams without backfilling legacy assistant fields', async () => {
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
            event: 'optimizing_tools',
            selected: 1,
            total: 9,
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'thinking',
            delta: 'admin legacy thinking',
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'rag_sources',
            sources: [
              {
                doc_id: 8,
                doc_name: 'Admin Legacy KB',
                score: 0.91,
                snippet: 'admin legacy snippet',
              },
            ],
          }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: '管理员答复。' }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'completed',
            event: 'done',
            total_tokens: 6,
            turn_flow_complete: true,
          }),
        );
      },
    );

    const chat = createChat({ apiPrefix: '/admin' });

    await chat.loadAgents();
    chat.inputMessage.value = '请给我调试信息';
    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    const rawMessage = assistantMessage as ChatMessage &
      Record<string, unknown>;

    expect(getThinkingContentForDisplay(assistantMessage)).toBeUndefined();
    expect(getOptimizingToolsForDisplay(assistantMessage)).toBeUndefined();
    expect(getRagSourcesForDisplay(assistantMessage)).toBeUndefined();
    expect(rawMessage.thinkingContent).toBeUndefined();
    expect(rawMessage.optimizingTools).toBeUndefined();
    expect(rawMessage.ragSources).toBeUndefined();
  });

  it('ignores admin legacy semantic SSE events at the handler boundary for persisted assistant messages', () => {
    const assistantMessage = buildAssistantMessage('', {
      streaming: false,
    }) as ChatMessage;
    const scrollToBottom = vi.fn();
    const lifecycle = {
      didTerminalizeMessage: false,
      getAssistantMessage: () => assistantMessage,
      hasReceivedStreamPayload: false,
    };

    const handleSsePayload = createStreamSseHandler(
      {
        options: { apiPrefix: '/admin' },
        scrollToBottom,
      } as unknown as Parameters<typeof createStreamSseHandler>[0],
      lifecycle as unknown as Parameters<typeof createStreamSseHandler>[1],
    );

    handleSsePayload(
      JSON.stringify({
        event: 'optimizing_tools',
        selected: 1,
        total: 9,
      }),
    );
    handleSsePayload(
      JSON.stringify({
        delta: 'admin legacy thinking',
        event: 'thinking',
      }),
    );
    handleSsePayload(
      JSON.stringify({
        event: 'rag_sources',
        sources: [
          {
            doc_id: 8,
            doc_name: 'Admin Legacy KB',
            score: 0.91,
            snippet: 'admin legacy snippet',
          },
        ],
      }),
    );

    expect(lifecycle.hasReceivedStreamPayload).toBe(true);
    expect(assistantMessage.turnFlow).toBeUndefined();
    expect(scrollToBottom).not.toHaveBeenCalled();
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
    await chat.sendMessage();
    await flushStreamSend();

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
    expect(getOptimizingToolsForDisplay(assistantMessage)).toBeUndefined();
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
    await chat.sendMessage();
    await flushStreamSend();

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

  it('clears stale running canonical turn stages after lifecycle finalization', async () => {
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
    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    const timeline = assistantMessage?.turnFlow?.timeline ?? [];
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(getToolCallsForDisplay(assistantMessage)).toBeUndefined();
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

  it('syncs empty assistant content from canonical turnFlow terminal summary on done', async () => {
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
            completion_reason: 'provider_timeout',
            event: 'done',
            final_stage_status: 'error',
            total_tokens: 5,
            turn_flow: {
              answer_card: {
                sections: [
                  {
                    content: 'AI 供应商请求超时',
                    id: 'final-answer',
                    title: 'Answer',
                  },
                ],
                summary: 'AI 供应商请求超时',
              },
              completion_reason: 'provider_timeout',
              error_surface: {
                message: 'AI 供应商请求超时',
              },
              final_stage_status: 'error',
              timeline: [
                {
                  id: 'thinking',
                  status: 'completed',
                  type: 'thinking',
                },
                {
                  id: 'failed',
                  status: 'error',
                  summary: 'AI 供应商请求超时',
                  type: 'failed',
                },
              ],
            },
            turn_flow_complete: true,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '开始执行';
    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(assistantMessage.content).toBe('AI 供应商请求超时');
    expect(assistantMessage.turnFlow?.finalStageStatus).toBe('error');
  });

  it('does not sync process-only answer card labels into empty assistant content on done', async () => {
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
            completion_reason: 'completed',
            event: 'done',
            final_stage_status: 'completed',
            total_tokens: 5,
            turn_flow: {
              answer_card: {
                summary: '结果整理',
              },
              completion_reason: 'completed',
              evidence: [
                {
                  id: 'aa-leaderboard',
                  kind: 'document',
                  title: 'Artificial Analysis LLM Leaderboard',
                },
              ],
              final_stage_status: 'completed',
              timeline: [
                {
                  id: 'stage-retrieval',
                  metrics: { source_count: 2 },
                  status: 'completed',
                  summary: '找到 2 条来源',
                  type: 'retrieval',
                },
                {
                  id: 'stage-answer',
                  status: 'completed',
                  summary: '已完成答案整理',
                  type: 'answer_assembly',
                },
              ],
            },
            turn_flow_complete: true,
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '查一下大模型排行榜 2026';
    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(assistantMessage.content).toBe('');
    expect(assistantMessage.turnFlow?.answerCard?.summary).toBe('结果整理');
    expect(
      assistantMessage.turnFlow?.timeline?.map((stage) => stage.id),
    ).toEqual(
      expect.arrayContaining(['stage-retrieval', 'stage-answer', 'turn-final']),
    );
  });

  it('does not sync generic provider retry copy into empty assistant content on done', async () => {
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
            completion_reason: 'provider_error',
            event: 'done',
            failure_kind: 'provider_error',
            final_stage_status: 'error',
            turn_flow: {
              completion_reason: 'provider_error',
              error_surface: {
                error_type: 'provider_error',
                message:
                  'The assistant could not finish this turn. Please retry.',
              },
              final_stage_status: 'error',
              timeline: [
                {
                  id: 'stage-retrieval-blocked',
                  metrics: { source_count: 0 },
                  status: 'error',
                  summary: '候选来源未通过核实',
                  type: 'retrieval',
                },
              ],
              turn_outcome: 'failed',
            },
            turn_flow_complete: true,
            turn_outcome: 'failed',
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '整理候选资料';
    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(assistantMessage.content).toBe('');
    expect(assistantMessage.turnFlow?.finalStageStatus).toBe('error');
    expect(assistantMessage.turnFlow?.failureKind).toBe('provider_error');
  });

  it('keeps nested provider failures authoritative even after prior retrieval chrome streamed in', async () => {
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
            event: 'turn_answer_card',
            answer_card: {
              summary: '结果整理',
              source_chip_ids: ['evidence_1', 'evidence_2', 'evidence_3'],
            },
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_evidence',
            evidence: {
              id: 'evidence_1',
              kind: 'knowledge_base',
              title: 'skill_resolver',
            },
          }),
        );
        await options.onMessage(
          sseEvent({
            event: 'turn_stage',
            id: 'stage-retrieval',
            metrics: { source_count: 3 },
            status: 'completed',
            summary: 'Retrieved 3 sources',
            type: 'retrieval',
          }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'provider_unavailable',
            event: 'done',
            final_stage_status: 'completed',
            turn_flow: {
              completion_reason: 'provider_unavailable',
              error_surface: {
                error_type: 'untrusted_final_output_source',
                message: 'Connection error.',
              },
              evidence: [
                {
                  id: 'evidence_1',
                  kind: 'knowledge_base',
                  title: 'skill_resolver',
                },
                {
                  id: 'evidence_2',
                  kind: 'memory',
                  title: 'long_term_memory',
                },
                {
                  id: 'evidence_3',
                  kind: 'knowledge_base',
                  title: 'gpt-5.5',
                },
              ],
              final_stage_status: 'error',
              timeline: [
                {
                  id: 'retrieval',
                  metrics: { source_count: 3 },
                  status: 'completed',
                  summary: 'Retrieved 3 sources',
                  type: 'retrieval',
                },
                {
                  id: 'failed',
                  status: 'error',
                  summary: 'provider_unavailable',
                  type: 'failed',
                },
              ],
              turn_outcome: 'partial',
            },
            turn_flow_complete: true,
            turn_outcome: 'partial',
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '帮我搜索一下2026年中国新能源汽车销量排行';
    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(assistantMessage.turnFlow?.finalStageStatus).toBe('error');
    expect(assistantMessage.turnFlow?.failureKind).toBe('provider_unavailable');
    expect(assistantMessage.turnFlow?.turnOutcome).toBe('partial');
    expect(assistantMessage.turnFlow?.completionReason).toBe(
      'provider_unavailable',
    );
    expect(
      assistantMessage.turnFlow?.timeline?.some(
        (stage) => stage.type === 'failed' && stage.status === 'error',
      ),
    ).toBe(true);
    const kernelState = buildTurnFlowState(assistantMessage);
    expect(kernelState.evidence).toEqual([]);
    expect(kernelState.selectedEvidence).toEqual([]);
    expect(kernelState.flow.answerCard?.sourceChipIds).toEqual([]);
    expect(
      kernelState.timeline.find((stage) => stage.type === 'retrieval')?.status,
    ).toBe('skipped');
  });

  it('hydrates canonical tool evidence from done turn_record.turn_flow when no tool_call stream event arrived', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([]),
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
          sseEvent({ event: 'message', delta: '今日报表摘要已生成。' }),
        );
        await options.onMessage(
          sseEvent({
            completion_reason: 'completed',
            conversation_id: 42,
            event: 'done',
            selected_tool_names: ['report_summary'],
            total_tokens: 24,
            turn_record: {
              turn_flow: {
                completion_reason: 'completed',
                evidence: [
                  {
                    display_name: '报表摘要',
                    id: 'ev_tool_tc_report_1',
                    kind: 'tool',
                    output: '今日报表摘要已生成。',
                    snippet: '已生成今日报表摘要',
                    status: 'success',
                    tool_call_id: 'tc_report_1',
                    tool_name: 'report_summary',
                  },
                ],
                final_stage_status: 'completed',
                timeline: [
                  {
                    id: 'tool-execution',
                    metrics: {
                      completed_tool_calls: 1,
                      total: 1,
                    },
                    status: 'completed',
                    summary: '执行了 1 个工具调用',
                    tool_call_ids: ['tc_report_1'],
                    type: 'tool_execution',
                  },
                  {
                    id: 'answer-assembly',
                    status: 'completed',
                    summary: '已生成最终答复',
                    type: 'answer_assembly',
                  },
                  {
                    id: 'terminal',
                    status: 'completed',
                    summary: 'completed',
                    type: 'completed',
                  },
                ],
              },
            },
          }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = '生成今天的报表摘要';

    const sendPromise = chat.sendMessage();
    await vi.advanceTimersByTimeAsync(3200);
    await sendPromise;
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }

    expect(getToolCallsForDisplay(assistantMessage)).toEqual([
      expect.objectContaining({
        displayName: '报表摘要',
        id: 'tc_report_1',
        name: 'report_summary',
        output: '今日报表摘要已生成。',
        status: 'success',
        summary: '已生成今日报表摘要',
      }),
    ]);
    expect(
      getTurnFlowForDisplay(assistantMessage).timeline.some(
        (stage) => stage.type === 'tool_execution',
      ),
    ).toBe(true);
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
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(getToolCallsForDisplay(assistantMessage)?.[0]?.displayName).toBe(
      '数据查询',
    );
    expect(
      getToolCallsForDisplay(assistantMessage)?.[0]?.summaryPayload,
    ).toEqual({
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

  it('deduplicates repeated canonical thinking stages inside one merged assistant turn', async () => {
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
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(getThinkingContentForDisplay(assistantMessage)).toBe(
      '**Considering tool responses** I have the report details now.',
    );
    expect(assistantMessage?.content).toBe(
      '今日报表显示调用量平稳，异常率低于阈值。',
    );
    expect(assistantMessage?.turnFlow).toBeDefined();
  });

  it('keeps persisted canonical turnFlow available to shared display helpers', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('查一下企业知识库策略'),
        buildAssistantMessage('可以按规范执行。', {
          metadata: {
            completion_reason: 'completed',
            context_sources: [{ kind: 'knowledge_base', name: 'policy_kb' }],
            selected_tool_names: ['query_records'],
            turn_outcome: 'success',
          },
          turn_flow: {
            completion_reason: 'completed',
            evidence: [
              {
                id: 'tc_policy_lookup_1',
                kind: 'tool',
                snippet: '查询到匹配记录',
                status: 'success',
                tool_call_id: 'tc_policy_lookup_1',
                tool_name: 'query_records',
                title: 'query_records',
              },
              {
                id: 'kb-policy-11',
                doc_name: '合规流程文档',
                kind: 'knowledge_base',
                score: 0.92,
                snippet: '流程要求先审计后执行',
                title: '合规流程文档',
              },
            ],
            timeline: [
              {
                detail_lines: ['先检查可用上下文，再输出最终建议。'],
                id: 'turn-thinking',
                status: 'completed',
                summary: '先检查可用上下文，再输出最终建议。',
                type: 'thinking',
              },
              {
                id: 'turn-tool-execution',
                status: 'completed',
                tool_call_ids: ['tc_policy_lookup_1'],
                type: 'tool_execution',
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
    const rawMessage = assistantMessage as ChatMessage &
      Record<string, unknown>;
    expect(assistantMessage?.turnFlow).toBeDefined();
    expect(assistantMessage?.completionReason).toBe('completed');
    expect(getThinkingContentForDisplay(rawMessage)).toContain(
      '先检查可用上下文',
    );
    expect(getToolCallsForDisplay(rawMessage)?.[0]?.name).toBe('query_records');
    expect(getRagSourcesForDisplay(rawMessage)?.[0]?.doc_name).toBe(
      '合规流程文档',
    );
    expect(rawMessage.thinkingContent).toBeUndefined();
    expect(rawMessage.toolCalls).toBeUndefined();
    expect(rawMessage.ragSources).toBeUndefined();
  });

  it('does not backfill legacy assistant fields once persisted turnFlow already exists', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('给我一份回放摘要'),
        buildAssistantMessage('历史答复。', {
          metadata: {
            rag_sources: [
              {
                doc_id: 11,
                doc_name: '合规流程文档',
                score: 0.92,
                snippet: '流程要求先审计后执行',
                source_kind: 'formal_kb',
              },
            ],
            thinking_content: '先读取上下文，再输出答复',
          },
          tool_calls: [
            {
              display_name: '数据查询',
              function: {
                arguments: '{"table":"ai_call_logs"}',
                name: 'query_records',
              },
              id: 'tc_history_turn_flow_1',
              success: true,
              summary: '查询到匹配记录',
              summary_payload: {
                filters: ['today'],
                tables: ['ai_call_logs'],
              },
            },
          ],
          turn_flow: {
            answer_card: {
              summary: '历史结构化摘要',
            },
            completion_reason: 'completed',
            timeline: [
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
    ).toEqual(['tool-select-legacy']);
    expect(getThinkingContentForDisplay(assistantMessage)).toBeUndefined();
    expect(getToolCallsForDisplay(assistantMessage)).toBeUndefined();
    expect(getOptimizingToolsForDisplay(assistantMessage)).toEqual({
      selected: 0,
      total: 12,
    });
    expect(getRagSourcesForDisplay(assistantMessage)).toBeUndefined();
  });

  it('keeps canonical tool evidence authoritative when legacy toolCalls share the same tool_call_id', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('给我一份工具回放'),
        buildAssistantMessage('历史答复。', {
          tool_calls: [
            {
              display_name: '数据查询',
              function: {
                arguments: '{"table":"ai_call_logs"}',
                name: 'query_records',
              },
              id: 'tc_history_conflict_1',
              output: 'legacy output',
              success: true,
              summary: 'legacy summary',
            },
          ],
          turn_flow: {
            completion_reason: 'completed',
            evidence: [
              {
                id: 'tc_history_conflict_1',
                kind: 'tool',
                output: 'canonical output',
                snippet: 'canonical summary',
                status: 'error',
                tool_call_id: 'tc_history_conflict_1',
                tool_name: 'query_records',
                title: '数据查询',
              },
            ],
            timeline: [
              {
                id: 'turn-tool-execution',
                status: 'error',
                tool_call_ids: ['tc_history_conflict_1'],
                type: 'tool_execution',
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

    expect(getToolCallsForDisplay(assistantMessage)).toEqual([
      expect.objectContaining({
        id: 'tc_history_conflict_1',
        name: 'query_records',
        output: 'canonical output',
        status: 'error',
        summary: 'canonical summary',
      }),
    ]);
  });

  it('keeps legacy-only persisted assistant fields out of process cards when canonical turnFlow is missing', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([
        buildUserMessage('回放一下旧工具记录'),
        buildAssistantMessage('历史答复。', {
          metadata: {
            completion_reason: 'completed',
            optimizing_tools: { selected: 0, total: 12 },
            rag_sources: [
              {
                doc_id: 11,
                doc_name: '旧知识库来源',
                score: 0.92,
                snippet: 'legacy rag snippet',
                source_kind: 'formal_kb',
              },
            ],
            thinking_content: 'legacy thinking should stay audit-only',
          },
          tool_calls: [
            {
              display_name: '数据查询',
              function: {
                arguments: '{"table":"ai_call_logs","page":1}',
                name: 'query_records',
              },
              output: 'first legacy output',
              success: true,
              summary: 'first legacy summary',
            },
            {
              display_name: '数据查询',
              function: {
                arguments: '{"table":"ai_call_logs","page":2}',
                name: 'query_records',
              },
              output: 'second legacy output',
              success: true,
              summary: 'second legacy summary',
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
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }

    expect(assistantMessage.content).toBe('历史答复。');
    expect(assistantMessage.turnFlow).toBeUndefined();
    expect(getThinkingContentForDisplay(assistantMessage)).toBeUndefined();
    expect(getOptimizingToolsForDisplay(assistantMessage)).toBeUndefined();
    expect(getToolCallsForDisplay(assistantMessage)).toBeUndefined();
    expect(getRagSourcesForDisplay(assistantMessage)).toBeUndefined();
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
    await chat.sendMessage();
    await flushStreamSend();

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
    await chat.sendMessage();
    await flushStreamSend();

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

  it('ignores legacy tool_start/tool_call SSE events with duplicate tool names', async () => {
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
    chat.inputMessage.value = '测试旧工具事件忽略';
    await chat.sendMessage();
    await flushStreamSend();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage).toBeDefined();
    if (!assistantMessage) {
      throw new Error('assistant message missing');
    }
    expect(getToolCallsForDisplay(assistantMessage)).toBeUndefined();
    expect(assistantMessage.turnFlow?.evidence).toEqual([]);
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

  it('does not synthesize tool cards from legacy progress diagnostics without tool evidence', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(buildLegacyToolInterruptedMessages()),
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
    expect(getToolCallsForDisplay(assistantMessage)).toBeUndefined();
  });

  it('applies knowledge base feedback from SSE to selectedKBIds', async () => {
    apiMocks.getChatAgentKBBindingsApi.mockResolvedValue([
      {
        enabled: true,
        kb_name: 'Operations KB',
        knowledge_base_id: 10,
      },
      {
        enabled: true,
        kb_name: 'Legacy KB',
        knowledge_base_id: 20,
      },
    ]);
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

    await chat.sendMessage();
    await flushPromises();

    expect(chat.selectedKBIds.value).toEqual([10]);
  });

  it('builds bound KB and skill-package mention candidates and inserts skill mentions as visible text', async () => {
    apiMocks.getChatAgentKBBindingsApi.mockResolvedValue([
      {
        enabled: true,
        kb_name: 'Operations KB',
        knowledge_base_id: 10,
      },
    ]);
    apiMocks.getChatAgentSkillsApi.mockResolvedValue([
      {
        agent_id: 1,
        enabled: true,
        id: 20,
        is_auto_bound: false,
        package_description: 'Record lookup helper',
        package_id: 30,
        package_is_system: true,
        package_name: '历史工具',
        skill_description: 'Search records through a bound tool',
        skill_id: 40,
        skill_key: 'legacy_tool_search',
        skill_name: 'Legacy Tool Skill',
        skill_type: 'toolkit',
      },
    ]);

    const chat = createChat();

    await chat.loadAgents();
    await flushPromises();

    chat.inputMessage.value = '@';
    await flushPromises();

    expect(chat.mentionCandidates.value).toEqual([
      {
        binding: expect.objectContaining({
          kb_name: 'Operations KB',
          knowledge_base_id: 10,
        }),
        kind: 'knowledge_base',
      },
      {
        binding: expect.objectContaining({
          package_name: '历史工具',
          skill_id: 40,
        }),
        kind: 'skill_package',
      },
    ]);

    const handled = chat.handleInputKeyDown(
      new KeyboardEvent('keydown', { key: 'Enter' }),
    );

    expect(handled).toBe(true);
    expect(chat.selectedKBIds.value).toEqual([10]);
    expect(chat.inputMessage.value).toBe('');

    chat.inputMessage.value = '@历史';
    await flushPromises();

    const skillHandled = chat.handleInputKeyDown(
      new KeyboardEvent('keydown', { key: 'Enter' }),
    );

    expect(skillHandled).toBe(true);
    expect(chat.inputMessage.value).toBe('@历史工具 ');
  });

  it('keeps skill-package mentions as visible text instead of hidden activation', async () => {
    apiMocks.getChatAgentSkillsApi.mockResolvedValue([
      {
        agent_id: 1,
        enabled: true,
        id: 21,
        is_auto_bound: false,
        package_description: 'Record lookup helper',
        package_id: 31,
        package_is_system: true,
        package_name: '历史工具',
        skill_description: 'Search records through a bound tool',
        skill_id: 41,
        skill_key: 'legacy_tool_search',
        skill_name: 'Legacy Tool Skill',
        skill_type: 'toolkit',
      },
    ]);
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
    await flushPromises();

    chat.inputMessage.value = '@历史';
    await flushPromises();
    expect(
      chat.handleInputKeyDown(new KeyboardEvent('keydown', { key: 'Enter' })),
    ).toBe(true);
    expect(chat.inputMessage.value).toBe('@历史工具 ');
    chat.inputMessage.value += '统计今天调用情况';

    await chat.sendMessage();
    await flushStreamSend();

    const requestBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(requestBody).toBeDefined();
    expect(requestBody).not.toHaveProperty('selected_skill_names');
    expect(requestBody?.message).toBe('@历史工具 统计今天调用情况');
  });

  it('does not name-filter live skill package mentions in the frontend', async () => {
    apiMocks.getChatAgentSkillsApi.mockResolvedValue([
      {
        agent_id: 1,
        enabled: true,
        id: 22,
        is_auto_bound: false,
        package_description: 'Allowed internal knowledge helper',
        package_id: 32,
        package_is_system: true,
        package_name: '知识检索',
        skill_description: 'Query approved knowledge records',
        skill_id: 42,
        skill_key: 'knowledge_lookup',
        skill_name: '知识检索',
        skill_type: 'toolkit',
      },
      {
        agent_id: 1,
        enabled: true,
        id: 23,
        is_auto_bound: false,
        package_description: 'Allowed reporting helper',
        package_id: 33,
        package_is_system: false,
        package_name: '报表工具',
        skill_description: 'Query reports',
        skill_id: 43,
        skill_key: 'report_query',
        skill_name: '报表查询',
        skill_type: 'toolkit',
      },
    ]);
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
    await flushPromises();

    expect(
      chat.getAgentSkillBindings(1)?.map((item) => item.package_name),
    ).toEqual(['知识检索', '报表工具']);

    chat.inputMessage.value = '@知识';
    await flushPromises();
    expect(chat.mentionCandidates.value).toEqual([
      expect.objectContaining({
        kind: 'skill_package',
      }),
    ]);
    expect(
      chat.handleInputKeyDown(new KeyboardEvent('keydown', { key: 'Enter' })),
    ).toBe(true);
    expect(chat.inputMessage.value).toBe('@知识检索 ');

    chat.inputMessage.value = '@报表';
    await flushPromises();
    expect(chat.mentionCandidates.value).toEqual([
      expect.objectContaining({
        kind: 'skill_package',
      }),
    ]);
    expect(
      chat.handleInputKeyDown(new KeyboardEvent('keydown', { key: 'Enter' })),
    ).toBe(true);
    expect(chat.inputMessage.value).toBe('@报表工具 ');
    chat.inputMessage.value += '统计今天调用情况';
    await flushPromises();

    await chat.sendMessage();
    await flushStreamSend();

    const requestBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(requestBody).toBeDefined();
    expect(requestBody).not.toHaveProperty('selected_skill_names');
    expect(requestBody?.message).toBe('@报表工具 统计今天调用情况');
  });

  it('does not send retired batch messages payload for normal chat sends', async () => {
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
          sseEvent({ event: 'message', delta: 'single answer' }),
        );
        await options.onMessage(sseEvent({ event: 'done', total_tokens: 12 }));
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = 'single question';

    await chat.sendMessage();
    await flushPromises();

    expect(chat.chatMessages.value).toHaveLength(2);
    expect(chat.chatMessages.value[0]?.role).toBe('user');
    expect(chat.chatMessages.value[1]?.role).toBe('assistant');

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.content).toBe('single answer');

    const requestBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(requestBody).not.toHaveProperty('messages');
    expect(Object.keys(requestBody ?? {}).toSorted()).toEqual([
      'consented_actions',
      'conversation_id',
      'message',
    ]);
  });

  it('sends chat with only explicit chat request fields', async () => {
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
    chat.inputMessage.value = '请帮我查看智能体配置';

    await chat.sendMessage();
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1000);
    await flushPromises();

    expect(apiMocks.sendChatStreamApi).toHaveBeenCalledOnce();
    const requestBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(Object.keys(requestBody ?? {}).toSorted()).toEqual([
      'consented_actions',
      'conversation_id',
      'message',
    ]);
    expect(requestBody).not.toHaveProperty('messages');
    expect(socketStoreMocks.connect).not.toHaveBeenCalled();
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
          toolName: 'query_records',
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
        tool_name: 'query_records',
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
        content: '需要继续查询资料',
        pendingConfirmation: {
          toolName: 'query_records',
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
        tool_name: 'query_records',
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
        tool_name: 'query_records',
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
        tool_name: 'query_records',
      },
    ]);
    expect(aiPanelStoreMocks.restoreInteractionUpdates).not.toHaveBeenCalled();
  });
});
