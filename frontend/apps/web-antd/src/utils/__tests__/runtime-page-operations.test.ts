// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest';

import {
  buildRuntimePageOperationNames,
  hasRuntimePageState,
} from '../runtime-page-operations';

describe('runtime-page-operations', () => {
  it('ignores suggested_tools-only page context when deriving live runtime operations', () => {
    const pageContext = {
      page_key: 'tenant.dashboard',
      suggested_tools: {
        primary: ['ui_get_snapshot', 'ui_list_interactables'],
        secondary: ['ui_click'],
      },
    } as unknown as Parameters<typeof buildRuntimePageOperationNames>[0];

    expect(hasRuntimePageState(pageContext)).toBe(false);
    expect(buildRuntimePageOperationNames(pageContext)).toEqual([]);
  });

  it('derives live runtime operations from canonical page runtime facts only', () => {
    const pageContext = {
      active_form_session_id: 'form-session-1',
      active_form_summary: {
        can_submit: true,
        form_session_id: 'form-session-1',
      },
      active_surface_id: 'page:tenant.dashboard',
      page_key: 'tenant.dashboard',
      suggested_tools: {
        primary: ['ui_read_table'],
      },
      ui_epoch: 3,
    } as unknown as Parameters<typeof buildRuntimePageOperationNames>[0];

    expect(buildRuntimePageOperationNames(pageContext)).toEqual([
      'ui_get_snapshot',
      'ui_read_region',
      'ui_list_interactables',
      'ui_click',
      'ui_open_surface',
      'ui_get_form_state',
      'ui_fill_form',
      'ui_set_field',
      'ui_submit_form',
    ]);
  });
});
