// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import ChatMessageItem from '../ChatMessageItem.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('ant-design-vue', () => {
  const Modal = Object.assign(
    defineComponent({
      name: 'ModalStub',
      props: {
        open: {
          default: false,
          type: Boolean,
        },
      },
      template: '<div v-if="open"><slot /></div>',
    }),
    {
      confirm: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    },
  );

  return {
    Button: defineComponent({
      name: 'ButtonStub',
      emits: ['click'],
      template: '<button @click="$emit(\'click\')"><slot /></button>',
    }),
    Modal,
    Tooltip: defineComponent({
      name: 'TooltipStub',
      template: '<span><slot /></span>',
    }),
  };
});

vi.mock('#/store', () => ({
  useAIPanelStore: () => ({
    resolvePageOp: vi.fn(),
  }),
}));

describe('chatMessageItem turn diagnostics', () => {
  it('renders selected skills diagnostics chips for assistant messages', () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        index: 0,
        msg: {
          clientKey: 'assistant-turn-diagnostics',
          content: 'diagnostics',
          role: 'assistant',
          selectedSkillNames: ['runtime.page_context', 'runtime.route'],
          selectedToolNames: ['query_records'],
          turnOutcome: 'success',
        },
      },
      global: {
        stubs: {
          AgentProfilePopover: defineComponent({
            name: 'AgentProfilePopoverStub',
            template: '<div><slot /></div>',
          }),
          MarkdownRender: defineComponent({
            name: 'MarkdownRenderStub',
            props: { content: { default: '', type: String } },
            template: '<div class="markdown">{{ content }}</div>',
          }),
          RichTextDraftCard: defineComponent({
            name: 'RichTextDraftCardStub',
            template: '<div></div>',
          }),
        },
      },
    });

    const rendered = wrapper.text();
    expect(rendered).toContain('selected_skills');
    expect(rendered).toContain('runtime.page_context');
    expect(rendered).toContain('runtime.route');
    expect(rendered).toContain('selected_tools');
    expect(rendered).toContain('query_records');
  });
});
