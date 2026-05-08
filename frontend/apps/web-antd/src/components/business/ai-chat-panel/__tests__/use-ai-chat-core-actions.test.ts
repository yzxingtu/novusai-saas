/**
 * Test type: behavioral
 * Verifies: assistant regeneration keeps the active conversation for the latest turn while historical regeneration still forks.
 * Mock strategy: action dependencies are fakes; conversation binding state is real Vue refs.
 */
import type { ChatMessage } from '../types';

import { ref } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import { createAIChatCoreActions } from '../use-ai-chat-core-actions';

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
  },
}));

vi.mock('#/api/shared/ai-chat', () => ({
  getChatAgentsApi: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/ai-consent', () => ({
  clearConsents: vi.fn(),
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: null | string | undefined) => value ?? '',
}));

function buildHarness(messages: ChatMessage[]) {
  const activeConversationId = ref<null | number>(2365);
  const activeConversationAgentId = ref<null | number>(59);
  const chatMessages = ref<ChatMessage[]>(messages);
  const clearConversationAnchor = vi.fn();
  const inputMessage = ref('');
  const sendMessage = vi.fn(async () => true);

  const actions = createAIChatCoreActions({
    abortActiveStream: vi.fn(),
    activeConversationAgentId,
    activeConversationId,
    agents: ref([]),
    agentsLoading: ref(false),
    bumpConversationsRequestSeq: vi.fn(),
    bumpMessagesRequestSeq: vi.fn(),
    chatMessages,
    clearConversationAnchor,
    clearMentionDraft: vi.fn(),
    clearPendingAttachments: vi.fn(),
    inputMessage,
    interactionMode: ref('trusted_auto'),
    interactionModeEffective: ref('trusted_auto'),
    options: { apiPrefix: '/tenant' },
    pendingAttachments: ref([]),
    resetConversationState: vi.fn(),
    resetMemoryState: vi.fn(),
    resetPendingMessages: vi.fn(),
    resetVariables: vi.fn(),
    selectedAgentId: ref(59),
    sending: ref(false),
    sendMessage,
    streaming: ref(false),
  });

  return {
    activeConversationAgentId,
    activeConversationId,
    actions,
    chatMessages,
    clearConversationAnchor,
    inputMessage,
    sendMessage,
  };
}

describe('useAIChat core actions', () => {
  it('keeps conversation 2365 when regenerating the latest failed assistant turn', () => {
    const harness = buildHarness([
      {
        clientKey: 'user-2365-9',
        content: '凤凰县最近七天天气',
        role: 'user',
      },
      {
        clientKey: 'assistant-2365-12',
        content: '无法连接到 AI 供应商',
        requestFailedRetry: true,
        role: 'assistant',
      },
    ]);

    harness.actions.regenerateMessage(1);

    expect(harness.activeConversationId.value).toBe(2365);
    expect(harness.activeConversationAgentId.value).toBe(59);
    expect(harness.clearConversationAnchor).not.toHaveBeenCalled();
    expect(harness.chatMessages.value.map((item) => item.content)).toEqual([
      '凤凰县最近七天天气',
    ]);
    expect(harness.inputMessage.value).toBe('凤凰县最近七天天气');
    expect(harness.sendMessage).toHaveBeenCalledWith({ silent: true });
  });

  it('forks when regenerating a historical assistant turn', () => {
    const harness = buildHarness([
      {
        clientKey: 'user-2365-1',
        content: '使用 实时天气查询',
        role: 'user',
      },
      {
        clientKey: 'assistant-2365-4',
        content: '北京当前天气',
        role: 'assistant',
      },
      {
        clientKey: 'user-2365-5',
        content: '最近七天怎么样？',
        role: 'user',
      },
      {
        clientKey: 'assistant-2365-8',
        content: '北京七天天气',
        role: 'assistant',
      },
    ]);

    harness.actions.regenerateMessage(1);

    expect(harness.activeConversationId.value).toBeNull();
    expect(harness.activeConversationAgentId.value).toBe(59);
    expect(harness.clearConversationAnchor).toHaveBeenCalledOnce();
    expect(harness.chatMessages.value.map((item) => item.content)).toEqual([
      '使用 实时天气查询',
    ]);
    expect(harness.inputMessage.value).toBe('使用 实时天气查询');
    expect(harness.sendMessage).toHaveBeenCalledWith({ silent: true });
  });
});
