// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: turn diagnostics stay hidden by default and only render when the shared
// diagnostics policy or forceShow explicitly enables them.
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatMessageDiagnostics from '../ChatMessageDiagnostics.vue';

const mockPublicConfigStore = {
  platformConfig: null as null | { features?: Record<string, unknown> },
  tenantConfig: null as null | { features?: Record<string, unknown> },
};

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/store/shared/public-config', () => ({
  usePublicConfigStore: () => mockPublicConfigStore,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

function mountDiagnostics(
  props: Partial<InstanceType<typeof ChatMessageDiagnostics>['$props']> = {},
) {
  return mount(ChatMessageDiagnostics, {
    props: {
      apiPrefix: '/tenant',
      msg: {
        clientKey: 'diagnostics-message',
        content: 'failed reply',
        requestFailedRetry: true,
        role: 'assistant',
        selectedToolNames: ['query_records'],
        terminationReason: 'tool_error',
        turnOutcome: 'failed',
      },
      ...props,
    },
  });
}

describe('chatMessageDiagnostics', () => {
  beforeEach(() => {
    mockPublicConfigStore.platformConfig = null;
    mockPublicConfigStore.tenantConfig = null;
  });

  it('does not render when diagnostics are disabled by policy', () => {
    const wrapper = mountDiagnostics();

    expect(wrapper.text()).toBe('');
    expect(wrapper.text()).not.toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
  });

  it('renders when diagnostics are explicitly forced on', () => {
    const wrapper = mountDiagnostics({ forceShow: true });

    expect(wrapper.text()).toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(wrapper.text()).toContain('failed');
    expect(wrapper.text()).toContain(
      'common.globalAiChat.diagnosticSelectedToolsLabel',
    );
    expect(wrapper.text()).toContain('query_records');
  });

  it('filters retired online-search tool names from diagnostics', () => {
    const wrapper = mountDiagnostics({
      forceShow: true,
      msg: {
        clientKey: 'diagnostics-message',
        content: 'offline reply',
        requestFailedRetry: true,
        role: 'assistant',
        selectedToolNames: ['query_records', 'web_search', 'fetch_url'],
        terminationReason: 'tool_error',
        turnOutcome: 'failed',
      },
    });

    expect(wrapper.text()).toContain('query_records');
    expect(wrapper.text()).not.toContain('web_search');
    expect(wrapper.text()).not.toContain('fetch_url');
  });

  it('renders when the tenant diagnostics feature enables the shared policy', () => {
    mockPublicConfigStore.tenantConfig = {
      features: {
        show_diagnostics: true,
      },
    };

    const wrapper = mountDiagnostics({ apiPrefix: '/api/user' });

    expect(wrapper.text()).toContain(
      'common.globalAiChat.diagnosticTurnOutcomeLabel',
    );
    expect(wrapper.text()).toContain('failed');
  });
});
