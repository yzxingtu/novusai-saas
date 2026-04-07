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
  function mountMessage(
    msg: Partial<
      InstanceType<typeof ChatMessageItem>['$props']['msg']
    > = {},
  ) {
    return mount(ChatMessageItem, {
      props: {
        index: 0,
        msg: {
          clientKey: 'assistant-turn-diagnostics',
          content: 'diagnostics',
          role: 'assistant',
          ...msg,
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
  }

  it('hides turn diagnostics chips for successful assistant turns', () => {
    const wrapper = mountMessage({
      selectedSkillNames: ['runtime.page_context', 'runtime.route'],
      selectedToolNames: ['query_records'],
      terminationReason: 'completed',
      turnOutcome: 'success',
    });

    const rendered = wrapper.text();
    expect(rendered).not.toContain('selected_skills');
    expect(rendered).not.toContain('runtime.page_context');
    expect(rendered).not.toContain('selected_tools');
    expect(rendered).not.toContain('query_records');
    expect(rendered).not.toContain('turn_outcome');
    expect(rendered).not.toContain('termination_reason');
  });

  it('renders turn diagnostics chips for partial assistant turns', () => {
    const wrapper = mountMessage({
      partial: true,
      selectedSkillNames: ['runtime.page_context'],
      selectedToolNames: ['invoke_page_operation'],
      terminationReason: 'interrupted',
      turnOutcome: 'partial',
    });

    const rendered = wrapper.text();
    expect(rendered).toContain('turn_outcome');
    expect(rendered).toContain('partial');
    expect(rendered).toContain('termination_reason');
    expect(rendered).toContain('interrupted');
    expect(rendered).toContain('selected_skills');
    expect(rendered).toContain('runtime.page_context');
  });

  it('renders turn diagnostics chips for failed assistant turns', () => {
    const wrapper = mountMessage({
      requestFailedRetry: true,
      selectedToolNames: ['web_search'],
      terminationReason: 'tool_error',
      turnOutcome: 'failed',
    });

    const rendered = wrapper.text();
    expect(rendered).toContain('turn_outcome');
    expect(rendered).toContain('failed');
    expect(rendered).toContain('termination_reason');
    expect(rendered).toContain('tool_error');
    expect(rendered).toContain('selected_tools');
    expect(rendered).toContain('web_search');
  });
});
