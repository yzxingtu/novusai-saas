// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: running tool details default open during transcript streaming and collapse with the tool group after completion.
import type { ChatMessage } from '../types';

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import ChatMessageToolCalls from '../ChatMessageToolCalls.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

function createStreamingMessage(status: 'running' | 'success'): ChatMessage {
  return {
    clientKey: 'assistant-streaming-tool-calls',
    content: status === 'running' ? '' : 'Final reply',
    role: 'assistant',
    streaming: status === 'running',
    turnFlow: {
      evidence: [
        {
          arguments: {
            record_id: 101,
            table: 'suppliers',
          },
          id: 'tool-evidence-1',
          kind: 'tool',
          output: JSON.stringify({
            result: {
              changed: true,
              trace_id: 'trace-running-tool',
            },
          }),
          status,
          toolCallId: 'tool-call-1',
          toolName: 'query_records',
        },
      ],
      timeline: [],
    },
  };
}

describe('ChatMessageToolCalls state', () => {
  it('keeps running tool details open during streaming and folds the group after completion', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
      props: {
        compact: true,
        embedded: false,
        index: 0,
        msg: createStreamingMessage('running'),
      },
    });

    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="tool-group-body"]').attributes('style'),
    ).toContain('grid-template-rows: 1fr');
    expect(
      wrapper.get('[data-testid="tool-call-details-0"]').attributes('style'),
    ).toContain('grid-template-rows: 1fr');
    expect(wrapper.text()).toContain('common.globalAiChat.toolInputParameters');
    expect(wrapper.text()).toContain('common.globalAiChat.toolReturnValue');

    await wrapper.setProps({
      msg: createStreamingMessage('success'),
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="tool-group-body"]').attributes('style'),
    ).toContain('grid-template-rows: 0fr');
  });
});
