// @vitest-environment happy-dom

import { describe, expect, it, vi } from 'vitest';

const uiActionChannelMocks = vi.hoisted(() => ({
  waitForPageSessionJoin: vi.fn(() => Promise.resolve(true)),
}));

vi.mock('#/composables/use-ui-action-channel', () => ({
  waitForPageSessionJoin: uiActionChannelMocks.waitForPageSessionJoin,
}));

import {
  createAIChatPageOperations,
  hasInteractivePageContext,
} from '../use-ai-chat-page-operations';

describe('use-ai-chat-page-operations', () => {
  it('does not treat suggested_tools-only page context as interactive runtime state', () => {
    expect(
      hasInteractivePageContext({
        page_key: 'tenant.dashboard',
        suggested_tools: {
          primary: ['ui_get_snapshot', 'ui_list_interactables'],
          secondary: ['ui_click'],
        },
      }),
    ).toBe(false);
  });

  it('keeps interactive runtime state tied to canonical runtime facts', () => {
    expect(
      hasInteractivePageContext({
        active_surface_id: 'page:tenant.dashboard',
        page_key: 'tenant.dashboard',
        ui_epoch: 1,
      }),
    ).toBe(true);
  });

  it('refreshes page-session join readiness without page_key in the live handshake', async () => {
    const socketIOStore = {
      emit: vi.fn(),
      isConnected: true,
    };
    const operations = createAIChatPageOperations({
      pageSessionIdGetter: () => 'page-session-1',
      socketIOStore,
      socketSettleMs: 0,
    });

    const ready = await operations.ensurePageOperationChannelReady('/tenant', {
      active_surface_id: 'page:tenant.dashboard',
      page_key: 'tenant.dashboard',
      ui_epoch: 1,
    });

    expect(ready).toBe(true);
    expect(socketIOStore.emit).toHaveBeenCalledWith('page_session_join', {
      page_session_id: 'page-session-1',
    });
    expect(uiActionChannelMocks.waitForPageSessionJoin).toHaveBeenCalledWith(
      'page-session-1',
      3000,
      100,
    );
  });
});
