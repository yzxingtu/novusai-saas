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

  it('keeps get_form_options in the compacted operation set for form pages', () => {
    const result = guardPageDataSize(
      {
        available_operations: [
          {
            name: 'create_record',
            readonly: false,
            description: 'Open create form'.repeat(20),
          },
          {
            name: 'edit_record',
            readonly: false,
            description: 'Open edit form'.repeat(20),
          },
          {
            name: 'fill_form',
            readonly: false,
            description: 'Fill form with inferred values'.repeat(20),
          },
          {
            name: 'submit_form',
            readonly: false,
            description: 'Submit form'.repeat(20),
          },
          {
            name: 'get_form_state',
            readonly: true,
            description: 'Inspect current form state'.repeat(20),
          },
          {
            name: 'get_form_options',
            readonly: true,
            description: 'Fetch remote select options'.repeat(20),
          },
          {
            name: 'validate_form',
            readonly: true,
            description: 'Validate current form'.repeat(20),
          },
          {
            name: 'search',
            readonly: true,
            description: 'Search list'.repeat(20),
          },
          {
            name: 'read_visible_rows',
            readonly: true,
            description: 'Read visible rows'.repeat(20),
          },
          {
            name: 'capture_screenshot',
            readonly: true,
            description: 'Capture screenshot'.repeat(20),
          },
          {
            name: 'next_page',
            readonly: true,
            description: 'Next page'.repeat(20),
          },
          {
            name: 'prev_page',
            readonly: true,
            description: 'Previous page'.repeat(20),
          },
          {
            name: 'refresh_list',
            readonly: true,
            description: 'Refresh list'.repeat(20),
          },
        ],
      },
      1000,
    );

    const operations = result.available_operations as Array<
      Record<string, unknown>
    >;

    expect(operations.map((operation) => operation.name)).toContain(
      'get_form_options',
    );
  });
});
