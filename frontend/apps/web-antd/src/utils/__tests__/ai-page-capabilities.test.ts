import { describe, expect, it } from 'vitest';

import {
  buildTablePolicySupportData,
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
    ).toEqual([{ name: 'sync_policies' }]);
  });

  it('builds table policy runtime payload in snake case', () => {
    expect(
      buildTablePolicySupportData({
        enabled: true,
        kind: 'management',
        relatedPolicyIds: [1, 2, 2],
        relatedResources: ['/admin/ai/table-policies'],
        relatedTables: ['ai_table_policies'],
        supportedActions: ['list_policies', 'sync_policies'],
      }),
    ).toEqual({
      enabled: true,
      kind: 'management',
      related_policy_ids: [1, 2],
      related_resources: ['/admin/ai/table-policies'],
      related_tables: ['ai_table_policies'],
      supported_actions: ['list_policies', 'sync_policies'],
    });
  });
});
