// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
/**
 * AIChatSlidePanel component render tests: confirmCountdown in real component.
 * AIChatSlidePanel 组件挂载测试：倒计时文案在真实组件中渲染。
 *
 * 与 countdown-display.test.ts（纯逻辑单测）互补，覆盖“组件渲染层”。
 * Test type: behavioral
 * Mock strategy: store/runtime edges are mocked, while slide-panel shell/body bindings render real.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AIChatSlidePanel from '../AIChatSlidePanel.vue';
import { registerSlidePanelRichTextCases } from './ai-chat-slide-panel-rich-text-cases';
import {
  activeConversationIdValue,
  antMessageMocks,
  cleanupPanelDom,
  composerInteractionState,
  createAIPanelStore,
  createPanelMountOptions,
  flushPanel,
  inputMessageValue,
  loadConversationMessagesMock,
  pageContextValue,
  pageOperationsValue,
  pendingAttachmentsValue,
  pendingPageOpsValue,
  requireElement,
  resetPanelState,
  routeMessageMock,
  selectedAgentIdValue,
  sendMessageMock,
  startNewConversationMock,
  supportsVisionValue,
  useAIChatState,
} from './ai-chat-slide-panel-test-helpers';

let aiPanelStore: ReturnType<typeof createAIPanelStore>;
const publicConfigState = {
  platformConfig: { brand: { siteName: 'Test' } } as {
    brand: { siteName: string };
    features?: Record<string, boolean>;
  },
  tenantConfig: null as null | { features?: Record<string, boolean> },
};

vi.mock('@vben/icons', async () => {
  const { createIconifyMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createIconifyMock();
});
vi.mock('#/utils/image', async () => {
  const { createImageMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createImageMock();
});
vi.mock('ant-design-vue', async () => {
  const { createAntDesignVueMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createAntDesignVueMock();
});

vi.mock('#/store', () => ({
  useAIPanelStore: () => aiPanelStore,
}));

vi.mock('#/store/shared/public-config', () => ({
  usePublicConfigStore: () => publicConfigState,
}));

vi.mock('#/locales', () => ({
  i18n: {
    global: {
      locale: {
        value: 'zh-CN',
      },
    },
  },
  $t: (key: string, params?: { seconds?: number }) =>
    key === 'shared.pageOperation.confirmCountdown' &&
    params?.seconds !== undefined
      ? `${params.seconds}s remaining`
      : key,
}));

vi.mock('#/components/business/ai-chat-panel/use-ai-chat', async () => {
  const { createUseAIChatMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createUseAIChatMock();
});

vi.mock(
  '#/components/business/rich-text-editor/sourceEditorRegistry',
  async () => {
    const { createSourceEditorRegistryMock } =
      await import('./ai-chat-slide-panel-test-helpers');
    return createSourceEditorRegistryMock();
  },
);

vi.mock('../use-agent-router', async () => {
  const { createUseAgentRouterMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createUseAgentRouterMock();
});
vi.mock('#/composables/use-modal-detector', async () => {
  const { createUseModalDetectorMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createUseModalDetectorMock();
});
vi.mock('#/composables/use-page-session', async () => {
  const { createUsePageSessionMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createUsePageSessionMock();
});
vi.mock('#/composables/use-page-screenshot', async () => {
  const { createUsePageScreenshotMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createUsePageScreenshotMock();
});
vi.mock('#/composables/use-form-state-tracker', async () => {
  const { createFormStateTrackerMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createFormStateTrackerMock();
});
vi.mock('#/components/business/ai-runtime/runtime-bridge', async () => {
  const { createRuntimeBridgeMock } =
    await import('./ai-chat-slide-panel-test-helpers');
  return createRuntimeBridgeMock();
});

const mountPanel = (
  overrides?: Parameters<typeof createPanelMountOptions>[0],
) => mount(AIChatSlidePanel, createPanelMountOptions(overrides));

describe('aIChatSlidePanel (component mount)', () => {
  beforeEach(() => {
    aiPanelStore = resetPanelState();
    publicConfigState.platformConfig = { brand: { siteName: 'Test' } };
    publicConfigState.tenantConfig = null;
  });

  afterEach(() => {
    cleanupPanelDom();
  });

  registerSlidePanelRichTextCases({
    getAiPanelStore: () => aiPanelStore,
    mountPanel,
    setAiPanelStore: (store) => {
      aiPanelStore = store;
    },
  });

  it('renders confirmCountdown when pending op exists', async () => {
    aiPanelStore = resetPanelState(1_000_000_000_000, { useFakeTimers: true });
    const startedAt = Date.now();
    pendingPageOpsValue.value = [
      {
        invokeId: 'op-1',
        operationLabel: 'Replace Content',
        operationDescription: 'Replace content in editor',
        resolved: false,
        startedAt,
      },
    ];
    aiPanelStore.pendingPageOps = pendingPageOpsValue.value;

    const wrapper = mountPanel();

    await flushPromises();

    // Panel is teleported to body; confirmCountdown should be visible / 面板通过 teleport 挂到 body，需能看到倒计时
    const panel = document.querySelector('[data-ai-panel]');
    expect(panel).toBeTruthy();
    expect(panel?.textContent).toMatch(/\d+s remaining/);

    wrapper.unmount();
  });

  it('reopens without resetting the current conversation when no external context is queued', async () => {
    activeConversationIdValue.value = 10;

    const wrapper = mountPanel();

    await flushPromises();
    startNewConversationMock.mockClear();

    aiPanelStore.visible = false;
    await flushPromises();
    aiPanelStore.visible = true;
    await flushPromises();

    expect(startNewConversationMock).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('restores queued conversation before sending queued message', async () => {
    selectedAgentIdValue.value = 2;
    loadConversationMessagesMock.mockImplementation(async (convId: number) => {
      activeConversationIdValue.value = convId;
    });

    const wrapper = mountPanel({
      props: {
        pendingConversationId: 10,
        pendingMessage: 'continue this thread',
      },
    });

    await flushPromises();

    expect(startNewConversationMock).not.toHaveBeenCalled();
    expect(loadConversationMessagesMock).toHaveBeenCalledWith(10);
    expect(sendMessageMock).toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        pageContext: null,
      }),
    );
    const loadInvocationOrder =
      loadConversationMessagesMock.mock.invocationCallOrder[0];
    const sendInvocationOrder = sendMessageMock.mock.invocationCallOrder[0];

    const resolvedLoadInvocationOrder = requireElement(
      loadInvocationOrder,
      'Expected loadConversationMessages invocation order',
    );
    const resolvedSendInvocationOrder = requireElement(
      sendInvocationOrder,
      'Expected sendMessage invocation order',
    );
    expect(resolvedLoadInvocationOrder).toBeLessThan(
      resolvedSendInvocationOrder,
    );

    wrapper.unmount();
  });

  it('falls back to store pendingMessage when prop timing lags behind visibility change', async () => {
    selectedAgentIdValue.value = 2;
    aiPanelStore.pendingMessage = 'store queued message';
    aiPanelStore.visible = false;

    const wrapper = mountPanel();

    await flushPromises();

    aiPanelStore.visible = true;
    await flushPromises();

    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        pageContext: null,
      }),
    );
    expect(wrapper.emitted('messageSent')).toBeTruthy();

    wrapper.unmount();
  });

  it('keeps queued pendingMessage when external send did not start', async () => {
    selectedAgentIdValue.value = null;
    aiPanelStore.pendingMessage = 'store queued message';
    aiPanelStore.visible = false;
    routeMessageMock.mockRejectedValue(new Error('route failed'));

    const wrapper = mountPanel();

    await flushPromises();

    aiPanelStore.visible = true;
    await flushPromises();

    expect(sendMessageMock).not.toHaveBeenCalled();
    expect(wrapper.emitted('messageSent')).toBeFalsy();
    expect(aiPanelStore.pendingMessage).toBe('store queued message');

    wrapper.unmount();
  });

  it('uses the queued pendingAgentId as the send target when external context starts a new conversation', async () => {
    selectedAgentIdValue.value = 2;
    aiPanelStore.pendingMessage = 'send to explicit agent';
    aiPanelStore.consumePendingAgentId = vi.fn(() => 1);
    aiPanelStore.visible = false;

    const wrapper = mountPanel();

    await flushPromises();

    aiPanelStore.visible = true;
    await flushPromises();

    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 1,
        pageContext: null,
      }),
    );
    expect(wrapper.emitted('messageSent')).toBeTruthy();

    wrapper.unmount();
  });

  it('countdown decrements over time and stays >= 0', async () => {
    const base = 1_000_000_000_000;
    aiPanelStore = resetPanelState(base, { useFakeTimers: true });
    const startedAt = Date.now();
    pendingPageOpsValue.value = [
      {
        invokeId: 'op-1',
        operationLabel: 'Replace',
        operationDescription: '',
        resolved: false,
        startedAt,
      },
    ];
    aiPanelStore.pendingPageOps = pendingPageOpsValue.value;

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.page',
      },
    });

    await flushPanel();
    let panel = document.querySelector('[data-ai-panel]');
    const readCountdown = () => {
      const text = panel?.textContent ?? '';
      const match = text.match(/(\d+)s remaining/);
      return match ? Number(match[1]) : null;
    };
    const initialCountdown = readCountdown();
    expect(initialCountdown).not.toBeNull();

    // Advance 5s; countdown ticks every 1s / 前进 5 秒；倒计时按 1 秒步进
    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(1000);
      await flushPanel();
    }
    panel = document.querySelector('[data-ai-panel]');
    const afterFiveSeconds = readCountdown();
    expect(afterFiveSeconds).not.toBeNull();
    if (initialCountdown !== null && afterFiveSeconds !== null) {
      expect(afterFiveSeconds).toBeLessThan(initialCountdown);
    }

    // Advance to 60s+; countdown should clamp at 0 / 前进到 60 秒以上；倒计时应钳制为 0
    vi.advanceTimersByTime(60_000);
    await flushPanel();
    panel = document.querySelector('[data-ai-panel]');
    const finalCountdown = readCountdown();
    expect(finalCountdown).toBe(0);

    wrapper.unmount();
  });

  it('sends directly within an active conversation without routing again', async () => {
    activeConversationIdValue.value = 10;
    selectedAgentIdValue.value = 2;
    inputMessageValue.value = 'follow-up';

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.page',
      },
    });

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    requireElement(
      sendButton,
      'Expected send button in active conversation test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).not.toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        pageContext: expect.objectContaining({
          page_key: 'tenant.demo.page',
        }),
      }),
    );

    wrapper.unmount();
  });

  it('renders the restored header action set and direct memory entry without reserving an empty status rail', async () => {
    activeConversationIdValue.value = 10;
    selectedAgentIdValue.value = 2;

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.page',
      },
    });

    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-header-actions"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelector('[data-testid="ai-panel-primary-actions"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-primary-actions"] button',
      ),
    ).toHaveLength(4);
    expect(
      document.body.querySelector('[data-testid="ai-panel-toolbar-row"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelector('[data-testid="ai-panel-memory-button"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelector(
        'button[aria-label="common.aiPanel.moreActions"]',
      ),
    ).toBeFalsy();

    wrapper.unmount();
  });

  it('keeps the shell compact and transcript-first even when legacy full mode state is restored', async () => {
    aiPanelStore.mode = 'full';

    const wrapper = mountPanel({
      global: {
        stubs: {
          AIChatMessageViewport: defineComponent({
            name: 'AIChatMessageViewportTranscriptProbe',
            props: {
              compact: { type: Boolean, required: false },
            },
            template:
              '<div data-testid="ai-panel-transcript-probe" :data-compact="String(compact)" />',
          }),
        },
      },
    });

    await flushPromises();

    const panel = requireElement(
      document.body.querySelector('[data-ai-panel]') as HTMLDivElement | null,
      'Expected AI panel in full-mode transcript test',
    );
    const transcriptProbe = requireElement(
      document.body.querySelector(
        '[data-testid="ai-panel-transcript-probe"]',
      ) as HTMLElement | null,
      'Expected transcript probe in compact transcript test',
    );
    expect(panel.getAttribute('style')).toContain('width: 460px');
    expect(panel.className).toContain('panel-mode-shell');
    expect(transcriptProbe.dataset.compact).toBe('true');

    wrapper.unmount();
  });

  it('renders route notice as a standalone header banner after routing', async () => {
    selectedAgentIdValue.value = 1;
    inputMessageValue.value = 'hello';
    routeMessageMock.mockResolvedValueOnce({
      agentId: 1,
      agentName: 'Agent One',
      confidence: 1,
      routedBy: 'router',
    });

    const wrapper = mountPanel();

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    requireElement(
      sendButton,
      'Expected send button in large context routing test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    const routeBanner = document.body.querySelector(
      '[data-testid="ai-panel-route-banner"]',
    );
    expect(routeBanner).toBeTruthy();
    expect(routeBanner?.textContent).toContain('common.aiPanel.routedTo');

    wrapper.unmount();
  });

  it('renders a compact page AI rail that expands on demand', async () => {
    pageOperationsValue.value = [
      { name: 'ui_get_snapshot', label: 'Refresh', readonly: true },
      { name: 'ui_open_surface', label: 'Open Drawer', readonly: false },
      { name: 'ui_fill_form', label: 'Save Draft', readonly: false },
      { name: 'ui_read_table', label: 'Search Records', readonly: true },
      { name: 'ui_set_field', label: 'Assign Owner', readonly: false },
      { name: 'ui_list_interactables', label: 'Export View', readonly: true },
    ];

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.page',
      },
    });

    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-card"]'),
    ).toBeTruthy();
    const pageAiRow = document.body.querySelector(
      '[data-testid="ai-panel-toolbar-row"]',
    ) as HTMLDivElement | null;
    expect(pageAiRow).toBeTruthy();
    expect(pageAiRow?.className).toContain('w-full');
    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();
    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-page-ai-preview-item"]',
      ),
    ).toHaveLength(0);

    const capabilityRail = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-card"]',
    ) as HTMLDivElement | null;
    expect(capabilityRail).toBeTruthy();
    expect(capabilityRail?.className).toContain('w-full');
    const utilityBar = document.body.querySelector(
      '[data-testid="ai-panel-utility-bar"]',
    ) as HTMLDivElement | null;
    expect(utilityBar).toBeTruthy();
    utilityBar?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();

    const capabilityTriggerAgain = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-trigger"]',
    ) as HTMLDivElement | null;
    expect(capabilityTriggerAgain).toBeTruthy();
    capabilityTriggerAgain?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    );
    await flushPromises();

    const pageAiDetails = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-details"]',
    ) as HTMLDivElement | null;
    expect(pageAiDetails).toBeTruthy();
    expect(pageAiDetails?.className).toContain('w-full');
    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-page-ai-preview-item"]',
      ),
    ).toHaveLength(4);

    const capabilityTrigger = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-trigger"]',
    ) as HTMLDivElement | null;
    expect(capabilityTrigger).toBeTruthy();
    capabilityTrigger?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    );
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();

    const toggleButton = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-toggle"]',
    ) as HTMLButtonElement | null;
    expect(toggleButton).toBeTruthy();
    toggleButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeTruthy();
    expect(document.body.textContent).not.toContain(
      'common.aiPanel.pageAiDiagnostics',
    );
    expect(
      document.body.querySelector(
        '[data-testid="ai-panel-page-ai-diagnostics"]',
      ),
    ).toBeFalsy();
    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-page-ai-preview-item"]',
      ),
    ).toHaveLength(4);

    const moreButton = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-more"]',
    ) as HTMLButtonElement | null;
    expect(moreButton).toBeTruthy();
    moreButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-page-ai-preview-item"]',
      ),
    ).toHaveLength(5);

    toggleButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();

    wrapper.unmount();
  });

  it('auto-expands page AI details while streaming and collapses them after completion', async () => {
    pageContextValue.value = {
      page_key: 'tenant.demo.streaming',
      page_title: 'Streaming Demo',
      surface_stack: [
        {
          kind: 'page',
          surface_id: 'surface-root',
          title: 'Streaming Demo',
        },
      ],
      ui_epoch: 3,
    };
    pageOperationsValue.value = [
      { name: 'ui_get_snapshot', label: 'Snapshot', readonly: true },
      { name: 'ui_click', label: 'Click CTA', readonly: false },
    ];
    useAIChatState.streaming.value = true;

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.streaming',
      },
    });

    await flushPanel();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeTruthy();

    useAIChatState.streaming.value = false;
    await flushPanel();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();

    wrapper.unmount();
  });

  it('keeps the toolbar row outside the restored header shell when no status badge is shown', async () => {
    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.page',
      },
    });

    await flushPromises();

    const headerActions = document.body.querySelector(
      '[data-testid="ai-panel-header-actions"]',
    );
    expect(headerActions).toBeTruthy();
    expect(
      document.body.querySelector('[data-testid="ai-panel-header-meta-row"]'),
    ).toBeFalsy();
    const toolbarRow = document.body.querySelector(
      '[data-testid="ai-panel-toolbar-row"]',
    );
    const headerShell = document.body.querySelector('.ai-panel-header');
    expect(headerShell).toBeTruthy();
    expect(toolbarRow).toBeTruthy();
    expect(headerShell?.contains(toolbarRow ?? null)).toBe(false);
    expect(toolbarRow?.contains(headerActions)).toBe(true);

    wrapper.unmount();
  });

  it('mounts safely when page context exists before runtime size guards initialize', async () => {
    pageContextValue.value = {
      page_key: 'tenant.demo.page',
      page_title: 'admin.system.codegen.name',
      page_data: {
        entity_description: 'Codegen workspace',
      },
    };
    pageOperationsValue.value = [
      { name: 'ui_get_snapshot', label: 'Inspect', readonly: true },
    ];

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.page',
      },
    });

    await flushPromises();

    const pageAiCard = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-card"]',
    ) as HTMLDivElement | null;
    expect(pageAiCard).toBeTruthy();
    expect(pageAiCard?.textContent).toContain('common.aiPanel.pageAiSupported');
    expect(pageAiCard?.textContent).not.toContain('admin.system.codegen.name');
    expect(pageAiCard?.textContent).not.toContain('common.aiPanel.pageAiSummary');
    expect(antMessageMocks.error).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('shows fallback-only page AI support with a downgraded awareness badge', async () => {
    pageContextValue.value = {
      page_key: 'tenant.demo.fallback',
      page_title: 'Fallback Only',
      page_data: {
        entity_description: 'Fallback demo page',
      },
    };

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.fallback',
      },
    });

    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-card"]'),
    ).toBeTruthy();
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiFallbackBadge',
    );

    const fallbackTrigger = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-trigger"]',
    ) as HTMLDivElement | null;
    expect(fallbackTrigger).toBeTruthy();
    fallbackTrigger?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(
      document.body.querySelector(
        '[data-testid="ai-panel-page-ai-diagnostics"]',
      ),
    ).toBeFalsy();

    wrapper.unmount();
  });

  it('shows runtime page AI summary instead of fallback copy when ui runtime state is present', async () => {
    pageContextValue.value = {
      page_key: 'tenant.demo.runtime',
      page_session_id: 'page-session-1',
      page_title: 'Runtime Ready',
      surface_stack: [
        {
          kind: 'page',
          surface_id: 'surface-root',
          title: 'Runtime Ready',
        },
      ],
      ui_epoch: 7,
    };
    pageOperationsValue.value = [
      { name: 'ui_get_snapshot', label: 'Snapshot', readonly: true },
      { name: 'ui_list_interactables', label: 'Interactables', readonly: true },
      { name: 'ui_click', label: 'Click', readonly: false },
      { name: 'ui_fill_form', label: 'Fill Form', readonly: false },
    ];

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.runtime',
      },
    });

    await flushPromises();

    const trigger = requireElement(
      document.body.querySelector(
        '[data-testid="ai-panel-page-ai-trigger"]',
      ) as HTMLDivElement | null,
      'expected page AI trigger',
    );
    trigger.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(document.body.textContent).toContain('common.aiPanel.pageAiSummary');
    expect(document.body.textContent).not.toContain(
      'common.aiPanel.pageAiFallbackSummary',
    );
    expect(document.body.textContent).not.toContain(
      'common.aiPanel.pageAiFallbackSummaryWithOps',
    );
    expect(document.body.textContent).not.toContain(
      'common.aiPanel.pageAiFallbackBadge',
    );

    wrapper.unmount();
  });

  it('preserves compact page_data while keeping routed page context thin', async () => {
    inputMessageValue.value = 'inspect this page';
    pageContextValue.value = {
      page_key: 'tenant.demo.large',
      page_title: 'Large Demo Page',
      page_data: {
        entity_description: 'Large demo runtime page',
        navigation_catalog: [
          {
            breadcrumb: ['Dashboard'],
            endpoint: 'tenant',
            page_key: 'tenant.dashboard',
            path: '/tenant/dashboard',
            title: 'Dashboard',
          },
          {
            breadcrumb: ['AI', 'Agents'],
            endpoint: 'tenant',
            page_key: 'tenant.ai.agents',
            path: '/tenant/ai/agents',
            title: 'Agents',
          },
        ],
        navigation_context: {
          breadcrumb: ['AI', 'Agents'],
          endpoint: 'tenant',
          page_key: 'tenant.ai.agents',
          path: '/tenant/ai/agents',
        },
      },
    };
    const uiToolPool = [
      'ui_get_snapshot',
      'ui_list_interactables',
      'ui_read_region',
      'ui_read_table',
      'ui_click',
      'ui_open_surface',
      'ui_get_form_state',
      'ui_set_field',
      'ui_fill_form',
      'ui_submit_form',
    ] as const;
    pageOperationsValue.value = Array.from({ length: 16 }, (_, index) => {
      const toolName = uiToolPool.at(index % uiToolPool.length) ?? 'ui_click';
      return {
        description: `Operation ${index} `.repeat(14),
        label: `Op ${index}`,
        name: toolName,
        params: {
          field_name: {
            description: `Field name ${index}`.repeat(12),
            required: true,
            type: 'string',
          },
          mode: {
            enum: ['draft', 'published', 'archived'],
            type: 'string',
          },
        },
        readonly: index % 2 === 0,
      };
    });

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.large',
      },
    });

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    requireElement(
      sendButton,
      'Expected send button in screenshot operation test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    const routedContext = routeMessageMock.mock.calls[0]?.[2] as null | {
      page_data?: {
        entity_description?: string;
        navigation_catalog?: Array<{
          page_key?: string;
          path?: string;
          title?: string;
        }>;
        navigation_context?: {
          page_key?: string;
          path?: string;
        };
      };
      page_key?: string;
      page_title?: string;
    };
    expect(routedContext?.page_key).toBe('tenant.demo.large');
    expect(routedContext?.page_title).toBe('Large Demo Page');
    expect(routedContext?.page_data).toMatchObject({
      entity_description: 'Large demo runtime page',
      navigation_catalog: [
        {
          page_key: 'tenant.dashboard',
          path: '/tenant/dashboard',
          title: 'Dashboard',
        },
        {
          page_key: 'tenant.ai.agents',
          path: '/tenant/ai/agents',
          title: 'Agents',
        },
      ],
      navigation_context: {
        page_key: 'tenant.ai.agents',
        path: '/tenant/ai/agents',
      },
    });
    expect('suggested_tools' in (routedContext ?? {})).toBe(false);

    const diagnosticsTrigger = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-trigger"]',
    ) as HTMLDivElement | null;
    expect(diagnosticsTrigger).toBeTruthy();
    diagnosticsTrigger?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    );
    await flushPromises();
    expect(
      document.body.querySelector(
        '[data-testid="ai-panel-page-ai-diagnostics"]',
      ),
    ).toBeFalsy();

    wrapper.unmount();
  });

  it('shows page AI diagnostics only when tenant diagnostics are explicitly enabled', async () => {
    publicConfigState.tenantConfig = {
      features: {
        show_diagnostics: true,
      },
    };
    pageContextValue.value = {
      page_key: 'tenant.demo.diagnostics',
      page_title: 'Diagnostics Demo',
      surface_stack: [
        {
          kind: 'page',
          surface_id: 'surface-root',
          title: 'Diagnostics Demo',
        },
      ],
      ui_epoch: 2,
    };
    pageOperationsValue.value = [
      { name: 'ui_get_snapshot', label: 'Snapshot', readonly: true },
    ];

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.diagnostics',
      },
    });

    await flushPromises();

    const diagnosticsTrigger = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-trigger"]',
    ) as HTMLDivElement | null;
    expect(diagnosticsTrigger).toBeTruthy();
    diagnosticsTrigger?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    );
    await flushPromises();

    expect(
      document.body.querySelector(
        '[data-testid="ai-panel-page-ai-diagnostics"]',
      ),
    ).toBeTruthy();

    wrapper.unmount();
  });

  it('keeps screenshot runtime page context thin for backend gating', async () => {
    inputMessageValue.value = 'inspect this page';
    supportsVisionValue.value = false;
    pageContextValue.value = {
      page_key: 'tenant.demo.visual',
      page_title: 'Visual Demo',
      page_data: {},
    };
    pageOperationsValue.value = [
      {
        label: 'Capture Screenshot',
        name: 'ui_get_snapshot',
        readonly: true,
      },
      { label: 'Read View', name: 'ui_list_interactables', readonly: true },
    ];

    const wrapper = mountPanel({
      props: {
        pageContextKey: 'tenant.demo.visual',
      },
    });

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    requireElement(
      sendButton,
      'Expected send button in screenshot capability test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    const routedContext = routeMessageMock.mock.calls[0]?.[2] as null | Record<
      string,
      unknown
    >;
    expect(routedContext).toBeTruthy();
    expect('suggested_tools' in (routedContext ?? {})).toBe(false);

    wrapper.unmount();
  });

  it('does not fall back to current agent when image reroute fails', async () => {
    activeConversationIdValue.value = 10;
    selectedAgentIdValue.value = 2;
    inputMessageValue.value = 'look at this';
    pendingAttachmentsValue.value = [{ type: 'image' }];
    routeMessageMock.mockRejectedValueOnce(new Error('no vision agent'));

    const wrapper = mountPanel();

    await flushPromises();
    const rerouteButton = document.body.querySelector(
      'button[aria-label="common.globalAiChat.rerouteThisTurn"]',
    );
    const sendButton = document.body.querySelector('button.send-btn');
    requireElement(
      rerouteButton,
      'Expected reroute button in image reroute failure test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    requireElement(
      sendButton,
      'Expected send button in image reroute failure test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).toHaveBeenCalledOnce();
    expect(routeMessageMock.mock.calls[0]?.[4]).toBe(true);
    expect(sendMessageMock).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('routes attachment-only audio messages with placeholder text and attachment flags', async () => {
    activeConversationIdValue.value = null;
    selectedAgentIdValue.value = 1;
    inputMessageValue.value = '';
    pendingAttachmentsValue.value = [{ type: 'audio' }];

    const wrapper = mountPanel();

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    requireElement(
      sendButton,
      'Expected send button in audio attachment routing test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).toHaveBeenCalledOnce();
    expect(routeMessageMock.mock.calls[0]?.[0]).toBe(' ');
    expect(routeMessageMock.mock.calls[0]?.[3]).toEqual({
      hasAudioAttachments: true,
      hasFileAttachments: false,
      hasImageAttachments: false,
      hasVideoAttachments: false,
    });
    expect(sendMessageMock).toHaveBeenCalledWith({
      agentId: 1,
      pageContext: null,
    });

    wrapper.unmount();
  });

  it('toggles the send button disabled state with composer input changes', async () => {
    const wrapper = mountPanel();

    await flushPanel();

    const composerInput = requireElement(
      document.body.querySelector('[data-testid="ai-chat-input"]'),
      'Expected composer input for send button state test',
    ) as HTMLTextAreaElement;

    let sendButton = requireElement(
      document.body.querySelector('button.send-btn'),
      'Expected send button for composer input state test',
    ) as HTMLButtonElement;
    expect(sendButton.hasAttribute('disabled')).toBe(true);

    composerInput.value = 'hello composer';
    composerInput.dispatchEvent(new Event('input', { bubbles: true }));
    await flushPanel();

    sendButton = requireElement(
      document.body.querySelector('button.send-btn'),
      'Expected send button after composer input update',
    ) as HTMLButtonElement;
    expect(sendButton.hasAttribute('disabled')).toBe(false);

    composerInput.value = '';
    composerInput.dispatchEvent(new Event('input', { bubbles: true }));
    await flushPanel();

    sendButton = requireElement(
      document.body.querySelector('button.send-btn'),
      'Expected send button after clearing composer input',
    ) as HTMLButtonElement;
    expect(sendButton.hasAttribute('disabled')).toBe(true);

    wrapper.unmount();
  });

  it('removes selected KB chips from the current turn via the composer controls', async () => {
    composerInteractionState.agentKBBindings.value = [
      {
        kb_name: 'Knowledge Base A',
        knowledge_base_id: 101,
      },
    ];
    composerInteractionState.selectedKBIds.value = [101];

    const wrapper = mountPanel();

    await flushPanel();

    expect(document.body.textContent).toContain('Knowledge Base A');
    const removeKbButton = requireElement(
      document.body.querySelector(
        'button[aria-label="common.globalAiChat.removeKbFromTurn"]',
      ),
      'Expected remove KB button for current turn chip',
    ) as HTMLButtonElement;

    removeKbButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(
      composerInteractionState.removeSelectedKnowledgeBase,
    ).toHaveBeenCalledWith(101);

    wrapper.unmount();
  });

  it('does not fall back to current agent when audio reroute fails', async () => {
    activeConversationIdValue.value = 10;
    selectedAgentIdValue.value = 2;
    inputMessageValue.value = 'listen to this';
    pendingAttachmentsValue.value = [{ type: 'audio' }];
    routeMessageMock.mockRejectedValueOnce(new Error('no audio model'));

    const wrapper = mountPanel();

    await flushPromises();
    const rerouteButton = document.body.querySelector(
      'button[aria-label="common.globalAiChat.rerouteThisTurn"]',
    );
    const sendButton = document.body.querySelector('button.send-btn');
    requireElement(
      rerouteButton,
      'Expected reroute button in audio reroute failure test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    requireElement(
      sendButton,
      'Expected send button in audio reroute failure test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).toHaveBeenCalledOnce();
    expect(routeMessageMock.mock.calls[0]?.[4]).toBe(true);
    expect(sendMessageMock).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('opens search result urls in a new tab instead of routing them to image preview', async () => {
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null as unknown as Window);

    const wrapper = mountPanel({
      global: {
        stubs: {
          AIChatMessageViewport: defineComponent({
            emits: ['openUrl'],
            template:
              '<button data-testid="search-open-url" @click="$emit(\'openUrl\', \'https://example.com/article\')">open</button>',
          }),
        },
      },
    });

    await flushPanel();

    requireElement(
      document.body.querySelector('[data-testid="search-open-url"]'),
      'Expected open-url trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(openSpy).toHaveBeenCalledWith(
      'https://example.com/article',
      '_blank',
      'noopener,noreferrer',
    );
    expect(document.body.querySelector('.image-preview-stub img')).toBeFalsy();

    openSpy.mockRestore();
    wrapper.unmount();
  });

  it('keeps image urls on the preview lightbox path', async () => {
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null as unknown as Window);

    const wrapper = mountPanel({
      global: {
        stubs: {
          AIChatMessageViewport: defineComponent({
            emits: ['openUrl'],
            template:
              '<button data-testid="image-open-url" @click="$emit(\'openUrl\', \'https://example.com/image.png\')">preview</button>',
          }),
        },
      },
    });

    await flushPanel();

    requireElement(
      document.body.querySelector('[data-testid="image-open-url"]'),
      'Expected image open-url trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(openSpy).not.toHaveBeenCalled();
    const previewImage = document.body.querySelector('.image-preview-stub img');
    expect(previewImage).toBeTruthy();
    expect((previewImage as HTMLImageElement).getAttribute('src')).toBe(
      'https://example.com/image.png',
    );

    openSpy.mockRestore();
    wrapper.unmount();
  });

  it('treats attachment image endpoints as previewable images', async () => {
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null as unknown as Window);

    const wrapper = mountPanel({
      global: {
        stubs: {
          AIChatMessageViewport: defineComponent({
            emits: ['openUrl'],
            template:
              '<button data-testid="attachment-image-open-url" @click="$emit(\'openUrl\', \'/api/public/attachments/42/image?exp=1&sign=abc&token=jwt\')">preview</button>',
          }),
        },
      },
    });

    await flushPanel();

    requireElement(
      document.body.querySelector('[data-testid="attachment-image-open-url"]'),
      'Expected attachment image open-url trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(openSpy).not.toHaveBeenCalled();
    const previewImage = document.body.querySelector('.image-preview-stub img');
    expect(previewImage).toBeTruthy();
    expect((previewImage as HTMLImageElement).getAttribute('src')).toBe(
      'http://localhost:8000/api/public/attachments/42/image?exp=1&sign=abc&token=jwt',
    );

    openSpy.mockRestore();
    wrapper.unmount();
  });
});
