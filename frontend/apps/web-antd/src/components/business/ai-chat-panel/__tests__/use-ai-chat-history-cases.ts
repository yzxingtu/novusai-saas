import type { useAIChat } from '../use-ai-chat';

import { flushPromises } from '@vue/test-utils';

import { expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';

import {
  buildAgent,
  buildAgentList,
  buildAssistantMessage,
  buildConversation,
  buildConversationDetail,
  buildConversationList,
  buildUserMessage,
  sseEvent,
} from './fixtures/ai-chat-fixtures';

type ChatHarness = ReturnType<typeof useAIChat>;

interface UseAIChatHistoryApiMocks {
  getChatAgentsApi: Mock;
  getChatConversationMessagesApi: Mock;
  getGlobalConversationsApi: Mock;
  sendChatStreamApi: Mock;
}

interface RegisterUseAIChatHistoryCasesOptions {
  apiMocks: UseAIChatHistoryApiMocks;
  createChat: () => ChatHarness;
}

export function registerUseAIChatHistoryCases(
  options: RegisterUseAIChatHistoryCasesOptions,
) {
  const { apiMocks, createChat } = options;

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
}
