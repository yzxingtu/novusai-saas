// Test type: structural
// Verifies: tool call detail helpers build input and output view models from canonical tool evidence.
import { describe, expect, it, vi } from 'vitest';

import { buildToolDisplayItems } from '../chat-message-tool-call-display-helpers';
import { buildToolCallDetailsViewModel } from '../chat-message-tool-call-details-helpers';

vi.mock('#/locales', () => ({
  $t: (key: string, params?: Record<string, unknown>) => {
    if (!params || Object.keys(params).length === 0) {
      return key;
    }
    const suffix = Object.entries(params)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([name, value]) => `${name}=${String(value)}`)
      .join(',');
    return `${key}:${suffix}`;
  },
}));

describe('chat-message-tool-call-details helpers', () => {
  it('builds one coherent detail view from arguments and returned payload', () => {
    const [toolItem] = buildToolDisplayItems(
      [
        {
          arguments: {
            filters: {
              owner: 'ops',
              status: 'active',
            },
            tenant_code: 'northwind',
          },
          name: 'query_records',
          output: JSON.stringify({
            records: [
              {
                name: 'Northwind',
                total: 12,
              },
            ],
            result: {
              trace_id: 'trace-123',
              updated: true,
            },
          }),
          status: 'success',
          summaryPayload: {
            explanation: 'Matched active tenants',
          },
        },
      ],
      {
        resolveExpanded: () => true,
      },
    );

    expect(toolItem).toBeDefined();
    if (!toolItem) {
      throw new Error('Tool display item was not built');
    }

    const detailView = buildToolCallDetailsViewModel(toolItem);

    expect(detailView.argumentFields.map((field) => field.key)).toEqual([
      'filters',
      'tenant_code',
    ]);
    expect(detailView.outputFields.map((field) => field.key)).toEqual([
      'records',
      'result',
    ]);
    expect(detailView.rawOutput).toContain('"trace_id": "trace-123"');
  });
});
