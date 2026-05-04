// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: assistant final-answer body rendering keeps canonical answer cards separate from residual search/process fragments.
// Mock strategy: Markdown/i18n/icon rendering is stubbed; prepareMessageContent and content-boundary logic run real.
import type { ChatMessage } from '../types';

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import ChatMessageContentBlock from '../ChatMessageContentBlock.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-icon-stub" />',
  }),
}));

vi.mock('#/components/business/markdown-render', () => ({
  MarkdownRender: defineComponent({
    name: 'MarkdownRenderStub',
    props: {
      content: {
        required: true,
        type: String,
      },
      streaming: {
        default: false,
        type: Boolean,
      },
    },
    template: '<div data-testid="markdown-render-content">{{ content }}</div>',
  }),
}));

function createLongMessage(
  clientKey: string,
  overrides: Partial<ChatMessage> = {},
): ChatMessage {
  return {
    clientKey,
    content: '长消息内容'.repeat(500),
    role: 'assistant',
    streaming: false,
    ...overrides,
  };
}

function createLeaderboardResearchMessage(
  content: string,
  overrides: Partial<ChatMessage> = {},
): ChatMessage {
  return {
    clientKey: 'leaderboard-research-message',
    content,
    role: 'assistant',
    streaming: false,
    turnFlow: {
      answerCard: {
        sections: [
          {
            body: '按 Artificial Analysis 的 intelligence、price、speed 等维度比较 GPT-5.5、Gemini 3 Pro 与 Claude Opus 4.6。',
            title: '榜单结论',
          },
        ],
        sourceChipIds: ['aa-leaderboard'],
        summary: '2026 大模型榜单需要以可验证来源和指标维度呈现。',
      },
      completion_reason: 'completed',
      evidence: [
        {
          id: 'aa-leaderboard',
          kind: 'web',
          snippet:
            'Comparison and ranking the performance of over 100 AI models (LLMs) across key metrics including intelligence, price, performance and speed.',
          title: 'Artificial Analysis LLM Leaderboard',
          url: 'https://artificialanalysis.ai/leaderboards/models',
        },
      ],
      final_stage_status: 'completed',
      timeline: [
        {
          id: 'stage-retrieval',
          metrics: { source_count: 2 },
          status: 'completed',
          summary: '找到 2 条来源',
          type: 'retrieval',
        },
        {
          id: 'stage-answer',
          status: 'completed',
          summary: '已完成答案整理',
          type: 'answer_assembly',
        },
      ],
      turn_outcome: 'success',
    },
    ...overrides,
  } as ChatMessage;
}

function createInsufficientSourceMessage(content: string): ChatMessage {
  return {
    clientKey: 'leaderboard-insufficient-sources',
    content,
    role: 'assistant',
    streaming: false,
    turnFlow: {
      completion_reason: 'completed',
      error_surface: {
        error_type: 'low_query_relevance',
        message: '可验证来源不足，暂不能生成可靠排行。',
      },
      evidence: [],
      failure_kind: 'low_query_relevance',
      final_stage_status: 'error',
      timeline: [
        {
          id: 'stage-retrieval-insufficient',
          metrics: { source_count: 0 },
          status: 'error',
          summary: '可验证来源不足',
          type: 'retrieval',
        },
        {
          id: 'stage-answer-failed',
          status: 'error',
          summary: '答复生成失败',
          type: 'answer_assembly',
        },
      ],
      turn_outcome: 'failed',
    },
  } as ChatMessage;
}

function createFashionWrapperFilteredMessage(content: string): ChatMessage {
  return {
    clientKey: 'fashion-wrapper-filtered',
    content,
    role: 'assistant',
    streaming: false,
    turnFlow: {
      completion_reason: 'candidate_search_wrapper_url',
      error_surface: {
        error_type: 'candidate_search_wrapper_url',
        message: '没有拿到可直接核实的网页来源。',
      },
      evidence: [],
      failure_kind: 'candidate_search_wrapper_url',
      final_stage_status: 'error',
      timeline: [
        {
          id: 'stage-fashion-retrieval',
          metrics: { source_count: 0 },
          status: 'error',
          summary: '搜索结果只包含包装页，未找到可直接核实来源',
          type: 'retrieval',
        },
        {
          id: 'stage-fashion-answer',
          status: 'error',
          summary: '未生成最终排行答案',
          type: 'answer_assembly',
        },
      ],
      turn_outcome: 'failed',
    },
  } as ChatMessage;
}

function mountContentBlock(msg: ChatMessage) {
  return mount(ChatMessageContentBlock, {
    props: {
      compact: true,
      index: 0,
      msg,
    },
  });
}

describe('chatMessageContentBlock', () => {
  it('resets to collapsed state when message identity changes on the same component instance', async () => {
    const wrapper = mount(ChatMessageContentBlock, {
      props: {
        compact: true,
        index: 0,
        msg: createLongMessage('history-msg-1'),
      },
    });

    expect(
      wrapper.get('[data-testid="assistant-content-collapse-toggle"]').text(),
    ).toBe('common.globalAiChat.expandMore');
    expect(
      wrapper.get('[data-testid="assistant-content-body"]').classes(),
    ).toContain('max-h-[176px]');

    await wrapper
      .get('[data-testid="assistant-content-collapse-toggle"]')
      .trigger('click');

    expect(
      wrapper.get('[data-testid="assistant-content-collapse-toggle"]').text(),
    ).toBe('common.globalAiChat.collapseMessage');
    expect(
      wrapper.get('[data-testid="assistant-content-body"]').classes(),
    ).not.toContain('max-h-[176px]');

    await wrapper.setProps({
      index: 0,
      msg: createLongMessage('history-msg-2'),
    });

    expect(
      wrapper.get('[data-testid="assistant-content-collapse-toggle"]').text(),
    ).toBe('common.globalAiChat.expandMore');
    expect(
      wrapper.get('[data-testid="assistant-content-body"]').classes(),
    ).toContain('max-h-[176px]');
  });

  it('keeps expanded state during updates for the same message identity', async () => {
    const message = createLongMessage('live-msg-1');
    const wrapper = mount(ChatMessageContentBlock, {
      props: {
        compact: true,
        index: 0,
        msg: message,
      },
    });

    await wrapper
      .get('[data-testid="assistant-content-collapse-toggle"]')
      .trigger('click');

    await wrapper.setProps({
      msg: {
        ...message,
        content: '更新后的长消息内容'.repeat(500),
      },
    });

    expect(
      wrapper.get('[data-testid="assistant-content-collapse-toggle"]').text(),
    ).toBe('common.globalAiChat.collapseMessage');
    expect(
      wrapper.get('[data-testid="assistant-content-body"]').classes(),
    ).not.toContain('max-h-[176px]');
  });

  it('resets expanded state when persisted message identity changes even if clientKey stays the same', async () => {
    const wrapper = mount(ChatMessageContentBlock, {
      props: {
        compact: true,
        index: 0,
        msg: {
          ...createLongMessage('shared-client-key'),
          message_id: 'message-1001',
        } as ChatMessage & { message_id: string },
      },
    });

    await wrapper
      .get('[data-testid="assistant-content-collapse-toggle"]')
      .trigger('click');

    await wrapper.setProps({
      msg: {
        ...createLongMessage('shared-client-key'),
        message_id: 'message-2002',
      } as ChatMessage & { message_id: string },
    });

    expect(
      wrapper.get('[data-testid="assistant-content-collapse-toggle"]').text(),
    ).toBe('common.globalAiChat.expandMore');
    expect(
      wrapper.get('[data-testid="assistant-content-body"]').classes(),
    ).toContain('max-h-[176px]');
  });

  it('does not render a one-character residual as the final answer when the leaderboard answer card is canonical', async () => {
    const wrapper = mountContentBlock(createLeaderboardResearchMessage('猫'));

    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="assistant-content-body"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).not.toContain('猫');
  });

  it('does not expose bare leaderboard metric numbers as an uncontextualized final answer body', async () => {
    const numericFragment =
      '59.68 65.71 20.54 27.41 26.12 36.40 31.26 34.84 6.55 13.50';
    const wrapper = mountContentBlock(
      createLeaderboardResearchMessage(numericFragment),
    );

    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="assistant-content-body"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).not.toContain(numericFragment);
  });

  it('keeps stage progress copy out of the final answer body when turnFlow already owns the process timeline', async () => {
    const processOnlyFragment =
      '结果整理\n本轮过程\n找到 2 条来源\n4 个阶段\n已完成';
    const wrapper = mountContentBlock(
      createLeaderboardResearchMessage(processOnlyFragment),
    );

    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="assistant-content-body"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).not.toContain('找到 2 条来源');
    expect(wrapper.text()).not.toContain('4 个阶段');
  });

  it('does not expose 2295 fashion search process-only text after wrapper candidates are rejected', async () => {
    const processOnlyFragment =
      '查一下 2026年最热门的 女性裙子款式排行！\n结果整理\n本轮过程\n找到 2 条来源\n4 个阶段\n已完成';
    const wrapper = mountContentBlock(
      createFashionWrapperFilteredMessage(processOnlyFragment),
    );

    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="assistant-content-body"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).not.toContain('女性裙子款式排行');
    expect(wrapper.text()).not.toContain('找到 2 条来源');
  });

  it('keeps the safe 2295 fallback answer visible after wrapper candidates are rejected', async () => {
    const safeFallback =
      '我找到了候选线索，但这些来源暂时无法直接核实，因此不生成结论。';
    const wrapper = mountContentBlock(
      createFashionWrapperFilteredMessage(safeFallback),
    );

    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="assistant-content-body"]').exists(),
    ).toBe(true);
    expect(wrapper.text()).toContain(safeFallback);
  });

  it('suppresses numeric fragments for insufficient-source leaderboard turns instead of showing a fake result', async () => {
    const wrapper = mountContentBlock(
      createInsufficientSourceMessage('59.68 65.71 20.54 27.41 26.12'),
    );

    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="assistant-content-body"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).not.toContain('59.68 65.71');
  });

  it('strips mixed residual query, process, source, and metric fragments while keeping the real final answer', async () => {
    const sourceSnippet =
      'Comparison and ranking the performance of over 100 AI models (LLMs) across key metrics including intelligence, price, performance and speed.';
    const numericFragment =
      '59.68 65.71 20.54 27.41 26.12 36.40 31.26 34.84 6.55 13.50';
    const finalAnswer =
      '正式结论：2026 年大模型排行应按 intelligence、price、speed 与 TTFT 分维度呈现，并标注每项来源。';
    const wrapper = mountContentBlock(
      createLeaderboardResearchMessage(
        `猫\n\n结果整理\n本轮过程\n找到 2 条来源\n4 个阶段\n已完成\n${sourceSnippet}\n${numericFragment}\n\n${finalAnswer}`,
      ),
    );

    await wrapper.vm.$nextTick();

    const rendered = wrapper
      .get('[data-testid="markdown-render-content"]')
      .text();
    expect(rendered).toContain(finalAnswer);
    expect(rendered).not.toContain('猫');
    expect(rendered).not.toContain('找到 2 条来源');
    expect(rendered).not.toContain(sourceSnippet);
    expect(rendered).not.toContain(numericFragment);
  });

  it('continues to render a contextual final leaderboard answer body', async () => {
    const finalAnswer =
      '截至 2026 年，建议用 Artificial Analysis LLM Leaderboard 这类可验证榜单，按 intelligence、price、speed 与 TTFT 维度比较 GPT-5.5、Gemini 3 Pro、Claude Opus 4.6。';
    const wrapper = mountContentBlock(
      createLeaderboardResearchMessage(finalAnswer),
    );

    await wrapper.vm.$nextTick();

    const rendered = wrapper
      .get('[data-testid="markdown-render-content"]')
      .text();
    expect(rendered).toContain('Artificial Analysis LLM Leaderboard');
    expect(rendered).toContain('GPT-5.5');
    expect(rendered).toContain('TTFT');
  });
});
