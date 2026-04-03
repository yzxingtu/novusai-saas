import { effectScope, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  appendCleanup: vi.fn(),
  appendPageOperations: vi.fn(),
  contextCleanup: vi.fn(),
  extrasCleanup: vi.fn(),
  registerPageContext: vi.fn(),
  registerPageContextExtras: vi.fn(),
  registerPageOperations: vi.fn(),
  routeMeta: { value: { title: 'Agents' } as Record<string, unknown> },
  routePath: { value: '/admin/ai/agents' },
  operationsCleanup: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({
    get meta() {
      return mockRefs.routeMeta.value;
    },
    get path() {
      return mockRefs.routePath.value;
    },
  }),
}));

vi.mock('#/components/business/ai-slide-panel', () => ({
  appendPageOperations: mockRefs.appendPageOperations,
  normalizePageKey: (value?: string) =>
    String(value ?? '')
      .replace(/^\//, '')
      .replaceAll('/', '.'),
  registerPageContext: mockRefs.registerPageContext,
  registerPageContextExtras: mockRefs.registerPageContextExtras,
  registerPageOperations: mockRefs.registerPageOperations,
}));

describe('usePageAIRegistration', () => {
  beforeEach(() => {
    mockRefs.appendCleanup.mockReset();
    mockRefs.appendPageOperations.mockReset();
    mockRefs.appendPageOperations.mockReturnValue(mockRefs.appendCleanup);
    mockRefs.contextCleanup.mockReset();
    mockRefs.extrasCleanup.mockReset();
    mockRefs.operationsCleanup.mockReset();
    mockRefs.registerPageContext.mockReset();
    mockRefs.registerPageContext.mockReturnValue(mockRefs.contextCleanup);
    mockRefs.registerPageContextExtras.mockReset();
    mockRefs.registerPageContextExtras.mockReturnValue(mockRefs.extrasCleanup);
    mockRefs.registerPageOperations.mockReset();
    mockRefs.registerPageOperations.mockReturnValue(mockRefs.operationsCleanup);
    mockRefs.routeMeta.value = { title: 'Agents' };
    mockRefs.routePath.value = '/admin/ai/agents';
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('registers primary context and operations with normalized page key', async () => {
    const module = await import('../use-page-ai-registration');
    const scope = effectScope();

    scope.run(() => {
      module.usePageAIRegistration({
        data: { count: 3 },
        entityName: 'Agents',
        operations: [{ label: 'Refresh', name: 'refresh', readonly: true }],
        resource: 'agents',
      });
    });
    await nextTick();

    expect(mockRefs.registerPageContext).toHaveBeenCalledWith(
      'admin.ai.agents',
      expect.any(Function),
    );
    expect(mockRefs.registerPageOperations).toHaveBeenCalledWith(
      'admin.ai.agents',
      [{ label: 'Refresh', name: 'refresh', readonly: true }],
    );

    const resolver = mockRefs.registerPageContext.mock.calls[0]?.[1] as
      | (() => Record<string, unknown>)
      | undefined;
    expect(resolver?.()).toEqual({
      page_key: 'admin.ai.agents',
      page_title: 'Agents',
      page_data: {
        count: 3,
        entity_name: 'Agents',
        resource: 'agents',
      },
    });

    scope.stop();
    expect(mockRefs.contextCleanup).toHaveBeenCalled();
    expect(mockRefs.operationsCleanup).toHaveBeenCalled();
  });

  it('supports extras context and append operation strategies', async () => {
    const module = await import('../use-page-ai-registration');
    const scope = effectScope();

    scope.run(() => {
      module.usePageAIRegistration({
        contextStrategy: 'extras',
        data: { total: 9 },
        entityDescription: 'Agent list',
        operationStrategy: 'append',
        operations: [{ label: 'Search', name: 'search', readonly: true }],
        pageKey: '/custom/page',
      });
    });
    await nextTick();

    expect(mockRefs.registerPageContextExtras).toHaveBeenCalledWith(
      'custom.page',
      expect.any(Function),
    );
    expect(mockRefs.appendPageOperations).toHaveBeenCalledWith(
      'custom.page',
      [{ label: 'Search', name: 'search', readonly: true }],
    );

    const resolver = mockRefs.registerPageContextExtras.mock.calls[0]?.[1] as
      | (() => Record<string, unknown>)
      | undefined;
    expect(resolver?.()).toEqual({
      page_key: 'custom.page',
      page_title: 'Agents',
      page_data: {
        entity_description_append: 'Agent list',
        total: 9,
      },
    });

    scope.stop();
  });

  it('skips registration when disabled is false', async () => {
    const module = await import('../use-page-ai-registration');
    const scope = effectScope();

    scope.run(() => {
      module.usePageAIRegistration({
        enabled: false,
        operations: [{ label: 'Refresh', name: 'refresh', readonly: true }],
      });
    });
    await nextTick();

    expect(mockRefs.registerPageContext).not.toHaveBeenCalled();
    expect(mockRefs.registerPageOperations).not.toHaveBeenCalled();
    scope.stop();
  });

  it('wrapper helpers can register only context or only operations', async () => {
    const module = await import('../use-page-ai-registration');

    const contextScope = effectScope();
    contextScope.run(() => {
      module.usePageAIContext({
        pageKey: '/context-only',
        resource: 'agents',
      });
    });
    await nextTick();

    expect(mockRefs.registerPageContext).toHaveBeenCalled();
    expect(mockRefs.registerPageOperations).not.toHaveBeenCalled();
    contextScope.stop();

    mockRefs.registerPageContext.mockClear();
    mockRefs.registerPageOperations.mockClear();

    const operationScope = effectScope();
    operationScope.run(() => {
      module.usePageAIOperations({
        operations: [{ label: 'Refresh', name: 'refresh', readonly: true }],
        pageKey: '/ops-only',
      });
    });
    await nextTick();

    expect(mockRefs.registerPageContext).not.toHaveBeenCalled();
    expect(mockRefs.registerPageOperations).toHaveBeenCalledWith(
      'ops-only',
      [{ label: 'Refresh', name: 'refresh', readonly: true }],
    );
    operationScope.stop();
  });
});
