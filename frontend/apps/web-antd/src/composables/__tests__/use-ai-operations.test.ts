// @vitest-environment happy-dom
import { ref } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  clearPageOperationRegistry,
  executePageOperation,
  registerPageOperations,
} from '#/components/business/ai-slide-panel/page-operation-registry';

import { formStateTracker } from '../use-form-state-tracker';
import {
  clearRemoteOptionsCache,
  createStandardOperations,
} from '../use-ai-operations';

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
    clearRemoteOptionsCache();
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

  it('strips invalid remote-select placeholders from create_record defaults', async () => {
    vi.useFakeTimers();

    const open = vi.fn();
    const setData = vi.fn(() => ({ open }));

    const operations = createStandardOperations({
      resource: '/admin/ai/agents',
      loadList: async () => {},
      onSearch: async () => {},
      list: ref([]),
      formPopupApi: {
        setData,
      },
      formDefaults: () => ({
        scope: 'global_shared',
      }),
      formSchema: () => [
        {
          component: 'Input',
          fieldName: 'name',
          label: 'Name',
          rules: 'required',
        },
        {
          component: 'ApiSelect',
          fieldName: 'model_id',
          label: '关联模型',
          rules: 'selectRequired',
          componentProps: {
            api: vi.fn(async () => ({ items: [{ label: 'GPT-5.4', value: 1 }] })),
          },
        },
        {
          component: 'ApiSelect',
          fieldName: 'tenant_ids',
          label: '分配企业',
          componentProps: {
            api: vi.fn(async () => ({ items: [{ label: '租户 A', value: 1 }] })),
            mode: 'multiple',
          },
        },
      ],
    });

    const createRecord = operations.find(
      (operation) => operation.name === 'create_record',
    );
    const resultPromise = createRecord?.handler?.({
      model_id: 0,
      name: 'AI agent',
      tenant_ids: [],
    });

    await vi.advanceTimersByTimeAsync(250);
    const result = await resultPromise;

    expect(result.success).toBe(true);
    expect(setData).toHaveBeenCalledWith(
      expect.objectContaining({
        _defaults: {
          name: 'AI agent',
          scope: 'global_shared',
        },
      }),
    );
    expect(open).toHaveBeenCalledOnce();
  });

  it('strips invalid remote-select overrides from edit_record payload', async () => {
    vi.useFakeTimers();

    const open = vi.fn();
    const setData = vi.fn(() => ({ open }));

    const operations = createStandardOperations({
      resource: '/admin/ai/agents',
      loadList: async () => {},
      onSearch: async () => {},
      list: ref([{ id: 42, model_id: 9, name: 'existing' }]),
      formPopupApi: {
        setData,
      },
      formSchema: () => [
        {
          component: 'Input',
          fieldName: 'name',
          label: 'Name',
          rules: 'required',
        },
        {
          component: 'ApiSelect',
          fieldName: 'model_id',
          label: '关联模型',
          rules: 'selectRequired',
          componentProps: {
            api: vi.fn(async () => ({ items: [{ label: 'GPT-5.4', value: 9 }] })),
          },
        },
      ],
    });

    const editRecord = operations.find(
      (operation) => operation.name === 'edit_record',
    );
    const resultPromise = editRecord?.handler?.({
      id: 42,
      model_id: 0,
      name: 'updated',
    });

    await vi.advanceTimersByTimeAsync(250);
    const result = await resultPromise;

    expect(result.success).toBe(true);
    expect(setData).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 42,
        _overrides: {
          name: 'updated',
        },
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

  it('describes remote *_id selects as numeric and exposes get_form_options', () => {
    const operations = createStandardOperations({
      resource: '/admin/ai/agents-timeout',
      loadList: async () => {},
      onSearch: async () => {},
      list: ref([]),
      formPopupApi: {
        setData: vi.fn(() => ({ open: vi.fn() })),
      },
      formSchema: () => [
        {
          component: 'ApiSelect',
          fieldName: 'model_id',
          label: '关联模型',
          rules: 'selectRequired',
          componentProps: {
            api: vi.fn(async () => ({ items: [{ label: 'GPT-5.4', value: 1 }] })),
          },
        },
      ],
      pageKey: 'admin.ai.agents',
    });

    const fillForm = operations.find((operation) => operation.name === 'fill_form');
    const getFormOptions = operations.find(
      (operation) => operation.name === 'get_form_options',
    );

    expect(fillForm?.params?.model_id).toMatchObject({
      type: 'number',
    });
    expect(getFormOptions).toBeTruthy();
  });

  it('describes remote *_ids multi-selects as numeric arrays', () => {
    const operations = createStandardOperations({
      resource: '/admin/ai/agents-timeout',
      loadList: async () => {},
      onSearch: async () => {},
      list: ref([]),
      formPopupApi: {
        setData: vi.fn(() => ({ open: vi.fn() })),
      },
      formSchema: () => [
        {
          component: 'ApiSelect',
          fieldName: 'tenant_ids',
          label: '分配企业',
          componentProps: {
            api: vi.fn(async () => ({ items: [{ label: '租户 A', value: 1 }] })),
            mode: 'multiple',
          },
        },
      ],
      pageKey: 'admin.ai.agents',
    });

    const fillForm = operations.find((operation) => operation.name === 'fill_form');

    expect(fillForm?.params?.tenant_ids).toMatchObject({
      type: 'array',
      items: { type: 'number' },
    });
  });

  it('fails fast when get_form_options is called before the form opens', async () => {
    const operations = createStandardOperations({
      resource: '/admin/ai/agents-timeout',
      loadList: async () => {},
      onSearch: async () => {},
      list: ref([]),
      formPopupApi: {
        setData: vi.fn(() => ({ open: vi.fn() })),
      },
      formSchema: () => [
        {
          component: 'ApiSelect',
          fieldName: 'model_id',
          label: '关联模型',
          rules: 'selectRequired',
          componentProps: {
            api: vi.fn(async () => ({ items: [{ label: 'GPT-5.4', value: 1 }] })),
          },
        },
      ],
      pageKey: 'admin.ai.agents',
    });

    const getFormOptions = operations.find(
      (operation) => operation.name === 'get_form_options',
    );
    const result = await getFormOptions?.handler?.({ field_name: 'model_id' });

    expect(result).toMatchObject({
      success: false,
      message: 'shared.pageOperation.msg.formNotOpen',
    });
  });

  it('fails fast when remote get_form_options loading times out', async () => {
    vi.useFakeTimers();
    clearRemoteOptionsCache('/admin/ai/agents-timeout-hang');

    formStateTracker.open('admin.ai.agents', {
      mode: 'add',
      formApi: {
        getValues: async () => ({}),
        setValues: vi.fn(),
        submitForm: vi.fn(async () => {}),
        validate: async () => ({ valid: true }),
      },
    });

    const operations = createStandardOperations({
      resource: '/admin/ai/agents-timeout-hang',
      loadList: async () => {},
      onSearch: async () => {},
      list: ref([]),
      formPopupApi: {
        setData: vi.fn(() => ({ open: vi.fn() })),
      },
      formSchema: () => [
        {
          component: 'ApiSelect',
          fieldName: 'model_id',
          label: '关联模型',
          rules: 'selectRequired',
          componentProps: {
            api: vi.fn(
              () => new Promise(() => {}) as Promise<{ items: Array<{ label: string; value: number }> }>,
            ),
          },
        },
      ],
      pageKey: 'admin.ai.agents',
    });

    const getFormOptions = operations.find(
      (operation) => operation.name === 'get_form_options',
    );
    const resultPromise = getFormOptions?.handler?.({ field_name: 'model_id' });

    await vi.advanceTimersByTimeAsync(8_100);
    const result = await resultPromise;

    expect(result).toMatchObject({
      success: false,
      message: 'shared.pageOperation.msg.optionsLoadTimeout',
    });
  });
});
