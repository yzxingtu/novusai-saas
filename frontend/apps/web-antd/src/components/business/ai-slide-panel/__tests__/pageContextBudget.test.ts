import { describe, expect, it } from 'vitest';

import { guardPageDataSize } from '../page-context-budget';

describe('guardPageDataSize', () => {
  it('preserves a minimal available_operations list even when payload is heavily compacted', () => {
    const result = guardPageDataSize(
      {
        available_operations: [
          {
            description: 'Open create form and start record creation'.repeat(8),
            label: 'Create',
            name: 'create_record',
            params: {
              draft: { required: false, type: 'boolean' },
              template_id: { required: false, type: 'integer' },
            },
            readonly: false,
          },
          {
            description: 'Fill the opened form with inferred values'.repeat(8),
            label: 'Fill Form',
            name: 'fill_form',
            params: {
              values: { required: true, type: 'object' },
            },
            readonly: false,
          },
          {
            description: 'Read the currently visible rows in the grid'.repeat(
              8,
            ),
            label: 'Read Rows',
            name: 'read_visible_rows',
            params: {
              limit: { required: false, type: 'integer' },
            },
            readonly: true,
          },
        ],
        document_body_text: 'x'.repeat(8000),
        form_fields: Object.fromEntries(
          Array.from({ length: 16 }, (_, index) => [
            `field_${index}`,
            {
              component: 'input',
              description: `Description ${index}`.repeat(20),
              options: Array.from({ length: 6 }, (__, optionIndex) => ({
                label: `Option ${index}-${optionIndex}`,
                value: `${index}-${optionIndex}`,
              })),
              required: index % 2 === 0,
              type: 'string',
            },
          ]),
        ),
        list_summary: {
          sample_rows: Array.from({ length: 5 }, (_, index) => ({
            name: `Record ${index}`,
            summary: 'Row summary '.repeat(18),
          })),
          total_rows: 99,
        },
      },
      900,
    );

    const operations = result.available_operations as Array<
      Record<string, unknown>
    >;

    expect(Array.isArray(operations)).toBe(true);
    expect(operations.length).toBeGreaterThan(0);
    expect(operations.map((operation) => operation.name)).toContain(
      'create_record',
    );
    expect(
      operations.every(
        (operation) =>
          typeof operation.name === 'string' &&
          typeof operation.readonly === 'boolean',
      ),
    ).toBe(true);
  });
});
