// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
// Test type: behavioral
// Verifies: inline assistant diagnostics stay hidden by default across surfaces
// and only render when explicitly forced or enabled by the shared diagnostics policy.
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatMessageItem from '../ChatMessageItem.vue';

const mockPublicConfigStore = {
  platformConfig: null as null | { features?: Record<string, unknown> },
  tenantConfig: null as null | { features?: Record<string, unknown> },
};

vi.mock('#/locales', () => ({
  $t: (key: string, params?: Record<string, unknown>) =>
    params && 'traceId' in params
      ? `${key}:${String(params.traceId)}`
      : key,
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
    Popover: defineComponent({
      name: 'PopoverStub',
      template: '<span><slot /></span>',
    }),
    Tooltip: defineComponent({
      name: 'TooltipStub',
      template: '<span><slot /></span>',
    }),
  };
});

vi.mock('#/store/shared/public-config', () => ({
  usePublicConfigStore: () => mockPublicConfigStore,
}));

vi.mock('#/utils/request/app-env', () => ({
  isDevErrorMode: () => false,
}));

describe('chatMessageItem turn diagnostics', () => {
  beforeEach(() => {
    mockPublicConfigStore.platformConfig = null;
    mockPublicConfigStore.tenantConfig = null;
  });

  function mountMessage(
    msg: Partial<InstanceType<typeof ChatMessageItem>['$props']['msg']> = {},
    props: Partial<InstanceType<typeof ChatMessageItem>['$props']> = {},
  ) {
    return mount(ChatMessageItem, {
      props: {
        apiPrefix: '/admin',
        index: 0,
        msg: {
          clientKey: 'assistant-turn-diagnostics',
          content: 'diagnostics',
          role: 'assistant',
          ...msg,
        },
        ...props,
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
      selectedSkillNames: ['runtime.search', 'runtime.route'],
      selectedToolNames: ['query_records'],
      terminationReason: 'completed',
      turnOutcome: 'success',
    });

    const rendered = wrapper.text();
    expect(rendered).not.toContain('selected_skills');
    expect(rendered).not.toContain('runtime.search');
    expect(rendered).not.toContain('selected_tools');
    expect(rendered).not.toContain('query_records');
    expect(rendered).not.toContain('turn_outcome');
    expect(rendered).not.toContain('termination_reason');
  });

  it('hides turn diagnostics chips for benign partial assistant turns', () => {
    const wrapper = mountMessage({
      partial: true,
      selectedSkillNames: ['runtime.search'],
      selectedToolNames: ['web_search'],
      terminationReason: 'interrupted',
      turnOutcome: 'partial',
    });

    const rendered = wrapper.text();
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(rendered).not.toContain('partial');
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticTerminationReasonLabel',
    );
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticSelectedSkillsLabel',
    );
    expect(rendered).not.toContain('runtime.search');
  });

  it('hides failed-turn diagnostics by default', () => {
    const wrapper = mountMessage({
      requestFailedRetry: true,
      selectedToolNames: ['web_search'],
      terminationReason: 'tool_error',
      turnOutcome: 'failed',
    });

    const rendered = wrapper.text();
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(rendered).not.toContain('failed');
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticTerminationReasonLabel',
    );
    expect(rendered).not.toContain('tool_error');
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticSelectedToolsLabel',
    );
    expect(rendered).not.toContain('web_search');
  });

  it('renders inline diagnostics when admin diagnostics features are enabled', () => {
    mockPublicConfigStore.platformConfig = {
      features: {
        show_diagnostics: true,
      },
    };

    const wrapper = mountMessage({
      requestFailedRetry: true,
      selectedSkillNames: ['runtime.web'],
      selectedToolNames: ['web_search'],
      terminationReason: 'tool_error',
      turnOutcome: 'failed',
    });

    const rendered = wrapper.text();
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(rendered).toContain('failed');
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticSelectedToolsLabel',
    );
    expect(rendered).toContain('web_search');
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticSelectedSkillsLabel',
    );
    expect(rendered).toContain('runtime.web');
  });

  it('renders diagnostics when explicitly forced on', () => {
    const wrapper = mountMessage(
      {
        requestFailedRetry: true,
        selectedToolNames: ['web_search'],
        terminationReason: 'tool_error',
        turnOutcome: 'failed',
      },
      {
        forceShowDiagnostics: true,
      },
    );

    const rendered = wrapper.text();
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(rendered).toContain('failed');
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticTerminationReasonLabel',
    );
    expect(rendered).toContain('tool_error');
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticSelectedToolsLabel',
    );
    expect(rendered).toContain('web_search');
  });

  it('only renders active context source chips when diagnostics are enabled', () => {
    const wrapper = mountMessage(
      {
        contextSources: [
          {
            active: true,
            kind: 'skill',
            name: 'skill_resolver',
          },
          {
            active: false,
            kind: 'session_memory',
            name: 'session_memory',
          },
        ],
        requestFailedRetry: true,
        terminationReason: 'tool_error',
        turnOutcome: 'failed',
      },
      {
        forceShowDiagnostics: true,
      },
    );

    const rendered = wrapper.text();
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticContextSourcesLabel',
    );
    expect(rendered).toContain('skill:skill_resolver');
    expect(rendered).not.toContain('session_memory:session_memory');
  });

  it('shows a truncation warning when the reply hits the length limit', () => {
    const wrapper = mountMessage({
      completionReason: 'length',
      content: 'This response stopped because it hit the model length limit.',
    });

    expect(wrapper.text()).toContain('common.globalAiChat.responseTruncated');
    expect(wrapper.find('[data-testid="truncation-warning"]').exists()).toBe(
      true,
    );
  });

  it('hides turn diagnostics when a structured error panel is shown', () => {
    const wrapper = mountMessage({
      error: {
        message: '服务器内部错误',
        source: 'sse',
        traceId: 'trace-chat-error',
      },
      requestFailedRetry: true,
      selectedToolNames: ['web_search'],
      terminationReason: 'error',
      turnOutcome: 'failed',
    });

    const rendered = wrapper.text();
    expect(rendered).toContain('服务器内部错误');
    expect(wrapper.get('[data-testid="assistant-error-trace-id"]').text()).toContain(
      'trace-chat-error',
    );
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticSelectedToolsLabel',
    );
    expect(rendered).not.toContain('web_search');
  });

  it('hides diagnostics by default on the tenant surface', () => {
    const wrapper = mountMessage(
      {
        requestFailedRetry: true,
        selectedToolNames: ['web_search'],
        terminationReason: 'tool_error',
        turnOutcome: 'failed',
      },
      {
        apiPrefix: '/tenant',
      },
    );

    const rendered = wrapper.text();
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(rendered).not.toContain(
      'common.globalAiChat.diagnosticSelectedToolsLabel',
    );
    expect(rendered).not.toContain('web_search');
  });

  it('renders diagnostics on the user surface when tenant diagnostics are enabled', () => {
    mockPublicConfigStore.tenantConfig = {
      features: {
        show_diagnostics: true,
      },
    };

    const wrapper = mountMessage(
      {
        requestFailedRetry: true,
        selectedToolNames: ['web_search'],
        terminationReason: 'tool_error',
        turnOutcome: 'failed',
      },
      {
        apiPrefix: '/api/user',
      },
    );

    const rendered = wrapper.text();
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(rendered).toContain('failed');
    expect(rendered).toContain(
      'common.globalAiChat.diagnosticSelectedToolsLabel',
    );
    expect(rendered).toContain('web_search');
  });
});
