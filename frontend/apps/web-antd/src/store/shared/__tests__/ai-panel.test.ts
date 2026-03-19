/**
 * AIPanel page operation store tests.
 * AI 面板页面操作状态测试。
 */
import { createPinia, setActivePinia } from 'pinia';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAIPanelStore } from '../ai-panel';

describe('useAIPanelStore page operations', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('auto-cleans resolved page operations after a short grace period', async () => {
    const store = useAIPanelStore();
    const confirmation = store.requestPageOpConfirmation({
      invokeId: 'op-1',
      pageKey: 'admin.ai.agents',
      operationName: 'create_record',
      operationLabel: '新建记录',
      operationDescription: '打开新建表单',
      params: {},
      toolCallId: 'tc-1',
    });

    expect(store.pendingPageOps).toHaveLength(1);

    store.resolvePageOp('op-1', true);
    await expect(confirmation).resolves.toBe(true);

    expect(store.pendingPageOps).toHaveLength(1);
    vi.advanceTimersByTime(1500);

    expect(store.pendingPageOps).toHaveLength(0);
  });

  it('clearResolvedPageOps keeps unresolved operations intact', () => {
    const store = useAIPanelStore();

    void store.requestPageOpConfirmation({
      invokeId: 'resolved-op',
      pageKey: 'admin.ai.agents',
      operationName: 'create_record',
      operationLabel: '新建记录',
      operationDescription: '打开新建表单',
      params: {},
    });
    void store.requestPageOpConfirmation({
      invokeId: 'pending-op',
      pageKey: 'admin.ai.agents',
      operationName: 'edit_record',
      operationLabel: '编辑记录',
      operationDescription: '打开编辑表单',
      params: {},
    });

    store.resolvePageOp('resolved-op', false);
    store.clearResolvedPageOps();

    expect(store.pendingPageOps.map((op) => op.invokeId)).toEqual(['pending-op']);
  });
});
