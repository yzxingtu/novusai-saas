// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
// Test type: behavioral
// Verifies: user full-page AI chat memory panel surfaces long-term memory
// preview records instead of rendering the empty state.
import { mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import UserAIChatWorkspaceMemoryPanel from '../UserAIChatWorkspaceMemoryPanel.vue';

const showMemoryPanel = ref(true);
const memoryState = ref({
  constraints: [],
  long_term_memories: ['我的项目代号是 Phoenix'],
  preferences: [],
  task_states: [],
  updated_at: 0,
  verified_facts: [],
  version: 0,
});
const memoryLoading = ref(false);
const clearingMemory = ref(false);
const onClearMemory = vi.fn();

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    props: {
      icon: { default: '', type: String },
    },
    template: '<span class="iconify-stub" :data-icon="icon" />',
  }),
}));

vi.mock('../user-ai-chat-workspace-context', () => ({
  useUserAIChatWorkspaceContext: () => ({
    page: {
      chat: {
        clearingMemory,
        memoryLoading,
        memoryState,
      },
      onClearMemory,
      showMemoryPanel,
    },
  }),
}));

describe('userAIChatWorkspaceMemoryPanel', () => {
  it('renders long-term memory preview records', () => {
    const wrapper = mount(UserAIChatWorkspaceMemoryPanel, {
      global: {
        stubs: {
          Spin: defineComponent({
            name: 'SpinStub',
            template: '<span />',
          }),
          Tooltip: defineComponent({
            name: 'TooltipStub',
            inheritAttrs: false,
            template: '<span><slot /></span>',
          }),
        },
      },
    });

    expect(wrapper.text()).toContain('common.globalAiChat.longTermMemories');
    expect(wrapper.text()).toContain('我的项目代号是 Phoenix');
    expect(wrapper.text()).not.toContain(
      'common.globalAiChat.clearMemoryEmpty',
    );
  });
});
