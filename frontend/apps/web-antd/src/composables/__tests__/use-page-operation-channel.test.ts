/**
 * Page session room recovery tests.
 * 页面会话房间自愈测试。
 */
import { effectScope, nextTick, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const connected = ref(false);
const pageSessionId = ref<null | string>('page-session-1');
const emit = vi.fn();
const registerHandler = vi.fn();
const unregisterHandler = vi.fn();

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
}));

vi.mock('#/composables/use-page-session', () => ({
  getActivePageSessionId: () => pageSessionId.value,
}));

vi.mock('@vben/locales', () => ({
  $t: (key: string) => key,
}));

import { usePageOperationChannel } from '../use-page-operation-channel';

describe('usePageOperationChannel', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    connected.value = false;
    pageSessionId.value = 'page-session-1';
    emit.mockClear();
    registerHandler.mockClear();
    unregisterHandler.mockClear();
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
});
