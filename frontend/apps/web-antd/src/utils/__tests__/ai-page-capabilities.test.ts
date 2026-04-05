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
        disabledCapabilities: ['search', 'pagination'],
        disabledOperations: ['sync_policies'],
        legacyDisabledOperations: ['read_visible_rows'],
      }),
    ).toEqual(
      expect.arrayContaining([
        'clear_search',
        'go_to_page',
        'next_page',
        'prev_page',
        'read_visible_rows',
        'search',
        'set_page_size',
        'sync_policies',
      ]),
    );
  });

  it('filters operations by mode and disabled capabilities', () => {
    const operations = [
      { name: 'search' },
      { name: 'navigate_menu' },
      { name: 'next_page' },
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
        disabledCapabilities: ['search', 'pagination'],
      }),
    ).toEqual([{ name: 'navigate_menu' }, { name: 'sync_policies' }]);

    expect(
      filterPageOperationsByPolicy(operations, {
        mode: 'navigation_only',
      }),
    ).toEqual([{ name: 'navigate_menu' }]);
  });
});
