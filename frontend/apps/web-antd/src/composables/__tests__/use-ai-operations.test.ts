// @vitest-environment happy-dom
import { ref } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  clearPageOperationRegistry,
  executePageOperation,
  registerPageOperations,
} from '#/components/business/ai-slide-panel/page-operation-registry';

import { formStateTracker } from '../use-form-state-tracker';
import { createStandardOperations } from '../use-ai-operations';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    delete: vi.fn(),
  },
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe('createStandardOperations', () => {
  afterEach(() => {
    vi.useRealTimers();
    clearPageOperationRegistry();
    formStateTracker.clear();
  });

  it('allows create_record to omit form-required fields and rely on drawer defaults', async () => {
    vi.useFakeTimers();

    const open = vi.fn();
    const setData = vi.fn(() => ({ open }));

    const operations = createStandardOperations({
      resource: '/admin/periodic-tasks',
      loadList: async () => {},
      onSearch: async () => {},
      list: ref([]),
      formPopupApi: {
        setData,
      },
      formDefaults: () => ({
        interval_seconds: 60,
        scope: 'admin_only',
      }),
      formSchema: () => [
        {
          component: 'Input',
          fieldName: 'name',
          label: 'Name',
          rules: 'required',
        },
        {
          component: 'Input',
          fieldName: 'task_path',
          label: 'Task Path',
          rules: 'required',
        },
        {
          component: 'Select',
          fieldName: 'scope',
          label: 'Scope',
          rules: 'selectRequired',
        },
      ],
    });

    registerPageOperations('admin.system.periodic-tasks', operations);

    const resultPromise = executePageOperation(
      'admin.system.periodic-tasks',
      'create_record',
      {
        name: 'AI scope regression',
        task_path: 'tasks.regression',
      },
    );

    await vi.advanceTimersByTimeAsync(2_000);
    const result = await resultPromise;

    expect(result.success).toBe(true);
    expect(setData).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'add',
        _defaults: expect.objectContaining({
          interval_seconds: 60,
          name: 'AI scope regression',
          scope: 'admin_only',
          task_path: 'tasks.regression',
        }),
      }),
    );
    expect(open).toHaveBeenCalledOnce();
  });

  it('allows fill_form to patch only a subset of fields even when the form schema marks them required', async () => {
    vi.useFakeTimers();

    const values: Record<string, unknown> = {
      scope: 'admin_only',
      task_path: 'tasks.original',
    };
    const setValues = vi.fn((nextValues: Record<string, unknown>) => {
      Object.assign(values, nextValues);
    });

    formStateTracker.open('admin.system.periodic-tasks', {
      formApi: {
        getValues: async () => ({ ...values }),
        setValues,
        validate: async () => ({ valid: true }),
      },
      initialValues: { ...values },
      mode: 'add',
    });

    const operations = createStandardOperations({
      resource: '/admin/periodic-tasks',
      loadList: async () => {},
      onSearch: async () => {},
      list: ref([]),
      formPopupApi: {
        setData: vi.fn(() => ({ open: vi.fn() })),
      },
      formSchema: () => [
        {
          component: 'Input',
          fieldName: 'name',
          label: 'Name',
          rules: 'required',
        },
        {
          component: 'Input',
          fieldName: 'task_path',
          label: 'Task Path',
          rules: 'required',
        },
        {
          component: 'Select',
          fieldName: 'scope',
          label: 'Scope',
          rules: 'selectRequired',
        },
      ],
      pageKey: 'admin.system.periodic-tasks',
    });

    registerPageOperations('admin.system.periodic-tasks', operations);

    const resultPromise = executePageOperation(
      'admin.system.periodic-tasks',
      'fill_form',
      {
        name: 'Only update name',
      },
    );

    await vi.advanceTimersByTimeAsync(2_000);
    const result = await resultPromise;

    expect(result.success).toBe(true);
    expect(setValues).toHaveBeenCalledWith({
      name: 'Only update name',
    });
    expect(values).toMatchObject({
      name: 'Only update name',
      scope: 'admin_only',
      task_path: 'tasks.original',
    });
  });
});
