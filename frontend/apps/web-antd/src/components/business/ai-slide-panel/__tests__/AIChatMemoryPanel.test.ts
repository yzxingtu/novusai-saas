// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: memory panel surfaces long-term memory preview records instead of
// showing an empty state when session memory buckets are empty.
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatMemoryPanel from '../AIChatMemoryPanel.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    props: {
      icon: { type: String, required: false },
    },
    template: '<span class="iconify-stub" :data-icon="icon" />',
  }),
}));

describe('AIChatMemoryPanel', () => {
  it('renders long-term memory previews when short-term buckets are empty', () => {
    const wrapper = mount(AIChatMemoryPanel, {
      props: {
        memoryState: {
          constraints: [],
          long_term_memories: ['我的项目代号是 Phoenix'],
          preferences: [],
          task_states: [],
          updated_at: 0,
          verified_facts: [],
          version: 0,
        },
        open: true,
      },
      global: {
        stubs: {
          Spin: defineComponent({
            name: 'SpinStub',
            template: '<span />',
          }),
          Tooltip: defineComponent({
            name: 'TooltipStub',
            template: '<span><slot /></span>',
          }),
        },
      },
    });

    expect(wrapper.text()).toContain('common.globalAiChat.longTermMemories');
    expect(wrapper.text()).toContain('我的项目代号是 Phoenix');
    expect(wrapper.text()).not.toContain('common.globalAiChat.clearMemoryEmpty');
  });
});
