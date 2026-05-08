// @vitest-environment happy-dom
// Test type: behavioral
// 中文: 验证实时答案摘要不会重复展示已在助手正文中出现的同一内容。
// EN: Verifies live answer digests do not duplicate the assistant transcript body.
// 中文: 只 stub i18n 与图标呈现，EvidenceCard 去重逻辑走真实实现。
// EN: Only i18n and icons are stubbed; EvidenceCard redundancy logic runs real.
import type { ChatMessage } from '#/types/ai-chat';

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import EvidenceCard from '../EvidenceCard.vue';
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

function mountEvidenceCard(msg: ChatMessage) {
  return mount(EvidenceCard, {
    props: {
      compact: true,
      msg,
      state: buildTurnFlowState(msg),
    },
  });
}

describe('evidence card', () => {
  it('suppresses redundant live answer summaries already visible in assistant content', async () => {
    const duplicateAnswer =
      '近7天拉萨天气整体偏晴朗、昼夜温差大，白天注意防晒，早晚加厚外套。';
    const wrapper = mountEvidenceCard({
      clientKey: 'assistant-live-duplicate',
      content: duplicateAnswer,
      role: 'assistant',
      streaming: true,
      turnFlow: {
        answerCard: {
          summary: ` ${duplicateAnswer.replaceAll('，', '，\n')} `,
        },
        evidence: [],
        timeline: [
          {
            id: 'answer-assembly',
            status: 'running',
            summary: '正在组织答案',
            type: 'answer_assembly',
          },
        ],
      },
    } as ChatMessage);

    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(false);
  });

  it('keeps live process digest visible when it differs from the answer body', async () => {
    const wrapper = mountEvidenceCard({
      clientKey: 'assistant-live-process',
      content: '近7天拉萨天气整体偏晴朗。',
      role: 'assistant',
      streaming: true,
      turnFlow: {
        evidence: [],
        timeline: [
          {
            id: 'answer-assembly',
            status: 'running',
            summary: '正在组织答案',
            type: 'answer_assembly',
          },
        ],
      },
    } as ChatMessage);

    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(true);
    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnStageStatus.running',
    );
  });
});
