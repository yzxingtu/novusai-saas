// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest';

import { hasInteractivePageContext } from '../use-ai-chat-page-operations';

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
});
