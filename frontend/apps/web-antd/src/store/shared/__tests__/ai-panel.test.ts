/**
 * Test type: behavioral
 * Verifies: shared AI panel mode and interaction-update queue ordering.
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

  it('queues and consumes interaction updates independently', () => {
    const store = useAIPanelStore();

    store.queueInteractionUpdate({
      kind: 'pending_confirmation',
      tool_name: 'query_records',
      value: 'confirm-query',
    });

    expect(store.consumeInteractionUpdates()).toEqual([
      {
        kind: 'pending_confirmation',
        tool_name: 'query_records',
        value: 'confirm-query',
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
        tool_name: 'load_record',
      },
    ]);

    expect(store.consumeInteractionUpdates()).toEqual([
      {
        kind: 'pending_consent',
        tool_name: 'load_record',
      },
      {
        action: 'accepted',
        kind: 'action_buttons',
        tool_name: 'query_records',
      },
    ]);
  });

  it('rejects external AI panel context while chat is unavailable', () => {
    const store = useAIPanelStore();

    store.setChatAvailable(false);
    const opened = store.openWithContext({
      agentId: 8,
      conversationId: 12,
      message: 'send later',
    });
    store.queueInteractionUpdate({
      kind: 'pending_confirmation',
      tool_name: 'query_records',
    });

    expect(opened).toBe(false);
    expect(store.visible).toBe(false);
    expect(store.pendingAgentId).toBeUndefined();
    expect(store.pendingConversationId).toBeNull();
    expect(store.pendingMessage).toBeNull();
    expect(store.consumeInteractionUpdates()).toEqual([]);

    store.setChatAvailable(true);
    expect(
      store.openWithContext({
        agentId: 8,
        conversationId: 12,
        message: 'send later',
      }),
    ).toBe(true);
    expect(store.visible).toBe(true);
    expect(store.consumePendingAgentId()).toBe(8);
    expect(store.consumePendingConversationId()).toBe(12);
    expect(store.consumePendingMessage()).toBe('send later');
  });
});
