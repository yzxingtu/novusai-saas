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

vi.mock('#/utils/ai-consent', () => ({
  addConsent: vi.fn(),
  getConsentedActions: vi.fn(() => []),
}));

vi.mock('#/utils/error-helpers', () => ({
  showRequestError: vi.fn(),
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: string | null | undefined) => value ?? '',
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
});
