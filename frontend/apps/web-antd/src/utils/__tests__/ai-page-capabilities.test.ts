import { describe, expect, it } from 'vitest';

import {
  filterPageOperationsByPolicy,
  mergeDisabledOperations,
  normalizePageAIMode,
} from '../ai-page-capabilities';

describe('ai-page-capabilities', () => {
  it('falls back to operate mode when mode is missing', () => {
    expect(normalizePageAIMode(undefined)).toBe('operate');
  });

  it('merges disabled capabilities with explicit operation names', () => {
    expect(
      mergeDisabledOperations({
        disabledCapabilities: ['search', 'pagination', 'submit'],
        disabledOperations: ['sync_policies'],
      }),
    ).toEqual(
      expect.arrayContaining([
        'ui_click',
        'ui_fill_form',
        'ui_open_surface',
        'ui_set_field',
        'ui_submit_form',
        'sync_policies',
      ]),
    );
  });

  it('filters operations by mode and disabled capabilities', () => {
    const operations = [
      { name: 'ui_fill_form' },
      { name: 'ui_open_surface' },
      { name: 'ui_submit_form' },
      { name: 'sync_policies' },
    ];

    expect(
      filterPageOperationsByPolicy(operations, {
        mode: 'context_only',
      }),
    ).toEqual([]);

    expect(
      filterPageOperationsByPolicy(operations, {
        mode: 'operate',
        disabledCapabilities: ['form', 'submit'],
      }),
    ).toEqual([{ name: 'ui_open_surface' }, { name: 'sync_policies' }]);
  });

  it('keeps navigation_only constrained to canonical ui tools', () => {
    expect(
      filterPageOperationsByPolicy(
        [
          { name: 'navigate_menu' },
          { name: 'ui_click' },
          { name: 'ui_open_surface' },
          { name: 'ui_fill_form' },
        ],
        {
          mode: 'navigation_only',
        },
      ),
    ).toEqual([{ name: 'ui_click' }, { name: 'ui_open_surface' }]);
  });
});
