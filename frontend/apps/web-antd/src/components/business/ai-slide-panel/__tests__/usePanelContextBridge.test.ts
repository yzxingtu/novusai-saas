// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { usePanelContextBridge } from '../use-panel-context-bridge';

vi.mock('#/locales', () => ({
  i18n: {
    global: {
      locale: {
        value: 'zh-CN',
      },
    },
  },
  $t: (key: string) => key,
}));

vi.mock('ant-design-vue', () => ({
  message: {
    warning: vi.fn(),
  },
}));

async function flushBridge() {
  await flushPromises();
  await flushPromises();
}

describe('usePanelContextBridge', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('consumes queued agent context even when the AI panel is already visible', async () => {
    const agents = ref([{ id: 1 }, { id: 2 }]);
    const activeConversationId = ref<null | number>(88);
    const allAgentsVariables = ref<Record<number, Record<string, string>>>({});
    const chatMessages = ref([{ role: 'assistant' }]);
    const forceRerouteNextTurn = ref(false);
    const inputMessage = ref('');
    const manualNewConversationAgentId = ref<null | number>(null);
    const pendingConversationId = ref<null | number>(null);
    const pendingMessage = ref<null | string | undefined>(null);
    const selectedAgentId = ref<null | number>(1);
    const showHistory = ref(true);
    const showMemoryPanel = ref(true);
    const storePendingAgentId = ref<number | undefined>(2);
    const storePendingConversationId = ref<null | number>(null);
    const storePendingMessage = ref<null | string>('命令栏继续发送');
    const visible = ref(true);

    const applyVariables = vi.fn();
    const clearResolvedToolActions = vi.fn();
    const consumePendingAgentId = vi.fn(() => {
      const nextId = storePendingAgentId.value;
      storePendingAgentId.value = undefined;
      return nextId ?? null;
    });
    const ensureAgentVarsLoaded = vi.fn();
    const handleSendMessage = vi.fn(async () => true);
    const loadAgents = vi.fn(async () => {});
    const loadConversationMessages = vi.fn(async () => {});
    const loadConversations = vi.fn(async () => {});
    const onConversationRestored = vi.fn();
    const onMessageSent = vi.fn();
    const sendMessage = vi.fn(async () => {});
    const startNewConversation = vi.fn((forceReset?: boolean) => {
      if (forceReset) {
        activeConversationId.value = null;
        chatMessages.value = [];
      }
    });

    const wrapper = mount(
      defineComponent({
        setup() {
          usePanelContextBridge({
            agents,
            activeConversationId,
            allAgentsVariables,
            applyVariables,
            chatMessages,
            clearMentionedAgent: vi.fn(),
            clearResolvedToolActions,
            consumePendingAgentId,
            ensureAgentVarsLoaded,
            forceRerouteNextTurn,
            handleSendMessage,
            inputMessage,
            loadAgents,
            loadConversationMessages,
            loadConversations,
            manualNewConversationAgentId,
            onConversationRestored,
            onMessageSent,
            pendingConversationId,
            pendingMessage,
            selectedAgentId,
            sendMessage,
            showHistory,
            showMemoryPanel,
            startNewConversation,
            storePendingAgentId,
            storePendingConversationId,
            storePendingMessage,
            visible,
          });
          return () => null;
        },
      }),
    );

    await flushBridge();

    expect(clearResolvedToolActions).toHaveBeenCalled();
    expect(consumePendingAgentId).toHaveBeenCalledTimes(1);
    expect(loadAgents).toHaveBeenCalledWith(2);
    expect(startNewConversation).toHaveBeenCalledWith(true);
    expect(selectedAgentId.value).toBe(2);
    expect(manualNewConversationAgentId.value).toBe(2);
    expect(showHistory.value).toBe(false);
    expect(showMemoryPanel.value).toBe(false);
    expect(inputMessage.value).toBe('命令栏继续发送');
    expect(handleSendMessage).toHaveBeenCalledTimes(1);
    expect(storePendingAgentId.value).toBeUndefined();

    wrapper.unmount();
  });

  it('only marks queued conversation restore as consumed after the target conversation is active', async () => {
    const agents = ref([{ id: 1 }]);
    const activeConversationId = ref<null | number>(88);
    const allAgentsVariables = ref<Record<number, Record<string, string>>>({});
    const chatMessages = ref([{ role: 'assistant' }]);
    const forceRerouteNextTurn = ref(false);
    const inputMessage = ref('');
    const manualNewConversationAgentId = ref<null | number>(null);
    const pendingConversationId = ref<null | number>(123);
    const pendingMessage = ref<null | string | undefined>(null);
    const selectedAgentId = ref<null | number>(1);
    const showHistory = ref(true);
    const showMemoryPanel = ref(true);
    const storePendingAgentId = ref<number | undefined>(undefined);
    const storePendingConversationId = ref<null | number>(null);
    const storePendingMessage = ref<null | string>(null);
    const visible = ref(true);

    const loadConversationMessages = vi.fn(async () => {});
    const onConversationRestored = vi.fn();

    const wrapper = mount(
      defineComponent({
        setup() {
          usePanelContextBridge({
            agents,
            activeConversationId,
            allAgentsVariables,
            applyVariables: vi.fn(),
            chatMessages,
            clearMentionedAgent: vi.fn(),
            clearResolvedToolActions: vi.fn(),
            consumePendingAgentId: vi.fn(() => null),
            ensureAgentVarsLoaded: vi.fn(),
            forceRerouteNextTurn,
            handleSendMessage: vi.fn(async () => false),
            inputMessage,
            loadAgents: vi.fn(async () => {}),
            loadConversationMessages,
            loadConversations: vi.fn(async () => {}),
            manualNewConversationAgentId,
            onConversationRestored,
            onMessageSent: vi.fn(),
            pendingConversationId,
            pendingMessage,
            selectedAgentId,
            sendMessage: vi.fn(async () => {}),
            showHistory,
            showMemoryPanel,
            startNewConversation: vi.fn(),
            storePendingAgentId,
            storePendingConversationId,
            storePendingMessage,
            visible,
          });
          return () => null;
        },
      }),
    );

    await flushBridge();

    expect(loadConversationMessages).toHaveBeenCalledWith(123);
    expect(onConversationRestored).not.toHaveBeenCalled();

    wrapper.unmount();
  });
});
