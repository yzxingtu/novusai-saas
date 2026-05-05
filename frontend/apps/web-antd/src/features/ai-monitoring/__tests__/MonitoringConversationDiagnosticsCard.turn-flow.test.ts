// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import MonitoringConversationDiagnosticsCard from '../pages/monitoring-conversation/MonitoringConversationDiagnosticsCard.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

describe('monitoringConversationDiagnosticsCard turn-flow parity', () => {
  it('prefers canonical turn_flow failure semantics over stale diagnostics fields', () => {
    const wrapper = mount(MonitoringConversationDiagnosticsCard, {
      props: {
        detail: {
          call_count: 1,
          call_trace: [],
          context_diagnostics: {
            candidate_tool_names: ['query_records', 'web_search'],
            execution_path: 'stream',
            failure_kind: 'provider_timeout',
            intent_plan: [
              {
                allowed_tools: ['query_records', 'fetch_url'],
                intent_id: 'intent-1',
                kind: 'direct_reply',
                selected_tools: ['query_records', 'web_search'],
                status: 'completed',
              },
            ],
            partial_exit_reason: 'stale_partial_exit_reason',
            provider_events: [
              { kind: 'connection_recovered' },
              { kind: 'response.web_search_call.completed' },
            ],
          },
          created_at: '2026-04-16T10:00:00Z',
          id: 9001,
          message_count: 1,
          message_list: [
            {
              content: '',
              created_at: '2026-04-16T10:00:01Z',
              id: 1001,
              metadata: {
                turn_flow: {
                  completion_reason: 'provider_failure_after_partial_progress',
                  failure_kind: 'provider_failure_after_partial_progress',
                  final_stage_status: 'error',
                  timeline: [
                    {
                      id: 'stage-thinking',
                      status: 'completed',
                      type: 'thinking',
                    },
                    {
                      id: 'stage-terminal',
                      status: 'error',
                      type: 'failed',
                    },
                  ],
                  turn_outcome: 'failed',
                },
              },
              role: 'assistant',
              sequence: 1,
              token_count: 0,
            },
          ],
          status: 'active',
          title: 'diag parity',
          total_cost: 0,
          total_tokens: 0,
          updated_at: '2026-04-16T10:00:02Z',
        },
        i18nPrefix: 'admin.ai.monitoring.conversations',
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
        },
      },
    });

    const text = wrapper.text();
    expect(text).toContain('provider_failure_after_partial_progress');
    expect(text).toContain('query_records');
    expect(text).not.toContain('provider_timeout');
    expect(text).not.toContain('stale_partial_exit_reason');
    expect(text).not.toContain('web_search');
    expect(text).not.toContain('fetch_url');
    expect(text).not.toContain('response.web_search_call.completed');
  });
});
