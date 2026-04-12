// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
/**
 * AIChatSlidePanel component render tests: confirmCountdown in real component.
 * AIChatSlidePanel 组件挂载测试：倒计时文案在真实组件中渲染。
 *
 * 与 countdown-display.test.ts（纯逻辑单测）互补，覆盖“组件渲染层”。
 */
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AIChatSlidePanel from '../AIChatSlidePanel.vue';
import {
  activeConversationIdValue,
  antMessageMocks,
  cleanupPanelDom,
  composerInteractionState,
  createAIPanelStore,
  createPanelMountOptions,
  createRichTextMessage,
  createRichTextTask,
  createSourceEditorMock,
  flushPanel,
  inputMessageValue,
  loadConversationMessagesMock,
  mountRichTextOrchestrationHarness,
  pageContextValue,
  pageOperationsValue,
  pendingAttachmentsValue,
  pendingPageOpsValue,
  requireElement,
  resetPanelState,
  routeMessageMock,
  selectedAgentIdValue,
  sendMessageMock,
  sourceEditorMockState,
  startNewConversationMock,
  supportsVisionValue,
  useAIChatState,
  visible,
} from './ai-chat-slide-panel-test-helpers';
let aiPanelStore: ReturnType<typeof createAIPanelStore>;

vi.mock('@vben/icons', async () => {
  const { createIconifyMock } = await import('./ai-chat-slide-panel-test-helpers');
  return createIconifyMock();
});
vi.mock('#/utils/image', async () => {
  const { createImageMock } = await import('./ai-chat-slide-panel-test-helpers');
  return createImageMock();
});
vi.mock('ant-design-vue', async () => {
  const { createAntDesignVueMock } = await import(
    './ai-chat-slide-panel-test-helpers'
  );
  return createAntDesignVueMock();
});

vi.mock('#/store', () => ({
  useAIPanelStore: () => aiPanelStore,
}));

vi.mock('#/store/shared/public-config', () => ({
  usePublicConfigStore: () => ({
    platformConfig: { brand: { siteName: 'Test' } },
    tenantConfig: null,
  }),
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
  const { createUseAIChatMock } = await import(
    './ai-chat-slide-panel-test-helpers'
  );
  return createUseAIChatMock();
});

vi.mock(
  '#/components/business/rich-text-editor/sourceEditorRegistry',
  async () => {
    const { createSourceEditorRegistryMock } = await import(
      './ai-chat-slide-panel-test-helpers'
    );
    return createSourceEditorRegistryMock();
  },
);

vi.mock('../use-agent-router', async () => {
  const { createUseAgentRouterMock } = await import(
    './ai-chat-slide-panel-test-helpers'
  );
  return createUseAgentRouterMock();
});
vi.mock('#/composables/use-modal-detector', async () => {
  const { createUseModalDetectorMock } = await import(
    './ai-chat-slide-panel-test-helpers'
  );
  return createUseModalDetectorMock();
});
vi.mock('#/composables/use-page-session', async () => {
  const { createUsePageSessionMock } = await import(
    './ai-chat-slide-panel-test-helpers'
  );
  return createUsePageSessionMock();
});
vi.mock('#/composables/use-page-screenshot', async () => {
  const { createUsePageScreenshotMock } = await import(
    './ai-chat-slide-panel-test-helpers'
  );
  return createUsePageScreenshotMock();
});
vi.mock('#/composables/use-form-state-tracker', async () => {
  const { createFormStateTrackerMock } = await import(
    './ai-chat-slide-panel-test-helpers'
  );
  return createFormStateTrackerMock();
});
vi.mock('#/components/business/ai-runtime/runtime-bridge', async () => {
  const { createRuntimeBridgeMock } = await import(
    './ai-chat-slide-panel-test-helpers'
  );
  return createRuntimeBridgeMock();
});

const mountPanel = (
  overrides?: Parameters<typeof createPanelMountOptions>[0],
) => mount(AIChatSlidePanel, createPanelMountOptions(overrides));

describe('aIChatSlidePanel (component mount)', () => {
  beforeEach(() => {
    aiPanelStore = resetPanelState();
  });

  afterEach(() => {
    cleanupPanelDom();
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

  it('renders header actions and more-actions trigger without reserving an empty status rail', async () => {
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
      document.body.querySelector('[data-testid="ai-panel-toolbar-row"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelector(
        'button[aria-label="common.aiPanel.moreActions"]',
      ),
    ).toBeTruthy();

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
      { name: 'op-1', label: 'Refresh', readonly: true },
      { name: 'op-2', label: 'Open Drawer', readonly: false },
      { name: 'op-3', label: 'Save Draft', readonly: false },
      { name: 'op-4', label: 'Search Records', readonly: true },
      { name: 'op-5', label: 'Assign Owner', readonly: false },
      { name: 'op-6', label: 'Export View', readonly: true },
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
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiOperationCount',
    );
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiDiagnostics',
    );
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
    ).toHaveLength(6);

    toggleButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();

    wrapper.unmount();
  });

  it('does not reserve a blank header slot row when no status badge is shown', async () => {
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
    expect(toolbarRow?.contains(headerActions)).toBe(true);

    wrapper.unmount();
  });

  it('mounts safely when page context exists before runtime size guards initialize', async () => {
    pageContextValue.value = {
      page_key: 'tenant.demo.page',
      page_title: 'admin.system.codegen.name',
      page_data: {
        list_summary: {
          columns: ['name'],
          row_count: 1,
          sample_rows: [{ name: 'Codegen' }],
        },
      },
    };
    pageOperationsValue.value = [
      { name: 'op-1', label: 'Inspect', readonly: true },
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
    expect(antMessageMocks.error).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('shows fallback-only page AI support with a downgraded awareness badge', async () => {
    pageContextValue.value = {
      page_key: 'tenant.demo.fallback',
      page_title: 'Fallback Only',
      page_data: {
        source: 'dom_snapshot',
        tables: [{ columns: ['name'], row_count: 1 }],
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
    ).toBeTruthy();
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiDiagSource',
    );

    wrapper.unmount();
  });

  it('keeps routed page context thin while preserving suggested ui tools', async () => {
    inputMessageValue.value = 'inspect this page';
    pageContextValue.value = {
      page_key: 'tenant.demo.large',
      page_title: 'Large Demo Page',
      page_data: {
        document_body_text: 'x'.repeat(6400),
        form_fields: Object.fromEntries(
          Array.from({ length: 24 }, (_, index) => [
            `field_${index}`,
            {
              component: 'input',
              description: `Field ${index} `.repeat(18),
              options: Array.from({ length: 6 }, (__, optionIndex) => ({
                label: `Option ${index}-${optionIndex}`,
                value: `${index}-${optionIndex}`,
              })),
              required: index % 2 === 0,
              type: 'string',
            },
          ]),
        ),
        list_summary: {
          sample_rows: Array.from({ length: 5 }, (_, index) => ({
            description: `Row ${index} `.repeat(32),
            name: `Record ${index}`,
          })),
          total_rows: 50,
        },
      },
    };
    pageOperationsValue.value = Array.from({ length: 16 }, (_, index) => ({
      description: `Operation ${index} `.repeat(14),
      label: `Op ${index}`,
      name: `op_${index}`,
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
    }));

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
      page_data?: Record<string, unknown>;
      page_key?: string;
      page_title?: string;
      suggested_tools?: {
        primary?: string[];
        secondary?: string[];
      };
    };
    expect(routedContext?.page_key).toBe('tenant.demo.large');
    expect(routedContext?.page_title).toBe('Large Demo Page');
    expect(routedContext?.page_data).toBeUndefined();
    const suggestedToolNames = [
      ...(routedContext?.suggested_tools?.primary ?? []),
      ...(routedContext?.suggested_tools?.secondary ?? []),
    ];
    expect(suggestedToolNames.length).toBeGreaterThan(0);
    expect(
      suggestedToolNames.every((toolName) => toolName.startsWith('ui_')),
    ).toBe(true);

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

  it('keeps screenshot runtime tools in routed page context for backend runtime gating', async () => {
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
        name: 'capture_screenshot',
        readonly: true,
      },
      { label: 'Read View', name: 'read_current_view', readonly: true },
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

    const routedContext = routeMessageMock.mock.calls[0]?.[2] as null | {
      suggested_tools?: {
        primary?: string[];
        secondary?: string[];
      };
    };
    const toolNames = [
      ...(routedContext?.suggested_tools?.primary ?? []),
      ...(routedContext?.suggested_tools?.secondary ?? []),
    ];
    expect(toolNames).toContain('ui_get_snapshot');
    expect(toolNames).toContain('ui_list_interactables');

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

  it('dispatches a pending rich text task after reopening from the closed panel state', async () => {
    visible.value = false;
    const task = createRichTextTask({
      message: '[Rich Text Task] Rewrite from closed panel',
      taskId: 'rich-text-closed-task',
    });
    sendMessageMock.mockImplementation(async ({ agentId, routeSource }) => {
      useAIChatState.chatMessages.value = [
        ...useAIChatState.chatMessages.value,
        {
          clientKey: 'assistant-rich-text-closed',
          content: 'Draft ready',
          role: 'assistant',
          agent_id: agentId ?? null,
          routeSource: routeSource ?? null,
        },
      ];
      return true;
    });
    aiPanelStore = createAIPanelStore();
    aiPanelStore.visible = false;
    aiPanelStore.pendingRichTextTask = task;

    const wrapper = mountPanel();

    await flushPanel();

    expect(aiPanelStore.open).toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 1,
        pageContext: null,
        routeSource: 'rich_text_ai',
      }),
    );
    expect(aiPanelStore.clearPendingRichTextTask).toHaveBeenCalledWith(
      'rich-text-closed-task',
    );
    expect(useAIChatState.chatMessages.value[0]?.richTextAI?.taskId).toBe(
      'rich-text-closed-task',
    );

    wrapper.unmount();
  });

  it('queues the latest pending rich text task while streaming', async () => {
    useAIChatState.streaming.value = true;

    const wrapper = mountPanel();

    await flushPanel();

    aiPanelStore.pendingRichTextTask = createRichTextTask({
      message: '[Rich Text Task] First queued draft',
      taskId: 'rich-text-queue-1',
    });
    await flushPanel();

    aiPanelStore.pendingRichTextTask = createRichTextTask({
      draft: {
        html: '<p>Second</p>',
        markdown: 'Second',
        plainText: 'Second',
      },
      message: '[Rich Text Task] Latest queued draft',
      taskId: 'rich-text-queue-2',
    });
    await flushPanel();

    expect(aiPanelStore.queueRichTextTask).toHaveBeenCalledTimes(2);
    expect(aiPanelStore.queueRichTextTask).toHaveBeenLastCalledWith(
      expect.objectContaining({
        taskId: 'rich-text-queue-2',
      }),
    );
    expect(aiPanelStore.queuedRichTextTask?.taskId).toBe('rich-text-queue-2');
    expect(aiPanelStore.pendingRichTextTask).toBeNull();
    expect(sendMessageMock).not.toHaveBeenCalled();
    expect(antMessageMocks.info).toHaveBeenCalledWith(
      'common.richTextTaskQueued',
    );

    wrapper.unmount();
  });

  it('flushes the queued rich text task once the panel returns to idle', async () => {
    useAIChatState.streaming.value = true;
    sendMessageMock.mockImplementation(async ({ agentId, routeSource }) => {
      useAIChatState.chatMessages.value = [
        ...useAIChatState.chatMessages.value,
        {
          clientKey: 'assistant-rich-text-queued',
          content: 'Queued draft ready',
          role: 'assistant',
          agent_id: agentId ?? null,
          routeSource: routeSource ?? null,
        },
      ];
      return true;
    });

    const wrapper = mountPanel();

    await flushPanel();

    aiPanelStore.pendingRichTextTask = createRichTextTask({
      message: '[Rich Text Task] Flush queued draft',
      taskId: 'rich-text-flush-1',
    });
    await flushPanel();

    expect(aiPanelStore.queuedRichTextTask?.taskId).toBe('rich-text-flush-1');

    aiPanelStore.clearPendingRichTextTask.mockClear();
    aiPanelStore.promoteQueuedRichTextTask.mockClear();
    sendMessageMock.mockClear();
    useAIChatState.streaming.value = false;

    await flushPanel();

    expect(aiPanelStore.promoteQueuedRichTextTask).toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 1,
        pageContext: null,
        routeSource: 'rich_text_ai',
      }),
    );
    expect(aiPanelStore.clearPendingRichTextTask).toHaveBeenCalledWith(
      'rich-text-flush-1',
    );
    expect(
      useAIChatState.chatMessages.value.some(
        (message) => message.richTextAI?.taskId === 'rich-text-flush-1',
      ),
    ).toBe(true);

    wrapper.unmount();
  });

  it('wires rich text apply, discard, and undo events through the slide panel', async () => {
    activeConversationIdValue.value = 42;
    const task = createRichTextTask({
      taskId: 'rich-text-actions',
    });
    const sourceEditor = createSourceEditorMock(task);
    useAIChatState.chatMessages.value = [createRichTextMessage(task)];

    const wrapper = mountPanel({
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemStub',
            props: {
              index: {
                required: true,
                type: Number,
              },
              msg: {
                required: true,
                type: Object,
              },
              richTextState: {
                default: null,
                type: Object,
              },
            },
            emits: ['rich-text-apply', 'rich-text-discard', 'rich-text-undo'],
            template: `
              <div data-testid="rich-text-message-item">
                <div data-testid="rich-text-state">
                  {{
                    JSON.stringify({
                      canUndo: richTextState?.canUndo ?? false,
                      discarded: richTextState?.discarded ?? false,
                    })
                  }}
                </div>
                <button
                  data-testid="rich-text-discard-btn"
                  @click="$emit('rich-text-discard', index)"
                />
                <button
                  data-testid="rich-text-apply-btn"
                  @click="$emit('rich-text-apply', index, 'replace_selection', 'formatted')"
                />
                <button
                  data-testid="rich-text-undo-btn"
                  @click="$emit('rich-text-undo', index)"
                />
              </div>
            `,
          }),
        },
      },
    });

    await flushPanel();

    const getRichTextStateText = () =>
      requireElement(
        document.body.querySelector('[data-testid="rich-text-state"]'),
        'Expected rich text state output',
      ).textContent ?? '';
    expect(getRichTextStateText()).toContain('"discarded":false');
    expect(getRichTextStateText()).toContain('"canUndo":false');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-discard-btn"]'),
      'Expected discard trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(getRichTextStateText()).toContain('"discarded":true');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-apply-btn"]'),
      'Expected apply trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(sourceEditorMockState.prepareRichTextContent).toHaveBeenCalledWith(
      'Draft',
      { mode: 'formatted' },
    );
    expect(sourceEditor.replaceRange).toHaveBeenCalledWith(
      4,
      12,
      'prepared::formatted::Draft',
    );
    expect(aiPanelStore.markRichTextTaskApplied).toHaveBeenCalledWith(
      'rich-text-actions',
      {
        conversationId: 42,
        lastAppliedMode: 'formatted',
      },
    );
    expect(getRichTextStateText()).toContain('"discarded":false');
    expect(getRichTextStateText()).toContain('"canUndo":true');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-undo-btn"]'),
      'Expected undo trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(sourceEditor.undo).toHaveBeenCalled();
    expect(aiPanelStore.markRichTextTaskUndone).toHaveBeenCalledWith(
      'rich-text-actions',
      {
        conversationId: 42,
        lastAppliedMode: 'formatted',
      },
    );
    expect(getRichTextStateText()).toContain('"canUndo":false');

    wrapper.unmount();
  });

  it('invalidates rich text undo once the active conversation changes', async () => {
    const task = createRichTextTask({
      taskId: 'rich-text-conversation-switch',
    });
    createSourceEditorMock(task);
    const { activeConversationId, wrapper } = await mountRichTextOrchestrationHarness(
      {
        activeConversationId: 42,
        chatMessages: [createRichTextMessage(task)],
      },
    );

    await flushPanel();

    const harness = wrapper.vm as unknown as {
      getRichTextDraftState: (index: number) => null | { canUndo: boolean };
      onRichTextApply: (
        index: number,
        target: 'replace_selection',
        mode: 'formatted',
      ) => void;
    };

    harness.onRichTextApply(0, 'replace_selection', 'formatted');
    await flushPanel();

    expect(harness.getRichTextDraftState(0)?.canUndo).toBe(true);

    activeConversationId.value = 99;
    await flushPanel();

    expect(harness.getRichTextDraftState(0)?.canUndo).toBe(false);

    wrapper.unmount();
  });

  it('keeps reopened rich text history messages read-only', async () => {
    const historyTask = createRichTextTask({
      messageClientKey: undefined,
      taskId: 'rich-text-history-readonly',
    });
    createSourceEditorMock(historyTask);
    const { wrapper } = await mountRichTextOrchestrationHarness({
      chatMessages: [
        createRichTextMessage(historyTask, {
          richTextAI: {
            ...historyTask,
            messageClientKey: undefined,
          },
        }),
      ],
    });

    await flushPanel();

    const harness = wrapper.vm as unknown as {
      getRichTextDraftState: (index: number) => unknown;
    };
    expect(harness.getRichTextDraftState(0)).toBeNull();

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
