/**
 * AIPanel tool action store tests.
 * AI 面板工具动作状态测试。
 */
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAIPanelStore } from '../ai-panel';

describe('useAIPanelStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('defaults to panel mode', () => {
    const store = useAIPanelStore();

    expect(store.mode).toBe('panel');
  });

  it('auto-cleans resolved tool actions after a short grace period', async () => {
    const store = useAIPanelStore();
    const confirmation = store.requestToolActionConfirmation({
      invokeId: 'op-1',
      pageKey: 'admin.ai.agents',
      operationName: 'create_record',
      operationLabel: '新建记录',
      operationDescription: '打开新建表单',
      params: {},
      toolCallId: 'tc-1',
    });

    expect(store.pendingToolActions).toHaveLength(1);

    store.resolveToolAction('op-1', true);
    await expect(confirmation).resolves.toBe(true);

    expect(store.pendingToolActions).toHaveLength(1);
    vi.advanceTimersByTime(1500);

    expect(store.pendingToolActions).toHaveLength(0);
  });

  it('clearResolvedToolActions keeps unresolved actions intact', () => {
    const store = useAIPanelStore();

    void store.requestToolActionConfirmation({
      invokeId: 'resolved-op',
      pageKey: 'admin.ai.agents',
      operationName: 'create_record',
      operationLabel: '新建记录',
      operationDescription: '打开新建表单',
      params: {},
    });
    void store.requestToolActionConfirmation({
      invokeId: 'pending-op',
      pageKey: 'admin.ai.agents',
      operationName: 'edit_record',
      operationLabel: '编辑记录',
      operationDescription: '打开编辑表单',
      params: {},
    });

    store.resolveToolAction('resolved-op', false);
    store.clearResolvedToolActions();

    expect(store.pendingToolActions.map((op) => op.invokeId)).toEqual([
      'pending-op',
    ]);
  });
});
