// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
/**
 * Test type: behavioral
 * Verifies: the slide-panel message viewport preserves turnFlow-first normalization and switches to transcript-first rendering in non-compact mode.
 * Mock strategy: child message items/icons are stubbed, while viewport normalization and prop wiring run real.
 */
import type { ChatMessage } from '#/types/ai-chat';

import { mount } from '@vue/test-utils';
import { computed, defineComponent, ref } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatMessageViewport from '../AIChatMessageViewport.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

describe('aiChatMessageViewport', () => {
  it('forwards assistant action button payload as messageIndex + value', async () => {
    const wrapper = mount(AIChatMessageViewport, {
      props: {
        apiPrefix: '/tenant',
        chatMessages: [
          {
            clientKey: 'assistant-action',
            content: '请选择',
            role: 'assistant',
          } satisfies ChatMessage,
        ],
        getPendingOpsForMessage: () => [],
        getRichTextDraftState: () => null,
        isAgentSwitch: () => false,
      },
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemStub',
            emits: ['actionClick'],
            template:
              '<button data-testid="action-btn" @click="$emit(\'actionClick\', 7, \'查看明细\')" />',
          }),
        },
      },
    });

    await wrapper.get('[data-testid="action-btn"]').trigger('click');

    expect(wrapper.emitted('actionClick')?.[0]).toEqual([7, '查看明细']);
  });

  it('passes shared message-item props including turn-flow payload', () => {
    const richTextState = {
      canAppendToEnd: true,
      canCopy: true,
      canInsertAfterSelection: true,
      canReplaceSelection: true,
      canUndo: false,
    };
    const pendingOps = [{ invokeId: 'op-1' }];
    const wrapper = mount(AIChatMessageViewport, {
      props: {
        apiPrefix: '/tenant',
        chatMessages: [
          {
            clientKey: 'assistant-turn-flow',
            content: '阶段摘要',
            role: 'assistant',
            turnFlow: {
              answer_card: null,
              completion_reason: 'stop',
              error_surface: null,
              evidence: [],
              interrupted: false,
              timeline: [
                {
                  id: 'stage-thinking',
                  status: 'completed',
                  title: '思考',
                  type: 'thinking',
                },
              ],
            },
          } as ChatMessage,
        ],
        getPendingOpsForMessage: () => pendingOps as never[],
        getRichTextDraftState: () => richTextState as never,
        isAgentSwitch: () => true,
      },
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemStub',
            props: {
              compact: { type: Boolean, required: false },
              index: { type: Number, required: true },
              msg: { type: Object, required: true },
              pendingOps: { type: Array, required: false },
              richTextState: { type: Object, required: false },
              showAgentSwitch: { type: Boolean, required: false },
            },
            template:
              '<div data-testid="message-item-props" :data-compact="String(compact)" :data-switch="String(showAgentSwitch)" :data-stage-id="msg?.turnFlow?.timeline?.[0]?.id" :data-index="String(index)" :data-pending-ops="String((pendingOps || []).length)" :data-has-rich-text-state="String(!!richTextState)" :data-streaming="String(!!msg?.streaming)" />',
          }),
        },
      },
    });

    const propsSnapshot = wrapper.get('[data-testid="message-item-props"]');
    expect(propsSnapshot.attributes('data-compact')).toBe('true');
    expect(propsSnapshot.attributes('data-switch')).toBe('true');
    expect(propsSnapshot.attributes('data-stage-id')).toBe('stage-thinking');
    expect(propsSnapshot.attributes('data-index')).toBe('0');
    expect(propsSnapshot.attributes('data-pending-ops')).toBe('1');
    expect(propsSnapshot.attributes('data-has-rich-text-state')).toBe('true');
    expect(propsSnapshot.attributes('data-streaming')).toBe('false');
  });

  it('renders expanded transcript items without compact message chrome', () => {
    const wrapper = mount(AIChatMessageViewport, {
      props: {
        apiPrefix: '/tenant',
        chatMessages: [
          {
            clientKey: 'assistant-expanded',
            content: 'expanded transcript',
            role: 'assistant',
          } satisfies ChatMessage,
        ],
        compact: false,
        getPendingOpsForMessage: () => [],
        getRichTextDraftState: () => null,
        isAgentSwitch: () => false,
      },
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemExpandedStub',
            props: {
              compact: { type: Boolean, required: false },
            },
            template:
              '<div data-testid="expanded-message-item" :data-compact="String(compact)" />',
          }),
        },
      },
    });

    expect(
      wrapper.get('[data-testid="expanded-message-item"]').attributes(
        'data-compact',
      ),
    ).toBe('false');
    expect(wrapper.html()).toContain('max-w-[42rem]');
  });

  it('keeps canonical turnFlow payload intact while stripping legacy display fields', () => {
    const ChatMessageItemProbe = defineComponent({
      name: 'ChatMessageItemProbe',
      props: {
        msg: { type: Object, required: true },
      },
      setup(props) {
        const rawMessage = computed(
          () => props.msg as Record<string, unknown>,
        );
        const hasThinking = computed(() =>
          Boolean(rawMessage.value.thinkingContent),
        );
        const hasToolCalls = computed(() => {
          const toolCalls = rawMessage.value.toolCalls;
          return Array.isArray(toolCalls) && toolCalls.length > 0;
        });
        const hasRag = computed(() => {
          const ragSources = rawMessage.value.ragSources;
          return Array.isArray(ragSources) && ragSources.length > 0;
        });
        const hasOptimizing = computed(() =>
          Boolean(rawMessage.value.optimizingTools),
        );
        const stageTypes = computed(() =>
          (
            (props.msg as ChatMessage).turnFlow?.timeline?.map(
              (stage) => stage.type,
            ) ?? []
          ).join('|'),
        );
        const stageStatuses = computed(() =>
          (
            (props.msg as ChatMessage).turnFlow?.timeline?.map(
              (stage) => stage.status,
            ) ?? []
          ).join('|'),
        );
        const stageIds = computed(() =>
          (
            (props.msg as ChatMessage).turnFlow?.timeline?.map(
              (stage) => stage.id,
            ) ?? []
          ).join('|'),
        );
        return {
          hasOptimizing,
          hasRag,
          hasThinking,
          hasToolCalls,
          stageIds,
          stageStatuses,
          stageTypes,
        };
      },
      template:
        '<div data-testid="message-item-probe" :data-stage-ids="stageIds" :data-stage-types="stageTypes" :data-stage-statuses="stageStatuses" :data-has-thinking="String(hasThinking)" :data-has-tool-calls="String(hasToolCalls)" :data-has-rag="String(hasRag)" :data-has-optimizing="String(hasOptimizing)" :data-streaming="String(!!msg?.streaming)" />',
    });

    const wrapper = mount(AIChatMessageViewport, {
      props: {
        apiPrefix: '/tenant',
        chatMessages: [
          {
            clientKey: 'assistant-turn-flow-normalized',
            completionReason: 'provider_failure_after_partial_progress',
            content: '安全占位答复',
            optimizingTools: { selected: 0, total: 15 },
            ragSources: [
              { doc_id: 1, doc_name: '知识库', score: 0.8, snippet: 'snippet' },
            ],
            role: 'assistant',
            thinkingContent: 'legacy-thinking',
            toolCalls: [{ name: 'web_search', status: 'error' }],
            turnFlow: {
              completion_reason: 'provider_failure_after_partial_progress',
              final_stage_status: 'error',
              timeline: [
                {
                  id: 'legacy-thinking',
                  status: 'completed',
                  type: 'thinking',
                },
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
                  id: 'stage-answer',
                  status: 'completed',
                  type: 'answer_assembly',
                },
                {
                  id: 'legacy-completed',
                  status: 'completed',
                  type: 'completed',
                },
              ],
            },
          } as unknown as ChatMessage,
        ],
        getPendingOpsForMessage: () => [],
        getRichTextDraftState: () => null,
        isAgentSwitch: () => false,
      },
      global: {
        stubs: {
          ChatMessageItem: ChatMessageItemProbe,
        },
      },
    });

    const probe = wrapper.get('[data-testid="message-item-probe"]');
    expect(probe.attributes('data-stage-ids')).toBe(
      'legacy-thinking|stage-thinking|stage-tool-selection|stage-answer|legacy-completed',
    );
    expect(probe.attributes('data-stage-types')).toBe(
      'thinking|thinking|tool_selection|answer_assembly|completed',
    );
    expect(probe.attributes('data-stage-statuses')).toBe(
      'completed|completed|skipped|completed|completed',
    );
    expect(probe.attributes('data-has-thinking')).toBe('false');
    expect(probe.attributes('data-has-tool-calls')).toBe('false');
    expect(probe.attributes('data-has-rag')).toBe('false');
    expect(probe.attributes('data-has-optimizing')).toBe('false');
    expect(probe.attributes('data-streaming')).toBe('false');
  });

  it('adapts raw turn_flow alias payloads without reprojecting legacy display fields', () => {
    const wrapper = mount(AIChatMessageViewport, {
      props: {
        apiPrefix: '/tenant',
        chatMessages: [
          {
            clientKey: 'assistant-turn-flow-alias',
            content: 'answer',
            metadata: {
              turn_flow: {
                evidence: [],
                timeline: [
                  {
                    id: 'stage-from-alias',
                    status: 'completed',
                    type: 'thinking',
                  },
                ],
              },
            },
            optimizingTools: { selected: 0, total: 12 },
            ragSources: [
              { doc_id: 7, doc_name: 'legacy doc', score: 0.7, snippet: 's' },
            ],
            role: 'assistant',
            thinkingContent: 'legacy-thinking',
            toolCalls: [{ name: 'legacy_tool', status: 'success' }],
          } as unknown as ChatMessage,
        ],
        getPendingOpsForMessage: () => [],
        getRichTextDraftState: () => null,
        isAgentSwitch: () => false,
      },
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemAliasProbe',
            props: {
              msg: { type: Object, required: true },
            },
            setup(props) {
              const rawMessage = computed(
                () => props.msg as Record<string, unknown>,
              );
              const hasThinking = computed(() =>
                Boolean(rawMessage.value.thinkingContent),
              );
              const hasToolCalls = computed(() => {
                const toolCalls = rawMessage.value.toolCalls;
                return Array.isArray(toolCalls) && toolCalls.length > 0;
              });
              const hasRag = computed(() => {
                const ragSources = rawMessage.value.ragSources;
                return Array.isArray(ragSources) && ragSources.length > 0;
              });
              const hasOptimizing = computed(() =>
                Boolean(rawMessage.value.optimizingTools),
              );
              return {
                hasOptimizing,
                hasRag,
                hasThinking,
                hasToolCalls,
              };
            },
            template:
              '<div data-testid="alias-probe" :data-stage-id="msg?.turnFlow?.timeline?.[0]?.id || \'\'" :data-has-thinking="String(hasThinking)" :data-has-tool-calls="String(hasToolCalls)" :data-has-rag="String(hasRag)" :data-has-optimizing="String(hasOptimizing)" :data-streaming="String(!!msg?.streaming)" />',
          }),
        },
      },
    });

    const probe = wrapper.get('[data-testid="alias-probe"]');
    expect(probe.attributes('data-stage-id')).toBe('stage-from-alias');
    expect(probe.attributes('data-has-thinking')).toBe('false');
    expect(probe.attributes('data-has-tool-calls')).toBe('false');
    expect(probe.attributes('data-has-rag')).toBe('false');
    expect(probe.attributes('data-has-optimizing')).toBe('false');
    expect(probe.attributes('data-streaming')).toBe('false');
  });

  it('keeps message component identity stable when history prepends entries without client keys', async () => {
    const keySeed = ref(0);
    const MessageIdentityProbe = defineComponent({
      name: 'MessageIdentityProbe',
      props: {
        msg: { type: Object, required: true },
      },
      setup() {
        keySeed.value += 1;
        const instanceId = `instance-${keySeed.value}`;
        return { instanceId };
      },
      template:
        '<div data-testid="identity-probe" :data-instance-id="instanceId" :data-content="msg?.content || \'\'" :data-streaming="String(!!msg?.streaming)" />',
    });

    const initialMessages = [
      {
        content: 'first answer',
        created_at: '2026-04-16T10:01:00Z',
        role: 'assistant',
        sequence: 1,
      },
      {
        content: 'second answer',
        created_at: '2026-04-16T10:02:00Z',
        role: 'assistant',
        sequence: 2,
      },
    ] as unknown as ChatMessage[];

    const wrapper = mount(AIChatMessageViewport, {
      props: {
        apiPrefix: '/tenant',
        chatMessages: initialMessages,
        getPendingOpsForMessage: () => [],
        getRichTextDraftState: () => null,
        isAgentSwitch: () => false,
      },
      global: {
        stubs: {
          ChatMessageItem: MessageIdentityProbe,
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

    await wrapper.setProps({
      chatMessages: [
        {
          content: 'prepended answer',
          created_at: '2026-04-16T10:00:00Z',
          role: 'assistant',
          sequence: 0,
        },
        ...initialMessages,
      ] as unknown as ChatMessage[],
    });

    const afterPrepend = mapByContent();

    expect(afterPrepend.get('first answer')).toBe(
      beforePrepend.get('first answer'),
    );
    expect(afterPrepend.get('second answer')).toBe(
      beforePrepend.get('second answer'),
    );

    const firstHistoryItem = wrapper
      .findAll('[data-testid="identity-probe"]')
      .find((item) => item.attributes('data-content') === 'first answer');
    expect(firstHistoryItem?.attributes('data-streaming')).toBe('false');
  });

  it('keeps live streaming messages marked as live while panel streaming is active', () => {
    const wrapper = mount(AIChatMessageViewport, {
      props: {
        apiPrefix: '/tenant',
        chatMessages: [
          {
            clientKey: 'assistant-live-message',
            content: 'live output',
            role: 'assistant',
            streaming: true,
          } as ChatMessage,
        ],
        getPendingOpsForMessage: () => [],
        getRichTextDraftState: () => null,
        isAgentSwitch: () => false,
        streaming: true,
      },
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemLiveProbe',
            props: {
              msg: { type: Object, required: true },
            },
            template:
              '<div data-testid="live-probe" :data-streaming="String(!!msg?.streaming)" />',
          }),
        },
      },
    });

    expect(
      wrapper.get('[data-testid="live-probe"]').attributes('data-streaming'),
    ).toBe('true');
  });
});
