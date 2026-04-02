// @vitest-environment happy-dom
import { flushPromises } from '@vue/test-utils';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAIChat } from '../use-ai-chat';

const apiMocks = vi.hoisted(() => ({
  getChatAgentKBBindingsApi: vi.fn(),
  getChatAgentsApi: vi.fn(),
  getChatConversationMemoryApi: vi.fn(),
  getChatConversationMessagesApi: vi.fn(),
  getGlobalConversationsApi: vi.fn(),
  sendChatStreamApi: vi.fn(),
}));

const aiPanelStoreMocks = vi.hoisted(() => ({
  consumeInteractionUpdates: vi.fn(() => []),
  restoreInteractionUpdates: vi.fn(),
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
  sendChatStreamApi: apiMocks.sendChatStreamApi,
  updateChatConversationTitleApi: vi.fn(),
  uploadChatFileApi: vi.fn(),
}));

vi.mock('#/components/business/ai-slide-panel/page-key-utils', () => ({
  normalizePageKey: (value: string) => value,
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
    emit: vi.fn(),
    isConnected: false,
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

    apiMocks.getChatAgentsApi.mockResolvedValue({
      items: [
        {
          avatar: null,
          description: 'Test agent',
          id: 1,
          input_variables: [],
          model_capabilities: {
            max_image_count: 4,
            max_image_size_mb: 10,
            supports_vision: false,
          },
          model_name: 'gpt-test',
          name: 'Agent One',
          status: 'published',
          tenant_id: 1,
        },
      ],
      total: 1,
    });

    apiMocks.getGlobalConversationsApi.mockResolvedValue({
      items: [
        {
          agent_id: 1,
          agent_name: 'Agent One',
          created_at: '2024-01-01T00:00:00Z',
          id: 42,
          message_count: 2,
          status: 'active',
          title: 'Recovered',
        },
      ],
      total: 1,
    });
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
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 42 })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'message', delta: 'partial answer' })}\n`,
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

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

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

  it('reloads conversation history when the stream ends without a done event', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue({
      agent_id: 1,
      interaction_mode_effective: 'trusted_auto',
      message_list: [
        {
          content: 'hello again',
          created_at: '2024-01-01T00:00:00Z',
          role: 'user',
        },
        {
          agent_id: 1,
          agent_name: 'Agent One',
          content: 'partial from backend',
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
          onEnd: () => Promise<void>;
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 42 })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'message', delta: 'partial from stream' })}\n`,
        );
        await options.onEnd();
      },
    );

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

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
    apiMocks.getChatAgentsApi.mockResolvedValue({
      items: [
        {
          avatar: null,
          description: 'Primary agent',
          id: 1,
          input_variables: [],
          model_capabilities: {
            max_image_count: 4,
            max_image_size_mb: 10,
            supports_vision: false,
          },
          model_name: 'gpt-test',
          name: 'Agent One',
          status: 'published',
          tenant_id: 1,
        },
        {
          avatar: null,
          description: 'Drifted agent',
          id: 2,
          input_variables: [],
          model_capabilities: {
            max_image_count: 4,
            max_image_size_mb: 10,
            supports_vision: false,
          },
          model_name: 'gpt-test-2',
          name: 'Agent Two',
          status: 'published',
          tenant_id: 1,
        },
      ],
      total: 2,
    });
    apiMocks.getChatConversationMessagesApi.mockResolvedValue({
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
          content: 'hi there',
          created_at: '2024-01-01T00:00:01Z',
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
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'done', conversation_id: 42, total_tokens: 8 })}\n`,
        );
      },
    );

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    chat.activeConversationId.value = null;
    chat.selectedAgentId.value = 2;
    chat.inputMessage.value = 'follow-up after interruption';

    await chat.sendMessage({ routeSource: 'anchor-recovery-test' });
    await flushPromises();

    const lastCall = apiMocks.sendChatStreamApi.mock.calls.at(-1);
    const requestBody = lastCall?.[2] as Record<string, unknown> | undefined;
    expect(lastCall?.[1]).toBe(1);
    expect(requestBody?.conversation_id).toBe(42);
    expect(chat.activeConversationId.value).toBe(42);
    expect(chat.selectedAgentId.value).toBe(1);
  });

  it('still forks to a new conversation when an explicit agent override is provided', async () => {
    apiMocks.getChatAgentsApi.mockResolvedValue({
      items: [
        {
          avatar: null,
          description: 'Primary agent',
          id: 1,
          input_variables: [],
          model_capabilities: {
            max_image_count: 4,
            max_image_size_mb: 10,
            supports_vision: false,
          },
          model_name: 'gpt-test',
          name: 'Agent One',
          status: 'published',
          tenant_id: 1,
        },
        {
          avatar: null,
          description: 'Secondary agent',
          id: 2,
          input_variables: [],
          model_capabilities: {
            max_image_count: 4,
            max_image_size_mb: 10,
            supports_vision: false,
          },
          model_name: 'gpt-test-2',
          name: 'Agent Two',
          status: 'published',
          tenant_id: 1,
        },
      ],
      total: 2,
    });
    apiMocks.getChatConversationMessagesApi.mockResolvedValue({
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
          content: 'hi there',
          created_at: '2024-01-01T00:00:01Z',
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
          onMessage: (chunk: string) => Promise<void>;
        },
      ) => {
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 84 })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'done', conversation_id: 84, total_tokens: 6 })}\n`,
        );
      },
    );

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    chat.inputMessage.value = 'start a fresh branch';

    await chat.sendMessage({
      agentId: 2,
      routeSource: 'explicit-agent-switch-test',
    });
    await flushPromises();

    const lastCall = apiMocks.sendChatStreamApi.mock.calls.at(-1);
    const requestBody = lastCall?.[2] as Record<string, unknown> | undefined;
    expect(lastCall?.[1]).toBe(2);
    expect(requestBody?.conversation_id).toBeNull();
    expect(chat.activeConversationId.value).toBe(84);
  });

  it('restores interactionMode from backend conversation detail when available', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue({
      agent_id: 1,
      interaction_mode_effective: 'trusted_auto',
      message_list: [
        {
          content: 'hello',
          created_at: '2024-01-01T00:00:00Z',
          role: 'user',
        },
      ],
    });

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    expect(chat.interactionMode.value).toBe('trusted_auto');
  });

  it('restores confirm interactionMode from backend conversation detail', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue({
      agent_id: 1,
      interaction_mode_effective: 'confirm',
      message_list: [
        {
          content: 'hello',
          created_at: '2024-01-01T00:00:00Z',
          role: 'user',
        },
      ],
    });

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

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
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 42 })}\n`,
        );
        if (streamCallCount === 1) {
          await options.onMessage(
            `data: ${JSON.stringify({
              event: 'tool_consent_request',
              name: 'web_search',
              arguments: { query: 'latest news' },
            })}\n`,
          );
        }
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'done', conversation_id: 42, total_tokens: 5 })}\n`,
        );
      },
    );

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

    await chat.loadAgents();
    chat.interactionMode.value = 'trusted_auto';
    chat.inputMessage.value = '查一下';

    const sendPromise = chat.sendMessage();
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
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 42 })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({
            arguments: { question: '统计今天调用情况' },
            event: 'tool_start',
            id: 'tc_data_query',
            name: 'data_query',
          })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({
            duration_ms: 120,
            event: 'tool_call',
            name: 'data_query',
            success: true,
            summary: '按今天范围统计调用并按租户分组',
            summary_payload: {
              filters: ['today'],
              group_by: ['t.name'],
              metrics: ['COUNT(acl.id)'],
              tables: ['ai_call_logs', 'tenants'],
              tool_kind: 'data_query',
            },
          })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'done', total_tokens: 18 })}\n`,
        );
      },
    );

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

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
      tool_kind: 'data_query',
    });
  });

  it('restores persisted rich tool contract and interaction state from conversation history', async () => {
    apiMocks.getChatConversationMessagesApi.mockResolvedValue({
      agent_id: 1,
      message_list: [
        {
          content: '统计今天调用情况',
          created_at: '2024-01-01T00:00:00Z',
          role: 'user',
        },
        {
          agent_id: 1,
          agent_name: 'Agent One',
          content: '',
          created_at: '2024-01-01T00:00:01Z',
          metadata: {
            action_buttons: [
              {
                label: '查看明细',
                style: 'primary',
                value: '查看今天调用明细',
              },
            ],
            pending_consent: {
              arguments: { question: '统计今天调用情况' },
              skill_name: '平台数据管理',
              tool_name: 'data_query',
            },
          },
          role: 'assistant',
          tool_calls: [
            {
              display_name: '平台数据管理',
              duration_ms: 120,
              function: {
                arguments: '{"question":"统计今天调用情况"}',
                name: 'data_query',
              },
              id: 'tc_history_1',
              pending_confirmation: {
                action: 'query',
                preview: { sql: 'SELECT 1' },
                table: 'ai_call_logs',
              },
              result_link: '/admin/ai/chat',
              skill_name: '平台数据管理',
              success: true,
              summary: '按今天范围统计调用',
              summary_payload: {
                filters: ['today'],
                tables: ['ai_call_logs'],
                tool_kind: 'data_query',
              },
            },
          ],
        },
        {
          content: '{"success": true}',
          created_at: '2024-01-01T00:00:02Z',
          metadata: {
            tool_display_name: '平台数据管理',
            tool_success: true,
            tool_summary: '按今天范围统计调用',
            tool_summary_payload: {
              filters: ['today'],
              tables: ['ai_call_logs'],
              tool_kind: 'data_query',
            },
          },
          role: 'tool',
          tool_call_id: 'tc_history_1',
          tool_name: 'data_query',
        },
      ],
    });

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

    await chat.loadAgents();
    await chat.loadConversationMessages(42);
    await flushPromises();

    const assistantMessage = chat.chatMessages.value.find(
      (msg) => msg.role === 'assistant',
    );
    expect(assistantMessage?.toolCalls?.[0]?.displayName).toBe('平台数据管理');
    expect(assistantMessage?.toolCalls?.[0]?.summaryPayload).toEqual({
      filters: ['today'],
      tables: ['ai_call_logs'],
      tool_kind: 'data_query',
    });
    expect(assistantMessage?.pendingConfirmation?.table).toBe('ai_call_logs');
    expect(assistantMessage?.pendingConsent?.toolName).toBe('data_query');
    expect(assistantMessage?.actionButtons?.[0]?.label).toBe('查看明细');
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
          `data: ${JSON.stringify({
            dropped_knowledge_base_ids: [20],
            effective_knowledge_base_ids: [10],
            event: 'knowledge_base_feedback',
          })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 42 })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'done', total_tokens: 18 })}\n`,
        );
      },
    );

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

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

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

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
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 42 })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'message', delta: 'debounced answer' })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'done', total_tokens: 12 })}\n`,
        );
      },
    );

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

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
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 42 })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'done', total_tokens: 18 })}\n`,
        );
      },
    );

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

    await chat.loadAgents();
    chat.chatMessages.value = [
      {
        clientKey: 'assistant-confirm-message',
        role: 'assistant',
        content: '需要处理',
        pendingConfirmation: {
          action: 'query',
          table: 'ai_call_logs',
        },
      },
      {
        clientKey: 'assistant-consent-message',
        role: 'assistant',
        content: '需要授权',
        pendingConsent: {
          toolName: 'data_query',
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
        tool_name: 'data_query',
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
          `data: ${JSON.stringify({ event: 'conversation', conversation_id: 42 })}\n`,
        );
        await options.onMessage(
          `data: ${JSON.stringify({ event: 'done', conversation_id: 42, total_tokens: 5 })}\n`,
        );
      },
    );

    aiPanelStoreMocks.consumeInteractionUpdates.mockReturnValue([
      {
        action: 'create_record',
        kind: 'pending_confirmation',
        rejected: false,
        tool_name: 'pageop_create_record',
      },
    ]);

    const chat = useAIChat({
      apiPrefix: '/tenant',
      uploadUrl: '/tenant/attachments',
    });

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
        tool_name: 'pageop_create_record',
      },
    ]);
    expect(aiPanelStoreMocks.restoreInteractionUpdates).not.toHaveBeenCalled();
  });
});
