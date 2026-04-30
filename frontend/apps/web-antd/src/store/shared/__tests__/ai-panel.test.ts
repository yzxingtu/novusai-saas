/**
 * Test type: behavioral
 * Verifies: shared AI panel mode and interaction-update queue ordering after page-operation retirement.
 * Mock strategy: Pinia store runs real; no external transport is mocked.
 *
 * AIPanel shared state tests.
 * AI 面板共享状态测试。
 */
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { useAIPanelStore } from '../ai-panel';

describe('useAIPanelStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('defaults to panel mode', () => {
    const store = useAIPanelStore();

    expect(store.mode).toBe('panel');
  });

  it('queues and consumes interaction updates without page-operation actions', () => {
    const store = useAIPanelStore();

    store.queueInteractionUpdate({
      kind: 'pending_confirmation',
      tool_name: 'web_search',
      value: 'confirm-search',
    });

    expect(store.consumeInteractionUpdates()).toEqual([
      {
        kind: 'pending_confirmation',
        tool_name: 'web_search',
        value: 'confirm-search',
      },
    ]);
    expect(store.consumeInteractionUpdates()).toEqual([]);
  });

  it('restores interaction updates before newer queued updates', () => {
    const store = useAIPanelStore();

    store.queueInteractionUpdate({
      action: 'accepted',
      kind: 'action_buttons',
      tool_name: 'query_records',
    });
    store.restoreInteractionUpdates([
      {
        kind: 'pending_consent',
        tool_name: 'fetch_url',
      },
    ]);

    expect(store.consumeInteractionUpdates()).toEqual([
      {
        kind: 'pending_consent',
        tool_name: 'fetch_url',
      },
      {
        action: 'accepted',
        kind: 'action_buttons',
        tool_name: 'query_records',
      },
    ]);
  });
});
