// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: the transcript-first process timeline uses a single process toggle,
// auto-collapses on completion, hides thinking bodies, and suppresses noop stages.
import type { ChatMessage } from '#/types/ai-chat';

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { buildTurnFlowState } from '../TurnFlowState';
import TurnTimeline from '../TurnTimeline.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

type ChatMessageOverrides = Omit<Partial<ChatMessage>, 'turnFlow'> & {
  turnFlow?: Omit<NonNullable<ChatMessage['turnFlow']>, 'evidence'> & {
    evidence?: NonNullable<ChatMessage['turnFlow']>['evidence'];
  };
};

function createAssistantMessage(
  overrides: ChatMessageOverrides = {},
): ChatMessage {
  const turnFlow = overrides.turnFlow
    ? {
        evidence: [],
        ...overrides.turnFlow,
      }
    : undefined;
  return {
    clientKey: 'assistant-turn-timeline',
    content: '',
    role: 'assistant',
    ...overrides,
    ...(turnFlow ? { turnFlow } : {}),
  };
}

function mountTimeline(msg: ChatMessage) {
  return mount(TurnTimeline, {
    props: {
      msg,
      state: buildTurnFlowState(msg),
    },
    global: {
      stubs: {
        ChatMessageThinkingBlock: defineComponent({
          name: 'ChatMessageThinkingBlockStub',
          props: {
            embedded: {
              default: false,
              type: Boolean,
            },
          },
          template:
            '<div data-testid="stub-thinking-block" :data-embedded="String(embedded)"></div>',
        }),
        ChatMessageToolCalls: defineComponent({
          name: 'ChatMessageToolCallsStub',
          props: {
            embedded: {
              default: false,
              type: Boolean,
            },
          },
          template:
            '<div data-testid="stub-tool-calls" :data-embedded="String(embedded)"></div>',
        }),
      },
    },
  });
}

describe('turnTimeline', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('hides terminal completed-only process sections that carry no user-facing body content', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              id: 'stage-completed',
              status: 'completed',
              summary: '本轮已完成',
              type: 'completed',
            },
          ],
        },
      }),
    );

    expect(
      wrapper.find('[data-testid="chat-message-kernel-timeline"]').exists(),
    ).toBe(false);
  });

  it('keeps only live running stages expanded by default', () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              detailLines: ['正在准备执行计划'],
              id: 'stage-running',
              status: 'running',
              summary: '进行中',
              type: 'tool_execution',
            },
            {
              detailLines: ['工具调用失败：超时'],
              id: 'stage-error',
              status: 'error',
              summary: '执行失败',
              type: 'failed',
            },
          ],
        },
      }),
    );

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');
    expect(wrapper.get('[data-testid="turn-process-toggle"]').attributes()).toMatchObject({
      'aria-expanded': 'true',
    });
    expect(
      wrapper.findAll('[data-testid^="turn-stage-"]').length,
    ).toBeGreaterThan(0);
  });

  it('keeps historical error and interrupted stages collapsed by default', () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: false,
        turnFlow: {
          timeline: [
            {
              detailLines: ['历史错误详情'],
              id: 'stage-error-history',
              status: 'error',
              summary: '执行失败',
              type: 'failed',
            },
            {
              detailLines: ['历史中断详情'],
              id: 'stage-interrupted-history',
              status: 'interrupted',
              summary: '用户中断',
              type: 'answer_assembly',
            },
          ],
        },
      }),
    );

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 0fr');
    expect(wrapper.get('[data-testid="turn-process-toggle"]').attributes()).toMatchObject({
      'aria-expanded': 'false',
    });
  });

  it('normalizes canonical metric aliases for stage summaries', () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        turnFlow: {
          evidence: [
            {
              id: 'source-1',
              kind: 'knowledge_base',
              snippet: '已核验资料片段',
              sourceRef: 'source-1',
              title: '真实来源',
            },
          ],
          timeline: [
            {
              id: 'stage-tool-selection-alias',
              metrics: {
                all_tools_count: 15,
                candidate_tools_count: 0,
              },
              status: 'skipped',
              type: 'tool_selection',
            },
            {
              id: 'stage-retrieval-alias',
              metrics: {
                source_count: 3,
              },
              sourceRefs: ['source-1'],
              status: 'completed',
              type: 'retrieval',
            },
          ],
        },
      }),
    );

    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnRetrievalSummary',
    );
    expect(wrapper.text()).not.toContain('common.globalAiChat.optimizingTools');
  });

  it('does not render raw runtime context diagnostics in expanded retrieval details', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        requestFailedRetry: true,
        turnFlow: {
          answerCard: {
            sections: [{ content: 'Connection error.', title: 'Answer' }],
            sourceChipIds: ['evidence_1', 'evidence_2', 'evidence_3'],
            summary: 'Connection error.',
          },
          completionReason: 'provider_unavailable',
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
          failureKind: 'provider_unavailable',
          finalStageStatus: 'error',
          timeline: [
            {
              id: 'retrieval',
              metrics: { source_count: 3 },
              sourceRefs: ['evidence_1', 'evidence_2', 'evidence_3'],
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
          turnOutcome: 'partial',
        },
      }),
    );

    await wrapper.get('[data-testid="turn-process-toggle"]').trigger('click');

    expect(wrapper.text()).not.toContain('Retrieved 3 sources');
    expect(wrapper.text()).not.toContain('skill_resolver');
    expect(wrapper.text()).not.toContain('long_term_memory');
    expect(wrapper.text()).not.toContain('gpt-5.5');
    expect(wrapper.text()).not.toContain(
      'common.globalAiChat.turnRetrievalSummary',
    );
  });

  it('localizes numeric backend English stage summaries before rendering them', () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        turnFlow: {
          timeline: [
            {
              id: 'stage-tool-selection-english-summary',
              metrics: {
                selected: 3,
                total: 13,
              },
              status: 'completed',
              summary: 'Selected 3 of 13 tools',
              type: 'tool_selection',
            },
            {
              id: 'stage-tool-execution-english-summary',
              metrics: {
                total: 1,
              },
              status: 'completed',
              summary: 'Executed 1 tool calls',
              type: 'tool_execution',
            },
          ],
        },
      }),
    );

    expect(wrapper.text()).toContain('common.globalAiChat.optimizingTools');
    expect(wrapper.text()).toContain('common.globalAiChat.toolGroupSummary');
    expect(wrapper.text()).not.toContain('Selected 3 of 13 tools');
    expect(wrapper.text()).not.toContain('Executed 1 tool calls');
  });

  it('provides safe non-empty running copy with provider hints for canonical stages', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              id: 'stage-tool-execution-provider',
              metrics: {
                provider: 'native:provider_1:gpt-5.4',
              },
              status: 'running',
              type: 'tool_execution',
            },
          ],
        },
      }),
    );

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('common.globalAiChat.toolExecutionRoute');
    expect(wrapper.text()).toContain('native:provider_1:gpt-5.4');
    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');
  });

  it('shows safe summary fallback for canonical thinking stages without raw detail lines', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              id: 'stage-thinking-running',
              status: 'running',
              summary: '正在分析用户问题并规划下一步',
              type: 'thinking',
            },
          ],
        },
      }),
    );

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('正在分析用户问题并规划下一步');
    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');
    expect(wrapper.find('[data-testid="turn-stage-body-0"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="stub-thinking-block"]').exists()).toBe(
      false,
    );
  });

  it('normalizes generic backend English stage titles into localized stage copy', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              id: 'stage-thinking-generic-title',
              status: 'running',
              summary: 'Thinking',
              title: 'Thinking',
              type: 'thinking',
            },
          ],
        },
      }),
    );

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('common.globalAiChat.turnStageType.thinking');
    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnStageSummary.thinking',
    );
    expect(wrapper.text()).not.toContain('Thinking');
  });

  it('filters punctuation-only stage summaries and falls back to localized process copy', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              id: 'stage-thinking-punctuation-only',
              status: 'running',
              summary: '!',
              type: 'thinking',
            },
          ],
        },
      }),
    );

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnStageSummary.thinking',
    );
    expect(wrapper.text()).not.toContain('!');
  });

  it('does not render timeline thinking detail bodies even when backend sends detail lines', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              detailLines: ['先分析当前用户问题，再整理下一步动作'],
              id: 'stage-thinking-embedded',
              status: 'running',
              summary: '正在思考',
              type: 'thinking',
            },
          ],
        },
      }),
    );

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('正在思考');
    expect(wrapper.text()).not.toContain('先分析当前用户问题，再整理下一步动作');
    expect(wrapper.find('[data-testid="stub-thinking-block"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="turn-stage-body-0"]').exists()).toBe(
      false,
    );
  });

  it('renders multiple thinking stages as compact rows without thinking renderers', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              detailLines: ['先梳理用户约束'],
              id: 'stage-thinking-earlier',
              status: 'completed',
              summary: '第一步',
              type: 'thinking',
            },
            {
              detailLines: ['再整理答案结构'],
              id: 'stage-thinking-latest',
              status: 'running',
              summary: '第二步',
              type: 'thinking',
            },
          ],
        },
      }),
    );

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('第一步');
    expect(wrapper.text()).toContain('第二步');
    expect(wrapper.text()).not.toContain('先梳理用户约束');
    expect(wrapper.text()).not.toContain('再整理答案结构');
    expect(wrapper.findAll('[data-testid="stub-thinking-block"]')).toHaveLength(
      0,
    );
    expect(wrapper.findAll('[data-testid^="turn-stage-body-"]')).toHaveLength(0);
  });

  it('shows tool call fallback content for canonical tool execution stages without detail lines', async () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          evidence: [
            {
              id: 'tool-running',
              kind: 'tool',
              status: 'running',
              toolName: 'query_records',
            },
          ],
          timeline: [
            {
              id: 'stage-tool-running',
              status: 'running',
              summary: '正在调用工具并等待结果返回',
              type: 'tool_execution',
            },
          ],
        },
      }),
    );

    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-testid="stub-tool-calls"]').exists()).toBe(true);
    expect(wrapper.get('[data-testid="stub-tool-calls"]').attributes()).toMatchObject(
      {
        'data-embedded': 'true',
      },
    );
    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');
  });

  it('preserves the 220ms delayed collapse when an expandable stage transitions from running to skipped', async () => {
    vi.useFakeTimers();
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: true,
        turnFlow: {
          timeline: [
            {
              detailLines: ['正在筛选工具'],
              id: 'stage-tool-selection',
              status: 'running',
              summary: '筛选中',
              type: 'tool_selection',
            },
          ],
        },
      }),
    );

    await wrapper.vm.$nextTick();

    await wrapper.setProps({
      msg: createAssistantMessage({
        streaming: false,
        turnFlow: {
          timeline: [
            {
              detailLines: ['15 个工具中筛选了 0 个'],
              id: 'stage-tool-selection',
              status: 'skipped',
              summary: '筛选结束',
              type: 'tool_selection',
            },
          ],
        },
      }),
      state: buildTurnFlowState(
        createAssistantMessage({
          streaming: false,
          turnFlow: {
            timeline: [
              {
                detailLines: ['15 个工具中筛选了 0 个'],
                id: 'stage-tool-selection',
                status: 'skipped',
                summary: '筛选结束',
                type: 'tool_selection',
              },
            ],
          },
        }),
      ),
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="chat-message-kernel-timeline"]').exists(),
    ).toBe(false);
  });

  it('collapses every settled expandable stage after the live turn stops streaming', async () => {
    vi.useFakeTimers();
    const liveMessage = createAssistantMessage({
      streaming: true,
      turnFlow: {
        timeline: [
          {
            detailLines: ['正在整合工具结果'],
            id: 'stage-answer',
            status: 'running',
            summary: '正在组织答案',
            type: 'answer_assembly',
          },
          {
            detailLines: ['已定位到 2 条相关来源'],
            id: 'stage-retrieval',
            status: 'completed',
            summary: '已完成证据整理',
            type: 'retrieval',
          },
        ],
      },
    });
    const wrapper = mountTimeline(liveMessage);

    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    const settledMessage = createAssistantMessage({
      streaming: false,
      turnFlow: {
        timeline: [
          {
            detailLines: ['已完成答案结构整理'],
            id: 'stage-answer',
            status: 'completed',
            summary: '已完成答案整理',
            type: 'answer_assembly',
          },
          {
            detailLines: ['已定位到 2 条相关来源'],
            id: 'stage-retrieval',
            status: 'completed',
            summary: '已完成证据整理',
            type: 'retrieval',
          },
        ],
      },
    });
    await wrapper.setProps({
      msg: settledMessage,
      state: buildTurnFlowState(settledMessage),
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    vi.advanceTimersByTime(220);
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 0fr');
  });

  it('keeps the whole process panel expanded while streaming and auto-collapses it after completion', async () => {
    vi.useFakeTimers();
    const liveMessage = createAssistantMessage({
      streaming: true,
      turnFlow: {
        timeline: [
          {
            detailLines: ['正在分析并准备下一步操作'],
            id: 'stage-thinking-live',
            status: 'running',
            summary: '正在思考',
            type: 'thinking',
          },
        ],
      },
    });
    const wrapper = mountTimeline(liveMessage);

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    const settledMessage = createAssistantMessage({
      streaming: false,
      turnFlow: {
        timeline: [
          {
            detailLines: ['已完成当前回合的思路整理'],
            id: 'stage-thinking-live',
            status: 'completed',
            summary: '已完成思考',
            type: 'thinking',
          },
          {
            id: 'stage-terminal',
            status: 'completed',
            summary: 'completed',
            type: 'completed',
          },
        ],
      },
    });
    await wrapper.setProps({
      msg: settledMessage,
      state: buildTurnFlowState(settledMessage),
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    vi.advanceTimersByTime(220);
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 0fr');
  });

  it('hides noop skipped tool and retrieval stages while preserving meaningful live stages', () => {
    const wrapper = mountTimeline(
      createAssistantMessage({
        streaming: false,
        turnFlow: {
          timeline: [
            {
              id: 'stage-tool-selection-skipped',
              metrics: { selected: 0, total: 3 },
              status: 'skipped',
              summary: 'Selected 0 of 3 tools',
              type: 'tool_selection',
            },
            {
              id: 'stage-tool-execution-skipped',
              metrics: { total: 0 },
              status: 'skipped',
              summary: 'No tools executed',
              type: 'tool_execution',
            },
            {
              id: 'stage-retrieval-skipped',
              metrics: { total: 0 },
              status: 'skipped',
              summary: 'No evidence retrieved',
              type: 'retrieval',
            },
            {
              detailLines: ['已完成最终答复整理'],
              id: 'stage-answer',
              status: 'completed',
              summary: '已完成答案整理',
              type: 'answer_assembly',
            },
          ],
        },
      }),
    );

    expect(wrapper.text()).not.toContain('Selected 0 of 3 tools');
    expect(wrapper.text()).not.toContain('No tools executed');
    expect(wrapper.text()).not.toContain('No evidence retrieved');
    expect(wrapper.text()).toContain('已完成答案整理');
  });
});
