// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: the shared conversation footer keeps export actions available even before token usage is populated.
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

vi.mock('ant-design-vue', () => ({
  Dropdown: defineComponent({
    name: 'DropdownStub',
    template:
      '<div data-testid="footer-dropdown"><slot /><slot name="overlay" /></div>',
  }),
  Menu: defineComponent({
    name: 'MenuStub',
    props: {
      items: {
        default: () => [],
        type: Array,
      },
    },
    template:
      '<div data-testid="footer-menu">{{ items.map((item) => item?.label).join(",") }}</div>',
  }),
}));

describe('aiChatConversationFooter', () => {
  it('keeps export actions visible while streaming even when token usage is not available yet', () => {
    const wrapper = mount(AIChatConversationFooter, {
      props: {
        exportMenuItems: [{ key: 'markdown', label: 'Markdown' }],
        messageCount: 4,
        streaming: true,
        totalTokensUsed: 0,
      },
    });

    expect(wrapper.find('[data-testid="footer-dropdown"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('common.globalAiChat.tokens');
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
