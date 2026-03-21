/**
 * Page session room recovery tests.
 * 页面会话房间自愈测试。
 */
import { effectScope, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const {
  connected,
  currentPageAIExecutionPolicy,
  emit,
  pageSessionId,
  registerHandler,
  unregisterHandler,
} = vi.hoisted(() => ({
  connected: (require('vue') as typeof import('vue')).ref(false),
  currentPageAIExecutionPolicy: (require('vue') as typeof import('vue')).ref({
      disabledCapabilities: [] as string[],
      disabledOperations: [] as string[],
      mode: 'operate' as const,
      pageContextKey: 'admin.ai.agents',
    }),
  emit: vi.fn(),
  pageSessionId: (require('vue') as typeof import('vue')).ref(
    'page-session-1' as null | string,
  ),
  registerHandler: vi.fn(),
  unregisterHandler: vi.fn(),
}));

vi.mock('#/store', () => ({
  useSocketIOStore: () => ({
    get isConnected() {
      return connected.value;
    },
    emit,
    registerHandler,
    unregisterHandler,
  }),
}));

vi.mock('#/store/shared/ai-panel', () => ({
  useAIPanelStore: () => ({
    open: vi.fn(),
    requestPageOpConfirmation: vi.fn(),
    resolvePageOp: vi.fn(),
  }),
}));

vi.mock('#/components/business/ai-slide-panel', () => ({
  normalizePageKey: () => 'admin.ai.agents',
}));

vi.mock('#/components/business/ai-slide-panel/page-operation-registry', () => ({
  executePageOperation: vi.fn(),
  findPageOperation: vi.fn(),
  listPageOperations: vi.fn(),
}));

vi.mock('#/composables/use-page-session', () => ({
  getActivePageSessionId: () => pageSessionId.value,
}));

vi.mock('#/composables/use-ai-page-policy', () => ({
  currentPageAIExecutionPolicy,
}));

vi.mock('@vben/locales', () => ({
  $t: (key: string) => key,
}));

import { usePageOperationChannel } from '../use-page-operation-channel';
import {
  executePageOperation,
  findPageOperation,
  listPageOperations,
} from '#/components/business/ai-slide-panel/page-operation-registry';

describe('usePageOperationChannel', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    connected.value = false;
    pageSessionId.value = 'page-session-1';
    emit.mockClear();
    registerHandler.mockClear();
    unregisterHandler.mockClear();
    currentPageAIExecutionPolicy.value = {
      disabledCapabilities: [],
      disabledOperations: [],
      mode: 'operate',
      pageContextKey: 'admin.ai.agents',
    };
    vi.mocked(executePageOperation).mockReset();
    vi.mocked(findPageOperation).mockReset();
    vi.mocked(listPageOperations).mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('retries room join after reconnect and forces rejoin on focus', async () => {
    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    expect(registerHandler).toHaveBeenCalledOnce();

    connected.value = true;
    await nextTick();
    vi.advanceTimersByTime(1300);

    const reconnectJoins = emit.mock.calls.filter(
      ([event]) => event === 'page_session_join',
    );
    expect(reconnectJoins).toHaveLength(3);
    expect(reconnectJoins[0]?.[1]).toEqual({
      page_key: 'admin.ai.agents',
      page_session_id: 'page-session-1',
    });

    emit.mockClear();
    window.dispatchEvent(new Event('focus'));

    expect(emit).toHaveBeenCalledWith('page_session_join', {
      page_key: 'admin.ai.agents',
      page_session_id: 'page-session-1',
    });

    scope.stop();
  });

  it('leaves the old room when page_session_id changes and unregisters on dispose', async () => {
    connected.value = true;

    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    await nextTick();
    vi.advanceTimersByTime(1300);
    emit.mockClear();

    pageSessionId.value = 'page-session-2';
    await nextTick();
    vi.advanceTimersByTime(0);

    expect(emit).toHaveBeenNthCalledWith(1, 'page_session_leave', {
      page_session_id: 'page-session-1',
    });
    expect(emit).toHaveBeenNthCalledWith(2, 'page_session_join', {
      page_key: 'admin.ai.agents',
      page_session_id: 'page-session-2',
    });

    emit.mockClear();
    scope.stop();

    expect(unregisterHandler).toHaveBeenCalledOnce();
    expect(emit).toHaveBeenCalledWith('page_session_leave', {
      page_session_id: 'page-session-2',
    });
  });

  it('rejects operations disabled by current page policy before execution', async () => {
    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    currentPageAIExecutionPolicy.value = {
      disabledCapabilities: ['search'],
      disabledOperations: [],
      mode: 'operate',
      pageContextKey: 'admin.ai.agents',
    };
    vi.mocked(findPageOperation).mockReturnValue({
      description: 'Search items',
      label: 'Search',
      name: 'search',
      readonly: true,
    });
    vi.mocked(listPageOperations).mockReturnValue([
      {
        description: 'Search items',
        label: 'Search',
        name: 'search',
        readonly: true,
      },
    ]);

    const invokeHandler = registerHandler.mock.calls[0]?.[1] as
      | ((data: unknown) => Promise<void>)
      | undefined;

    await invokeHandler?.({
      invoke_id: 'op-1',
      operation_name: 'search',
      page_key: 'admin.ai.agents',
      params: {},
      requires_confirmation: false,
    });

    expect(executePageOperation).not.toHaveBeenCalled();
    expect(emit).toHaveBeenCalledWith(
      'page_operation_result',
      expect.objectContaining({
        error_type: 'disabled_by_policy',
        invoke_id: 'op-1',
        success: false,
      }),
    );

    scope.stop();
  });
});
