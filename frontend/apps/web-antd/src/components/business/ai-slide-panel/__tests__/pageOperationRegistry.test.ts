// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

import { formStateTracker } from '#/composables/use-form-state-tracker';

import {
  appendPageOperations,
  clearPageOperationRegistry,
  executePageOperation,
  listPageOperations,
  registerPageOperations,
} from '../page-operation-registry';

describe('page-operation-registry', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    clearPageOperationRegistry();
    formStateTracker.clear();
    document.body.innerHTML = '';
  });

  it('coerces declared params before invoking handler', async () => {
    let receivedParams: Record<string, unknown> | null = null;

    registerPageOperations('tenant.demo.validation', [
      {
        name: 'update_status',
        label: 'Update Status',
        readonly: false,
        params: {
          id: { required: true, type: 'number' },
          mode: { enum: ['draft', 'published'], type: 'string' },
          published: { type: 'boolean' },
        },
        handler: async (params) => {
          receivedParams = params;
          return {
            success: true,
            message: 'updated',
          };
        },
      },
    ]);

    const result = await executePageOperation('tenant.demo.validation', 'update_status', {
      id: '12',
      mode: 'published',
      published: 'true',
    });

    expect(result.success).toBe(true);
    expect(receivedParams).toEqual({
      id: 12,
      mode: 'published',
      published: true,
    });
  });

  it('rejects missing required params and invalid enum values', async () => {
    registerPageOperations('tenant.demo.validation', [
      {
        name: 'update_status',
        label: 'Update Status',
        readonly: false,
        params: {
          id: { required: true, type: 'number' },
          mode: { enum: ['draft', 'published'], type: 'string' },
        },
        handler: async () => ({
          success: true,
          message: 'updated',
        }),
      },
    ]);

    const missingResult = await executePageOperation(
      'tenant.demo.validation',
      'update_status',
      { mode: 'draft' },
    );
    expect(missingResult.success).toBe(false);
    expect(missingResult.error_type).toBe('invalid_input');
    expect(missingResult.message).toContain('paramRequired');

    const invalidEnumResult = await executePageOperation(
      'tenant.demo.validation',
      'update_status',
      { id: 1, mode: 'archived' },
    );
    expect(invalidEnumResult.success).toBe(false);
    expect(invalidEnumResult.error_type).toBe('invalid_input');
    expect(invalidEnumResult.message).toContain('paramInvalidEnum');
  });

  it('merges observed context diff with handler-provided context diff', async () => {
    registerPageOperations('tenant.demo.context', [
      {
        name: 'open_editor',
        label: 'Open Editor',
        readonly: false,
        handler: async () => {
          formStateTracker.open('tenant.demo.context', {
            mode: 'add',
          });
          const drawer = document.createElement('div');
          drawer.className = 'ant-drawer-open';
          document.body.appendChild(drawer);
          return {
            success: true,
            message: 'opened',
            data: {
              context_diff: {
                custom_flag: true,
              },
            },
          };
        },
      },
    ]);

    const result = await executePageOperation('tenant.demo.context', 'open_editor');

    expect(result.success).toBe(true);
    expect(result.data?.context_diff).toMatchObject({
      custom_flag: true,
      drawer_opened: true,
      form_opened: true,
    });
  });

  it('filters falsy and invalid operations from register/append safely', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    registerPageOperations('tenant.demo.invalid_ops', [
      undefined as unknown as {
        label: string;
        name: string;
        readonly: boolean;
      },
      {
        name: 'valid_primary',
        label: 'Valid Primary',
        readonly: true,
        handler: async () => ({
          success: true,
          message: 'ok',
        }),
      },
      {
        name: '',
        label: 'Missing Name',
        readonly: true,
      } as unknown as {
        label: string;
        name: string;
        readonly: boolean;
      },
    ]);

    appendPageOperations('tenant.demo.invalid_ops', [
      null as unknown as {
        label: string;
        name: string;
        readonly: boolean;
      },
      {
        name: 'valid_extra',
        label: 'Valid Extra',
        readonly: false,
        handler: async () => ({
          success: true,
          message: 'extra',
        }),
      },
      {
        name: 'broken_without_readonly',
        label: 'Broken',
      } as unknown as {
        label: string;
        name: string;
        readonly: boolean;
      },
    ]);

    const operationNames = listPageOperations('tenant.demo.invalid_ops').map(
      (operation) => operation.name,
    );

    expect(operationNames).toContain('valid_primary');
    expect(operationNames).toContain('valid_extra');
    expect(operationNames).not.toContain('broken_without_readonly');
    expect(operationNames).not.toContain('');

    const result = await executePageOperation(
      'tenant.demo.invalid_ops',
      'valid_extra',
    );
    expect(result.success).toBe(true);
    expect(warnSpy).toHaveBeenCalled();
  });
});
