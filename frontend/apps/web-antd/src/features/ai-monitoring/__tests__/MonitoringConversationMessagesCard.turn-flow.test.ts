// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: monitoring message cards project canonical turn_flow data through real adapters.
import { mount } from '@vue/test-utils';
import { computed, defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import MonitoringConversationMessagesCard from '../pages/monitoring-conversation/MonitoringConversationMessagesCard.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('#/utils/common', () => ({
  formatDate: (value: string) => value,
  formatTimeOnly: (value: string) => value,
}));

vi.mock('#/components/business/ai-chat-panel/ChatMessageItem.vue', () => ({
  default: defineComponent({
    name: 'ChatMessageItemStub',
    props: {
      apiPrefix: { type: String, default: '' },
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
      '<div data-testid="chat-message-item-stub" :data-api-prefix="apiPrefix" :data-stage-id="msg?.turnFlow?.timeline?.[0]?.id || \'\'" :data-has-thinking="String(hasThinking)" :data-has-tool-calls="String(hasToolCalls)" :data-turn-outcome="msg?.turnOutcome || \'\'" :data-termination-reason="msg?.terminationReason || \'\'" :data-has-error="String(!!msg?.error)" :data-streaming="String(!!msg?.streaming)" />',
  }),
}));

describe('monitoringConversationMessagesCard turn-flow rendering', () => {
  it('uses ChatMessageItem only and avoids external timeline/evidence wrappers', () => {
    const wrapper = mount(MonitoringConversationMessagesCard, {
      props: {
        i18nPrefix: 'admin.ai.monitoring.conversations',
        messages: [
          {
            content: 'answer',
            created_at: '2026-04-16T10:00:00Z',
            id: 1,
            metadata: {
              failure_kind: 'provider_failure_after_partial_progress',
              thinking_content: 'legacy thinking',
              termination_reason: 'provider_failure_after_partial_progress',
              turn_outcome: 'partial',
            },
            role: 'assistant',
            sequence: 1,
            token_count: 12,
            tool_calls: [{ function: { name: 'legacy_tool' }, success: true }],
            turn_flow: {
              final_stage_status: 'error',
              evidence: [],
              timeline: [
                {
                  id: 'stage-monitoring',
                  status: 'completed',
                  type: 'thinking',
                },
              ],
            },
          } as unknown as import('../api').MonitoringConversationMessage,
        ],
        scope: 'admin',
      },
      global: {
        stubs: {
          ACard: defineComponent({
            name: 'CardStub',
            template:
              '<div class="card-stub"><slot name="title" /><slot /></div>',
          }),
          AEmpty: defineComponent({
            name: 'EmptyStub',
            template: '<div data-testid="empty-stub" />',
          }),
          ATag: defineComponent({
            name: 'TagStub',
            template: '<span><slot /></span>',
          }),
          ATooltip: defineComponent({
            name: 'TooltipStub',
            template: '<span><slot /></span>',
          }),
        },
      },
    });

    const messageItem = wrapper.get('[data-testid="chat-message-item-stub"]');
    expect(messageItem.attributes('data-api-prefix')).toBe('/admin');
    expect(messageItem.attributes('data-stage-id')).toBe('stage-monitoring');
    expect(messageItem.attributes('data-has-thinking')).toBe('false');
    expect(messageItem.attributes('data-has-tool-calls')).toBe('false');
    expect(messageItem.attributes('data-turn-outcome')).toBe('failed');
    expect(messageItem.attributes('data-termination-reason')).toBe(
      'provider_failure_after_partial_progress',
    );
    expect(messageItem.attributes('data-has-error')).toBe('false');
    expect(messageItem.attributes('data-streaming')).toBe('false');
  });
});
