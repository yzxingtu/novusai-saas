// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { computed, defineComponent, nextTick, ref } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import UserAIChatWorkspaceMessages from '../UserAIChatWorkspaceMessages.vue';

const workspaceContext = {
  askSuggested: vi.fn(),
  isAgentSwitch: vi.fn(() => false),
  onCopyMessage: vi.fn(),
  openImagePreview: vi.fn(),
  page: {
    apiPrefix: '/api/user',
    chat: {
      agents: [],
      chatMessages: ref([
        {
          clientKey: 'assistant-1',
          content: 'final answer',
          role: 'assistant',
          thinkingContent: 'legacy thinking',
          toolCalls: [{ name: 'legacy_tool', status: 'success' }],
          turn_flow: {
            final_stage_status: 'error',
            evidence: [],
            timeline: [
              {
                id: 'stage-thinking',
                status: 'completed',
                type: 'thinking',
              },
              {
                id: 'stage-tool-selection',
                status: 'skipped',
                type: 'tool_selection',
              },
              {
                id: 'stage-tool-execution',
                status: 'completed',
                type: 'tool_execution',
              },
              {
                id: 'stage-answer',
                status: 'error',
                type: 'answer_assembly',
              },
              {
                id: 'stage-terminal',
                status: 'error',
                type: 'failed',
              },
            ],
          },
        },
      ]),
      clickActionButton: vi.fn(),
      confirmAction: vi.fn(),
      confirmConsent: vi.fn(),
      editAndResend: vi.fn(),
      handleMessagesScroll: vi.fn(),
      messagesContainer: { value: null },
      regenerateMessage: vi.fn(),
      rejectAction: vi.fn(),
      rejectConsent: vi.fn(),
      retryLastMessage: vi.fn(),
      scrollToBottom: vi.fn(),
      scrollToTop: vi.fn(),
      selectedAgent: ref(null),
      sending: ref(false),
      showScrollToBottom: ref(false),
      showScrollToTop: ref(false),
      streaming: ref(false),
    },
    effectiveSuggestedQuestions: ref([]),
    effectiveWelcomeMessage: ref(''),
    showWorkspaceHero: ref(false),
  },
};

const resetWorkspaceMessages = () => {
  workspaceContext.page.chat.chatMessages.value = [
    {
      clientKey: 'assistant-1',
      content: 'final answer',
      role: 'assistant',
      thinkingContent: 'legacy thinking',
      toolCalls: [{ name: 'legacy_tool', status: 'success' }],
      turn_flow: {
        final_stage_status: 'error',
        evidence: [],
        timeline: [
          {
            id: 'stage-thinking',
            status: 'completed',
            type: 'thinking',
          },
          {
            id: 'stage-tool-selection',
            status: 'skipped',
            type: 'tool_selection',
          },
          {
            id: 'stage-tool-execution',
            status: 'completed',
            type: 'tool_execution',
          },
          {
            id: 'stage-answer',
            status: 'error',
            type: 'answer_assembly',
          },
          {
            id: 'stage-terminal',
            status: 'error',
            type: 'failed',
          },
        ],
      },
    },
  ];
};

vi.mock('../user-ai-chat-workspace-context', () => ({
  useUserAIChatWorkspaceContext: () => workspaceContext,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('#/components/business/ai-chat-panel/ChatMessageItem.vue', () => ({
  default: defineComponent({
    name: 'ChatMessageItemStub',
    props: {
      msg: { type: Object, required: true },
    },
    setup(props) {
      const hasThinking = computed(() =>
        Boolean((props.msg as Record<string, unknown>).thinkingContent),
      );
      const hasToolCalls = computed(() => {
        const toolCalls = (props.msg as Record<string, unknown>).toolCalls;
        return Array.isArray(toolCalls) && toolCalls.length > 0;
      });
      return {
        hasThinking,
        hasToolCalls,
      };
    },
    template:
      '<div data-testid="chat-message-item-stub" :data-has-thinking="String(hasThinking)" :data-has-tool-calls="String(hasToolCalls)" :data-stage-id="msg?.turnFlow?.timeline?.[0]?.id || \'\'" :data-stage-order="Array.isArray(msg?.turnFlow?.timeline) ? msg.turnFlow.timeline.map((stage) => stage?.type).join(\',\') : \'\'" :data-terminal-status="Array.isArray(msg?.turnFlow?.timeline) && msg.turnFlow.timeline.length > 0 ? msg.turnFlow.timeline[msg.turnFlow.timeline.length - 1]?.status : \'\'" :data-streaming="String(!!msg?.streaming)" />',
  }),
}));

describe('userAIChatWorkspaceMessages turn-flow rendering', () => {
  beforeEach(() => {
    resetWorkspaceMessages();
  });

  it('injects turnFlow-first message model without adding external timeline/evidence wrappers', () => {
    const wrapper = mount(UserAIChatWorkspaceMessages, {
      global: {
        stubs: {
          Transition: false,
        },
      },
    });

    const messageItem = wrapper.get('[data-testid="chat-message-item-stub"]');
    expect(messageItem.attributes('data-has-thinking')).toBe('false');
    expect(messageItem.attributes('data-has-tool-calls')).toBe('false');
    expect(messageItem.attributes('data-stage-id')).toBe('turn-thinking');
    expect(messageItem.attributes('data-stage-order')).toBe(
      'thinking,tool_execution',
    );
    expect(messageItem.attributes('data-terminal-status')).toBe('completed');
    expect(messageItem.attributes('data-streaming')).toBe('false');
  });

  it('keeps message identity stable when history prepends entries without client keys', async () => {
    workspaceContext.page.chat.chatMessages.value = [
      {
        content: 'first historical answer',
        created_at: '2026-04-16T10:01:00Z',
        role: 'assistant',
        sequence: 1,
      },
      {
        content: 'second historical answer',
        created_at: '2026-04-16T10:02:00Z',
        role: 'assistant',
        sequence: 2,
      },
    ] as unknown as typeof workspaceContext.page.chat.chatMessages.value;

    const mountCounter = ref(0);
    const MessageIdentityProbe = defineComponent({
      name: 'UserMessageIdentityProbe',
      props: {
        msg: { type: Object, required: true },
      },
      setup() {
        mountCounter.value += 1;
        const instanceId = `instance-${mountCounter.value}`;
        return { instanceId };
      },
      template:
        '<div data-testid="identity-probe" :data-instance-id="instanceId" :data-content="msg?.content || \'\'" :data-streaming="String(!!msg?.streaming)" />',
    });

    const wrapper = mount(UserAIChatWorkspaceMessages, {
      global: {
        stubs: {
          ChatMessageItem: MessageIdentityProbe,
          Transition: false,
        },
      },
    });

    const mapByContent = () =>
      new Map(
        wrapper
          .findAll('[data-testid="identity-probe"]')
          .map((item) => [
            item.attributes('data-content'),
            item.attributes('data-instance-id'),
          ]),
      );

    const beforePrepend = mapByContent();

    workspaceContext.page.chat.chatMessages.value = [
      {
        content: 'prepended answer',
        created_at: '2026-04-16T10:00:00Z',
        role: 'assistant',
        sequence: 0,
      },
      ...workspaceContext.page.chat.chatMessages.value,
    ] as unknown as typeof workspaceContext.page.chat.chatMessages.value;

    await nextTick();

    const afterPrepend = mapByContent();

    expect(afterPrepend.get('first historical answer')).toBe(
      beforePrepend.get('first historical answer'),
    );
    expect(afterPrepend.get('second historical answer')).toBe(
      beforePrepend.get('second historical answer'),
    );

    const firstHistoryItem = wrapper
      .findAll('[data-testid="identity-probe"]')
      .find(
        (item) => item.attributes('data-content') === 'first historical answer',
      );
    expect(firstHistoryItem?.attributes('data-streaming')).toBe('false');
  });
});
