import { beforeEach, describe, expect, it, vi } from 'vitest';

import { formStateTracker } from '../use-form-state-tracker';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('formStateTracker', () => {
  beforeEach(() => {
    formStateTracker.clear();
  });

  it('captures form state, dirty fields, and validation errors', async () => {
    formStateTracker.open('admin.ai.agents', {
      mode: 'edit',
      fieldDescriptors: {
        name: { label: 'Name' },
      } as never,
      formApi: {
        getValues: async () => ({
          metadata: { tags: ['a'] },
          name: 'Updated',
        }),
        setValues: vi.fn(),
        validate: async () => ({ valid: false }),
      },
      initialValues: {
        metadata: { tags: ['a'] },
        name: 'Original',
      },
    });

    const state = await formStateTracker.getState('admin.ai.agents');

    expect(state.isOpen).toBe(true);
    expect(state.mode).toBe('edit');
    expect(state.dirtyFields).toEqual(['name']);
    expect(state.validationErrors).toEqual({
      _form: 'shared.pageOperation.msg.formHasValidationErrors',
    });
    expect(state.fieldDescriptors.name?.label).toBe('Name');
  });

  it('falls back to the only tracked form for state and api lookup', async () => {
    const formApi = {
      getValues: async () => ({ name: 'Only Form' }),
      setValues: vi.fn(),
      validate: async () => ({ valid: true }),
    };
    formStateTracker.open('actual.page.key', {
      mode: 'add',
      formApi,
      initialValues: {},
    });

    expect(formStateTracker.isOpenWithFallback('different.page.key')).toBe(
      true,
    );
    expect(formStateTracker.getFormApi('different.page.key')).toBe(formApi);

    const state =
      await formStateTracker.getStateWithFallback('different.page.key');
    expect(state.currentValues).toEqual({ name: 'Only Form' });
  });

  it('closes and clears tracked entries', () => {
    formStateTracker.open('page.one', {
      mode: 'view',
      initialValues: {},
    });
    formStateTracker.open('page.two', {
      mode: 'add',
      initialValues: {},
    });

    expect(formStateTracker.getTrackedKeys()).toEqual(['page.one', 'page.two']);

    formStateTracker.close('page.one');
    expect(formStateTracker.getTrackedKeys()).toEqual(['page.two']);

    formStateTracker.clear();
    expect(formStateTracker.getTrackedKeys()).toEqual([]);
  });
});
