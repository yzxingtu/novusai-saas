import type { AIInteractionUpdate } from '#/store/shared/ai-panel';

// @vitest-environment happy-dom
import { flushPromises } from '@vue/test-utils';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { shouldDisplayConversationInHistory, useAIChat } from '../use-ai-chat';
import {
  baseChatOptions,
  buildAgent,
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
          buildAssistantMessage('并发 Session 超限：当前 3 个（限制：3 个）。', {
            created_at: '2026-04-07T12:00:01Z',
            metadata: {
              error: true,
              error_debug_message: '并发 Session 超限：当前 3 个（限制：3 个）。',
              error_message: '并发 Session 超限：当前 3 个（限制：3 个）。',
              error_only: true,
              error_trace_id: 'trace-stream-1044',
              error_type: 'stream_execution_error',
            },
          }),
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

  it('keeps active and recent empty conversations visible in history list', async () => {
    vi.setSystemTime(new Date('2026-04-07T12:00:00Z'));
    apiMocks.getGlobalConversationsApi.mockResolvedValueOnce(
      buildConversationList([
        buildConversation({
          created_at: '2026-04-06T12:00:00Z',
          id: 1001,
          status: 'closed',
          title: 'normal conversation',
        }),
        buildConversation({
          created_at: '2026-03-01T12:00:00Z',
          id: 1002,
          message_count: 0,
          status: 'active',
          title: 'active empty shell',
        }),
        buildConversation({
          created_at: '2026-04-07T11:30:00Z',
          id: 1003,
          message_count: 0,
          status: 'closed',
          title: 'recent empty shell',
        }),
        buildConversation({
          created_at: '2026-03-01T12:00:00Z',
          id: 1004,
          message_count: 0,
          status: 'closed',
          title: 'stale empty shell',
        }),
      ]),
    );

    const chat = createChat();
    await chat.loadAgents();
    await chat.loadConversations();
    await flushPromises();

    expect(chat.conversations.value.map((item) => item.id)).toEqual([
      1001, 1002, 1003,
    ]);
  });

  it('keeps the currently active empty conversation visible', async () => {
    vi.setSystemTime(new Date('2026-04-07T12:00:00Z'));
    apiMocks.getGlobalConversationsApi.mockResolvedValueOnce(
      buildConversationList([
        buildConversation({
          created_at: '2026-03-01T12:00:00Z',
          id: 2001,
          message_count: 0,
          status: 'closed',
          title: 'opened empty conversation',
        }),
      ]),
    );

    const chat = createChat();
    chat.activeConversationId.value = 2001;
    await chat.loadConversations();
    await flushPromises();

    expect(chat.conversations.value.map((item) => item.id)).toEqual([2001]);
  });

  it('reloads conversation history when the stream ends without a done event', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail(
        [
          buildUserMessage('hello again'),
          buildAssistantMessage('partial from backend', {
            metadata: {
              completion_reason: 'interrupted',
              interrupted: true,
              partial: true,
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
          onEnd: () => Promise<void>;
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          sseEvent({ event: 'conversation', conversation_id: 42 }),
        );
        await options.onMessage(
          sseEvent({ event: 'message', delta: 'partial from stream' }),
        );
        await options.onEnd();
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    chat.inputMessage.value = 'hello again';

    await chat.sendMessage({ routeSource: 'unexpected-end-test' });
    await flushPromises();

    expect(apiMocks.getChatConversationMessagesApi).toHaveBeenCalledTimes(1);
    expect(chat.chatMessages.value).toHaveLength(2);
    expect(chat.chatMessages.value[1]?.content).toBe('partial from backend');
    expect(chat.chatMessages.value[1]?.partial).toBe(true);
    expect(chat.chatMessages.value[1]?.interrupted).toBe(true);
  });

  it('keeps the anchored conversation binding after transient local state loss', async () => {
    apiMocks.getChatAgentsApi.mockResolvedValue(
      buildAgentList([
        buildAgent({ description: 'Primary agent' }),
        buildAgent({
          description: 'Drifted agent',
          id: 2,
          model_name: 'gpt-test-2',
          name: 'Agent Two',
        }),
      ]),
    );
    apiMocks.getChatConversationMessagesApi
      .mockResolvedValueOnce(
        buildConversationDetail([
          buildUserMessage('hello'),
          buildAssistantMessage('hi there'),
        ]),
      )
      .mockResolvedValue(
        buildConversationDetail([
          buildUserMessage('hello'),
          buildAssistantMessage('hi there'),
          buildUserMessage('follow-up after interruption'),
        ]),
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
          sseEvent({ event: 'done', conversation_id: 42, total_tokens: 8 }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    chat.activeConversationId.value = null;
    chat.selectedAgentId.value = 2;
    chat.inputMessage.value = 'follow-up after interruption';

    const sendPromise = chat.sendMessage({
      routeSource: 'anchor-recovery-test',
    });
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1000);
    await sendPromise;
    await flushPromises();

    const lastCall = apiMocks.sendChatStreamApi.mock.calls.at(-1);
    const requestBody = lastCall?.[2] as Record<string, unknown> | undefined;
    expect(lastCall?.[1]).toBe(1);
    expect(requestBody?.conversation_id).toBe(42);
    expect(chat.activeConversationId.value).toBe(42);
    expect(chat.selectedAgentId.value).toBe(1);
  });

  it('still forks to a new conversation when an explicit agent override is provided', async () => {
    apiMocks.getChatAgentsApi.mockResolvedValue(
      buildAgentList([
        buildAgent({ description: 'Primary agent' }),
        buildAgent({
          description: 'Secondary agent',
          id: 2,
          model_name: 'gpt-test-2',
          name: 'Agent Two',
        }),
      ]),
    );
    apiMocks.getChatConversationMessagesApi
      .mockResolvedValueOnce(
        buildConversationDetail([
          buildUserMessage('hello'),
          buildAssistantMessage('hi there'),
        ]),
      )
      .mockResolvedValue(
        buildConversationDetail(
          [
            buildUserMessage('hello'),
            buildAssistantMessage('hi there'),
            buildUserMessage('start a fresh branch'),
          ],
          { agent_id: 2 },
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
          sseEvent({ event: 'conversation', conversation_id: 84 }),
        );
        await options.onMessage(
          sseEvent({ event: 'done', conversation_id: 84, total_tokens: 6 }),
        );
      },
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    chat.inputMessage.value = 'start a fresh branch';

    const sendPromise = chat.sendMessage({
      agentId: 2,
      routeSource: 'explicit-agent-switch-test',
    });
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1000);
    await sendPromise;
    await flushPromises();

    const lastCall = apiMocks.sendChatStreamApi.mock.calls.at(-1);
    const requestBody = lastCall?.[2] as Record<string, unknown> | undefined;
    expect(lastCall?.[1]).toBe(2);
    expect(requestBody?.conversation_id).toBeNull();
    expect(chat.activeConversationId.value).toBe(84);
  });

  it('restores interactionMode from backend conversation detail when available', async () => {
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

  it('keeps trusted_auto requested mode when backend detail reports an effective confirm downgrade', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([buildUserMessage('hello')], {
        interaction_mode_effective: 'confirm',
        interaction_mode_requested: 'trusted_auto',
        last_run_summary: {
          downgrade_reason: 'missing_runtime_trust_policy',
        },
      }),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    expect(chat.interactionMode.value).toBe('trusted_auto');
    expect(chat.interactionModeEffective.value).toBe('confirm');
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
        { interaction_mode_effective: 'confirm' },
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
        { interaction_mode_effective: 'confirm' },
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

  it('restores confirm interactionMode from backend conversation detail', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue(
      buildConversationDetail([buildUserMessage('hello')], {
        interaction_mode_effective: 'confirm',
      }),
    );

    const chat = createChat();

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    expect(chat.interactionMode.value).toBe('confirm');
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
    expect(autoApproveBody?.interaction_mode).toBe('trusted_auto');
  });

  it('preserves trusted_auto on consent approval resend after a confirm downgrade', async () => {
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
          interaction_mode_effective: 'confirm',
          interaction_mode_requested: 'trusted_auto',
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
              interaction_mode_effective: 'confirm',
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
    expect(chat.interactionModeEffective.value).toBe('confirm');
    expect(chat.chatMessages.value.at(-1)?.pendingConsent?.toolName).toBe(
      'get_current_weather',
    );

    chat.confirmConsent(chat.chatMessages.value.length - 1);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1000);
    await flushPromises();

    const consentBody = apiMocks.sendChatStreamApi.mock.calls.at(-1)?.[2] as
      | Record<string, unknown>
      | undefined;
    expect(apiMocks.sendChatStreamApi).toHaveBeenCalledTimes(2);
    expect(consentBody?.interaction_mode).toBe('trusted_auto');
    expect(consentBody?.interaction_updates).toEqual([
      {
        kind: 'pending_consent',
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
    expect(assistantMessage?.toolCalls?.[0]?.summaryPayload).toEqual({
      filters: ['today'],
      group_by: ['t.name'],
      metrics: ['COUNT(acl.id)'],
      tables: ['ai_call_logs', 'tenants'],
      tool_kind: 'query_records',
    });
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
    expect(assistantMessage?.toolCalls?.[0]).toMatchObject({
      displayName: 'common.globalAiChat.toolNativeSearch',
      name: 'native_web_search',
      status: 'running',
    });

    releaseDone();
    await sendPromise;
    await flushPromises();

    expect(assistantMessage?.toolCalls?.[0]).toMatchObject({
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
    expect(assistantMessage?.pendingConfirmation?.toolName).toBe('query_records');
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
    expect(consentBody?.interaction_mode).toBe('trusted_auto');
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
        action: 'create_record',
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
        action: 'create_record',
        kind: 'pending_confirmation',
        rejected: false,
        tool_name: 'ui_open_surface',
      },
    ]);
    expect(aiPanelStoreMocks.restoreInteractionUpdates).not.toHaveBeenCalled();
  });
});
