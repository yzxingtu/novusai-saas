// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: the shared conversation footer stays focused on lightweight usage telemetry and no longer surfaces export chrome.
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatConversationFooter from '../AIChatConversationFooter.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

describe('aiChatConversationFooter', () => {
  it('stays hidden when only export actions exist without token usage', () => {
    const wrapper = mount(AIChatConversationFooter, {
      props: {
        exportMenuItems: [{ key: 'markdown', label: 'Markdown' }],
        messageCount: 4,
        streaming: true,
        totalTokensUsed: 0,
      },
    });

    expect(wrapper.html()).toBe('<!--v-if-->');
  });

  it('shows only the token summary once usage is available', () => {
    const wrapper = mount(AIChatConversationFooter, {
      props: {
        exportMenuItems: [{ key: 'markdown', label: 'Markdown' }],
        messageCount: 3,
        streaming: false,
        totalTokensUsed: 1024,
      },
    });

    expect(wrapper.text()).toContain('3 common.globalAiChat.messages');
    expect(wrapper.text()).toContain('1,024 common.globalAiChat.tokens');
    expect(wrapper.find('button').exists()).toBe(false);
  });

  it('stays hidden when there is no summary and no export action', () => {
    const wrapper = mount(AIChatConversationFooter, {
      props: {
        exportMenuItems: [],
        messageCount: 0,
        streaming: false,
        totalTokensUsed: 0,
      },
    });

    expect(wrapper.html()).toBe('<!--v-if-->');
  });
});
