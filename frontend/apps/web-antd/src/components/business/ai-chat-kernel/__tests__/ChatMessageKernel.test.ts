// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: the shared assistant kernel keeps transcript-adjacent process/result chrome compact,
// delays auto-collapse just long enough for completion to read smoothly, and uses the split layout in expanded mode.
import type { ChatMessage } from '#/types/ai-chat';

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import ChatMessageKernel from '../ChatMessageKernel.vue';
import { buildTurnFlowState } from '../TurnFlowState';

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
  turnFlow?: Record<string, unknown>;
};

function createAssistantMessage(
  overrides: ChatMessageOverrides = {},
): ChatMessage {
  return {
    clientKey: 'assistant-kernel-message',
    content: '',
    role: 'assistant',
    ...overrides,
  } as ChatMessage;
}

function mountKernel(msg: ChatMessage, compact = true) {
  return mount(ChatMessageKernel, {
    props: {
      compact,
      msg,
      state: buildTurnFlowState(msg),
    },
    global: {
      stubs: {
        ActionConsentGate: defineComponent({
          name: 'ActionConsentGateStub',
          template: '<div data-testid="stub-action-consent-gate"></div>',
        }),
        EvidenceCard: defineComponent({
          name: 'EvidenceCardStub',
          template: '<div data-testid="stub-evidence-card"></div>',
        }),
        TurnTimeline: defineComponent({
          name: 'TurnTimelineStub',
          template: '<div data-testid="stub-turn-timeline"></div>',
        }),
      },
    },
  });
}

describe('chatMessageKernel', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps the combined kernel expanded for 220ms after streaming settles before auto-collapsing', async () => {
    vi.useFakeTimers();
    const liveMessage = createAssistantMessage({
      streaming: true,
      turnFlow: {
        evidence: [],
        timeline: [
          {
            detailLines: ['正在根据上下文整理答案结构'],
            id: 'stage-answer-live',
            status: 'running',
            summary: '正在组织答案',
            type: 'answer_assembly',
          },
        ],
      },
    });
    const wrapper = mountKernel(liveMessage);

    await wrapper.vm.$nextTick();

    expect(
      wrapper
        .get('[data-testid="chat-message-kernel-body"]')
        .attributes('data-layout'),
    ).toBe('stacked');

    const settledMessage = createAssistantMessage({
      content: '最终答案',
      streaming: false,
      turnFlow: {
        answerCard: {
          summary: '已整理出最终结果',
        },
        evidence: [],
        timeline: [
          {
            detailLines: ['已完成答案结构整理'],
            id: 'stage-answer-live',
            status: 'completed',
            summary: '已完成答案整理',
            type: 'answer_assembly',
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
      wrapper
        .get('[data-testid="chat-message-kernel-overview-toggle"]')
        .attributes('aria-expanded'),
    ).toBe('true');
    expect(
      wrapper.find('[data-testid="chat-message-kernel-body"]').exists(),
    ).toBe(true);

    vi.advanceTimersByTime(219);
    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="chat-message-kernel-body"]').exists(),
    ).toBe(true);

    vi.advanceTimersByTime(1);
    await wrapper.vm.$nextTick();

    expect(
      wrapper
        .get('[data-testid="chat-message-kernel-overview-toggle"]')
        .attributes('aria-expanded'),
    ).toBe('false');
    expect(
      wrapper.find('[data-testid="chat-message-kernel-body"]').exists(),
    ).toBe(false);
  });

  it('uses the split kernel layout when default mode shows both result digest and process timeline', async () => {
    const message = createAssistantMessage({
      content: '最终答案',
      turnFlow: {
        answerCard: {
          summary: '结果整理',
        },
        evidence: [],
        timeline: [
          {
            id: 'stage-retrieval-completed',
            metrics: {
              source_count: 2,
            },
            status: 'completed',
            summary: '已完成证据整理',
            type: 'retrieval',
          },
        ],
      },
    });
    const wrapper = mountKernel(message, false);

    await wrapper.vm.$nextTick();
    await wrapper
      .get('[data-testid="chat-message-kernel-overview-toggle"]')
      .trigger('click');
    await wrapper.vm.$nextTick();

    const body = wrapper.get('[data-testid="chat-message-kernel-body"]');
    expect(body.attributes('data-layout')).toBe('split');
    expect(
      wrapper.find('[data-testid="chat-message-kernel-digest-panel"]').exists(),
    ).toBe(true);
    expect(
      wrapper
        .find('[data-testid="chat-message-kernel-timeline-panel"]')
        .exists(),
    ).toBe(true);
  });

  it('uses the safe answer digest instead of generic English retry text for 2326-style partial research turns', async () => {
    const safePartial =
      '我找到了候选来源，但交叉验证不足，暂时不生成新闻结论。你可以稍后重试或换一个更具体的关键词。';
    const genericRetry =
      'The assistant could not finish this turn. Please retry.';
    const wrapper = mountKernel(
      createAssistantMessage({
        completionReason: 'insufficient_cross_checked_sources',
        content: safePartial,
        turnOutcome: 'partial',
        turnFlow: {
          answerCard: {
            confidenceLabel: 'low',
            sections: [
              {
                content: safePartial,
                id: 'final_answer',
                title: 'Answer',
              },
            ],
            summary: safePartial,
          },
          completionReason: 'insufficient_cross_checked_sources',
          errorSurface: {
            errorType: 'untrusted_final_output_source',
            failureKind: 'insufficient_cross_checked_sources',
            message: genericRetry,
          },
          evidence: [],
          failureKind: 'insufficient_cross_checked_sources',
          finalStageStatus: 'error',
          timeline: [
            {
              id: 'answer_assembly',
              status: 'error',
              summary: '答复生成失败',
              type: 'answer_assembly',
            },
            {
              id: 'terminal',
              status: 'error',
              summary: 'insufficient_cross_checked_sources',
              type: 'failed',
            },
          ],
          turnOutcome: 'partial',
        },
      }),
    );

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain(safePartial);
    expect(wrapper.text()).not.toContain(genericRetry);
  });
});
