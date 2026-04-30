// @vitest-environment happy-dom

import { describe, expect, it, vi } from 'vitest';

import {
  createAIChatPageOperations,
  hasInteractivePageContext,
} from '../use-ai-chat-page-operations';

describe('use-ai-chat-page-operations', () => {
  it('always treats page context as non-interactive because page awareness is retired', () => {
    expect(
      hasInteractivePageContext({
        active_surface_id: 'page:tenant.dashboard',
        page_key: 'tenant.dashboard',
        suggested_tools: {
          primary: ['ui_get_snapshot', 'ui_list_interactables'],
          secondary: ['ui_click'],
        },
        ui_epoch: 1,
      }),
    ).toBe(false);
  });

  it('does not join page sessions or emit UI action channel events', async () => {
    const socketIOStore = {
      emit: vi.fn(),
      isConnected: true,
    };
    const operations = createAIChatPageOperations({
      pageSessionIdGetter: () => 'page-session-1',
      socketIOStore,
      socketSettleMs: 0,
    });

    const ready = await operations.ensurePageOperationChannelReady();

    expect(ready).toBe(true);
    expect(operations.hasPageOperations()).toBe(false);
    expect(socketIOStore.emit).not.toHaveBeenCalled();
  });
});
