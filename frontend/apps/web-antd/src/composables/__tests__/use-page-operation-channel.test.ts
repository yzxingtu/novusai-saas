/* eslint-disable @typescript-eslint/no-require-imports, @typescript-eslint/no-var-requires, unicorn/prefer-module */
// @vitest-environment happy-dom
/**
 * Page session room recovery tests.
 * 页面会话房间自愈测试。
 */
import { effectScope, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  executePageOperation,
  findPageOperation,
  listPageOperations,
} from '#/components/business/ai-slide-panel/page-operation-registry';

import { usePageOperationChannel } from '../use-page-operation-channel';

const {
  connected,
  currentPageAIExecutionPolicy,
  emit,
  formIsOpenWithFallback,
  isActiveConversationTrusted,
  openAIPanel,
  pageSessionId,
  requestPageOpConfirmation,
  registerHandler,
  resolvePageOp,
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
  formIsOpenWithFallback: vi.fn(),
  isActiveConversationTrusted: vi.fn(),
  openAIPanel: vi.fn(),
  pageSessionId: (require('vue') as typeof import('vue')).ref(
    'page-session-1' as null | string,
  ),
  requestPageOpConfirmation: vi.fn(),
  registerHandler: vi.fn(),
  resolvePageOp: vi.fn(),
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
    isActiveConversationTrusted,
    open: openAIPanel,
    requestPageOpConfirmation,
    resolvePageOp,
  }),
}));

vi.mock('#/components/business/ai-slide-panel', () => ({
  normalizePageKey: (value?: string) =>
    String(value ?? '')
      .replace(/^\//, '')
      .replaceAll('/', '.'),
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

vi.mock('#/composables/use-form-state-tracker', () => ({
  formStateTracker: {
    isOpenWithFallback: formIsOpenWithFallback,
  },
}));

vi.mock('#/composables/use-socketio', () => ({
  getSocketTraceId: () => 'socket-trace-1',
}));

vi.mock('@vben/locales', () => ({
  $t: (key: string) => key,
  loadLocalesMapFromDir: () => ({}),
}));

describe('usePageOperationChannel', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.history.replaceState({}, '', '/admin/ai/agents');
    connected.value = false;
    pageSessionId.value = 'page-session-1';
    emit.mockClear();
    openAIPanel.mockReset();
    registerHandler.mockClear();
    requestPageOpConfirmation.mockReset();
    requestPageOpConfirmation.mockResolvedValue(true);
    resolvePageOp.mockReset();
    formIsOpenWithFallback.mockReset();
    formIsOpenWithFallback.mockReturnValue(false);
    isActiveConversationTrusted.mockReset();
    isActiveConversationTrusted.mockReturnValue(false);
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
      trace_id: 'socket-trace-1',
    });

    emit.mockClear();
    window.dispatchEvent(new Event('focus'));

    expect(emit).toHaveBeenCalledWith('page_session_join', {
      page_key: 'admin.ai.agents',
      page_session_id: 'page-session-1',
      trace_id: 'socket-trace-1',
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
      trace_id: 'socket-trace-1',
    });
    expect(emit).toHaveBeenNthCalledWith(2, 'page_session_join', {
      page_key: 'admin.ai.agents',
      page_session_id: 'page-session-2',
      trace_id: 'socket-trace-1',
    });

    emit.mockClear();
    scope.stop();

    expect(unregisterHandler).toHaveBeenCalledOnce();
    expect(emit).toHaveBeenCalledWith('page_session_leave', {
      page_session_id: 'page-session-2',
      trace_id: 'socket-trace-1',
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
        trace_id: 'socket-trace-1',
      }),
    );

    scope.stop();
  });

  it('rejects operations whose page_key does not match the current active page', async () => {
    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    vi.mocked(findPageOperation).mockReturnValue({
      description: 'Open another page drawer',
      label: 'Open Drawer',
      name: 'open_drawer',
      readonly: false,
    });

    const invokeHandler = registerHandler.mock.calls[0]?.[1] as
      | ((data: unknown) => Promise<void>)
      | undefined;

    await invokeHandler?.({
      invoke_id: 'op-mismatch',
      operation_name: 'open_drawer',
      page_key: 'tenant.ai.other',
      params: {},
      requires_confirmation: false,
    });

    expect(executePageOperation).not.toHaveBeenCalled();
    expect(emit).toHaveBeenCalledWith(
      'page_operation_result',
      expect.objectContaining({
        error_type: 'page_key_mismatch',
        invoke_id: 'op-mismatch',
        success: false,
        trace_id: 'socket-trace-1',
      }),
    );

    scope.stop();
  });

  it('deduplicates duplicate invoke_id events and replays the cached result', async () => {
    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    vi.mocked(findPageOperation).mockReturnValue({
      description: 'Refresh data',
      label: 'Refresh',
      name: 'refresh_list',
      readonly: true,
    });
    vi.mocked(listPageOperations).mockReturnValue([
      {
        description: 'Refresh data',
        label: 'Refresh',
        name: 'refresh_list',
        readonly: true,
      },
    ]);

    let resolveExecution:
      | ((value: { message: string; success: boolean }) => void)
      | undefined;
    const executionPromise = new Promise<{ message: string; success: boolean }>(
      (resolve) => {
        resolveExecution = resolve;
      },
    );
    vi.mocked(executePageOperation).mockReturnValue(executionPromise);

    const invokeHandler = registerHandler.mock.calls[0]?.[1] as
      | ((data: unknown) => Promise<void>)
      | undefined;

    const first = invokeHandler?.({
      invoke_id: 'dup-1',
      operation_name: 'refresh_list',
      page_key: 'admin.ai.agents',
      params: {},
      requires_confirmation: false,
    });
    const second = invokeHandler?.({
      invoke_id: 'dup-1',
      operation_name: 'refresh_list',
      page_key: 'admin.ai.agents',
      params: {},
      requires_confirmation: false,
    });

    expect(executePageOperation).toHaveBeenCalledTimes(1);

    resolveExecution?.({
      success: true,
      message: 'Refreshed once',
    });

    await Promise.all([first, second]);

    const resultEvents = emit.mock.calls.filter(
      ([event, payload]) =>
        event === 'page_operation_result' && payload.invoke_id === 'dup-1',
    );
    expect(resultEvents).toHaveLength(2);
    expect(resultEvents[0]?.[1]).toMatchObject({
      invoke_id: 'dup-1',
      message: 'Refreshed once',
      success: true,
      trace_id: 'socket-trace-1',
    });
    expect(resultEvents[1]?.[1]).toMatchObject({
      invoke_id: 'dup-1',
      message: 'Refreshed once',
      success: true,
      trace_id: 'socket-trace-1',
    });

    scope.stop();
  });

  it('reuses confirmed mutation approval for follow-up fill_form within 60 seconds', async () => {
    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    vi.mocked(findPageOperation).mockImplementation(
      (_pageKey, operationName) => ({
        description: String(operationName),
        label: String(operationName),
        name: String(operationName),
        readonly: false,
      }),
    );
    vi.mocked(listPageOperations).mockReturnValue([
      {
        description: 'create_record',
        label: 'create_record',
        name: 'create_record',
        readonly: false,
      },
      {
        description: 'fill_form',
        label: 'fill_form',
        name: 'fill_form',
        readonly: false,
      },
    ]);
    vi.mocked(executePageOperation).mockResolvedValue({
      success: true,
      message: 'ok',
    });

    const invokeHandler = registerHandler.mock.calls[0]?.[1] as
      | ((data: unknown) => Promise<void>)
      | undefined;

    await invokeHandler?.({
      invoke_id: 'chain-create',
      operation_name: 'create_record',
      page_key: 'admin.ai.agents',
      params: {},
      requires_confirmation: false,
    });

    vi.advanceTimersByTime(59_000);

    await invokeHandler?.({
      invoke_id: 'chain-fill',
      operation_name: 'fill_form',
      page_key: 'admin.ai.agents',
      params: { name: 'demo' },
      requires_confirmation: false,
    });

    expect(requestPageOpConfirmation).toHaveBeenCalledTimes(1);
    expect(executePageOperation).toHaveBeenCalledTimes(2);

    scope.stop();
  });

  it('still requests confirmation for create_record even when a form is already open', async () => {
    formIsOpenWithFallback.mockReturnValue(true);

    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    vi.mocked(findPageOperation).mockReturnValue({
      description: 'Open create form',
      label: 'Create',
      name: 'create_record',
      readonly: false,
    });
    vi.mocked(listPageOperations).mockReturnValue([
      {
        description: 'Open create form',
        label: 'Create',
        name: 'create_record',
        readonly: false,
      },
    ]);
    vi.mocked(executePageOperation).mockResolvedValue({
      success: true,
      message: 'created',
    });

    const invokeHandler = registerHandler.mock.calls[0]?.[1] as
      | ((data: unknown) => Promise<void>)
      | undefined;

    await invokeHandler?.({
      invoke_id: 'open-form-create',
      operation_name: 'create_record',
      page_key: 'admin.ai.agents',
      params: {},
      requires_confirmation: false,
    });

    expect(requestPageOpConfirmation).toHaveBeenCalledTimes(1);
    expect(executePageOperation).toHaveBeenCalledTimes(1);

    scope.stop();
  });

  it('expires chain confirmation after 60 seconds and requests approval again', async () => {
    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    vi.mocked(findPageOperation).mockImplementation(
      (_pageKey, operationName) => ({
        description: String(operationName),
        label: String(operationName),
        name: String(operationName),
        readonly: false,
      }),
    );
    vi.mocked(listPageOperations).mockReturnValue([
      {
        description: 'create_record',
        label: 'create_record',
        name: 'create_record',
        readonly: false,
      },
      {
        description: 'fill_form',
        label: 'fill_form',
        name: 'fill_form',
        readonly: false,
      },
    ]);
    vi.mocked(executePageOperation).mockResolvedValue({
      success: true,
      message: 'ok',
    });

    const invokeHandler = registerHandler.mock.calls[0]?.[1] as
      | ((data: unknown) => Promise<void>)
      | undefined;

    await invokeHandler?.({
      invoke_id: 'expire-create',
      operation_name: 'create_record',
      page_key: 'admin.ai.agents',
      params: {},
      requires_confirmation: false,
    });

    vi.advanceTimersByTime(60_001);

    await invokeHandler?.({
      invoke_id: 'expire-fill',
      operation_name: 'fill_form',
      page_key: 'admin.ai.agents',
      params: { name: 'demo' },
      requires_confirmation: false,
    });

    expect(requestPageOpConfirmation).toHaveBeenCalledTimes(2);
    expect(executePageOperation).toHaveBeenCalledTimes(2);

    scope.stop();
  });

  it('auto-approves mutation page operations when the active conversation is trusted', async () => {
    isActiveConversationTrusted.mockReturnValue(true);

    const scope = effectScope();
    scope.run(() => {
      usePageOperationChannel();
    });

    vi.mocked(findPageOperation).mockReturnValue({
      description: 'Open create form',
      label: 'Create',
      name: 'create_record',
      readonly: false,
    });
    vi.mocked(listPageOperations).mockReturnValue([
      {
        description: 'Open create form',
        label: 'Create',
        name: 'create_record',
        readonly: false,
      },
    ]);
    vi.mocked(executePageOperation).mockResolvedValue({
      success: true,
      message: 'trusted-ok',
    });

    const invokeHandler = registerHandler.mock.calls[0]?.[1] as
      | ((data: unknown) => Promise<void>)
      | undefined;

    await invokeHandler?.({
      invoke_id: 'trusted-create',
      operation_name: 'create_record',
      page_key: 'admin.ai.agents',
      params: {},
      requires_confirmation: false,
    });

    expect(requestPageOpConfirmation).not.toHaveBeenCalled();
    expect(executePageOperation).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith(
      'page_operation_result',
      expect.objectContaining({
        invoke_id: 'trusted-create',
        message: 'trusted-ok',
        success: true,
      }),
    );

    scope.stop();
  });
});
