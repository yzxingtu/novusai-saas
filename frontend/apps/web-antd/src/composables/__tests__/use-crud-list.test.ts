// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { UseCrudListOptions } from '../use-crud-list';

import { useCrudList } from '../use-crud-list';

type Item = {
  featured?: boolean;
  id: number;
  is_active?: boolean;
  name?: string;
};

type TestVm = {
  FormDrawer: unknown;
  currentPage: number;
  filteredList: Item[];
  formApi: null | {
    open: ReturnType<typeof vi.fn>;
    setData: ReturnType<typeof vi.fn>;
  };
  handleMenuAction: (code: string, row: Item) => void;
  list: Item[];
  loadList: () => Promise<void>;
  loading: boolean;
  onCreate: () => void;
  onDelete: (row: Item) => Promise<void>;
  onEdit: (row: Item) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  onSearch: (params?: Record<string, unknown>) => void;
  onSelect: (row: Item) => void;
  onToggleField: (
    fieldName: string,
    newStatus: boolean,
    row: Item,
  ) => Promise<boolean>;
  onToggleStatus: (newStatus: boolean, row: Item) => Promise<boolean>;
  pageSize: number;
  reload: () => Promise<void>;
  searchKeyword: string;
  searchParams: Record<string, unknown>;
  selectedId: null | number | string;
  selectedItem: Item | null;
  startAutoRefresh: () => void;
  stopAutoRefresh: () => void;
  total: number;
};

function createPopupApi(payloads: Array<Record<string, unknown>>) {
  const api = {
    open: vi.fn(),
    setData: vi.fn(),
  };

  api.setData.mockImplementation((payload: Record<string, unknown>) => {
    payloads.push(payload);
    return api;
  });

  return api;
}

const mockRefs = vi.hoisted(() => {
  const drawerPayloads: Array<Record<string, unknown>> = [];
  const modalPayloads: Array<Record<string, unknown>> = [];
  const drawerApi = createPopupApi(drawerPayloads);
  const modalApi = createPopupApi(modalPayloads);
  const messageError = vi.fn();
  const messageSuccess = vi.fn();
  const requestDelete = vi.fn();
  const requestGet = vi.fn();
  const showDependencyBlockModal = vi.fn().mockResolvedValue(undefined);
  const showDependencyPreviewModal = vi.fn().mockResolvedValue(true);
  const getErrorData = vi.fn(
    (error: { response?: { data?: Record<string, unknown> } }) =>
      error?.response?.data,
  );
  const getErrorStatus = vi.fn(
    (error: { response?: { status?: number } }) => error?.response?.status,
  );
  const showRequestError = vi.fn(
    (error: { message?: string; response?: { data?: { message?: string } } }) =>
      messageError(
        error?.response?.data?.message ?? error?.message ?? 'request failed',
      ),
  );
  let confirmMode: 'cancel' | 'ok' = 'ok';
  const setConfirmMode = (mode: 'cancel' | 'ok') => {
    confirmMode = mode;
  };
  const modalConfirm = vi.fn(
    (config: { onCancel?: () => void; onOk?: () => void }) => {
      if (confirmMode === 'cancel') {
        config.onCancel?.();
        return;
      }
      config.onOk?.();
    },
  );

  return {
    drawerApi,
    drawerPayloads,
    getErrorData,
    getErrorStatus,
    messageError,
    messageSuccess,
    modalApi,
    modalConfirm,
    modalPayloads,
    requestDelete,
    requestGet,
    setConfirmMode,
    showDependencyBlockModal,
    showDependencyPreviewModal,
    showRequestError,
  };
});

vi.mock('@vben/common-ui', () => ({
  useVbenDrawer: () => [
    defineComponent({ name: 'MockDrawer', render: () => null }),
    mockRefs.drawerApi,
  ],
  useVbenModal: () => [
    defineComponent({ name: 'MockModal', render: () => null }),
    mockRefs.modalApi,
  ],
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    confirm: mockRefs.modalConfirm,
    warning: vi.fn(),
  },
  message: {
    error: mockRefs.messageError,
    success: mockRefs.messageSuccess,
    warning: vi.fn(),
  },
}));

vi.mock('#/components/business/dependency-block-modal/service', () => ({
  showDependencyBlockModal: mockRefs.showDependencyBlockModal,
  showDependencyPreviewModal: mockRefs.showDependencyPreviewModal,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/error-helpers', () => ({
  getErrorData: mockRefs.getErrorData,
  getErrorStatus: mockRefs.getErrorStatus,
  showRequestError: mockRefs.showRequestError,
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    delete: mockRefs.requestDelete,
    get: mockRefs.requestGet,
  },
}));

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => {
    resolve = resolver;
  });

  return { promise, resolve };
}

function mountCrudList(
  options: Partial<UseCrudListOptions<Item>> = {},
): TestVm {
  const defaultApi = {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    resource: '/admin/items',
  };

  const wrapper = mount(
    defineComponent({
      name: 'UseCrudListHarness',
      setup() {
        return useCrudList<Item>({
          api: {
            ...defaultApi,
            ...options.api,
          },
          formComponent: defineComponent({
            name: 'InlineForm',
            render: () => null,
          }),
          i18nPrefix: 'admin.test',
          ...options,
        });
      },
      render: () => null,
    }),
  );

  return wrapper.vm as unknown as TestVm;
}

function setDocumentHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', {
    configurable: true,
    get: () => hidden,
  });
}

describe('useCrudList', () => {
  beforeEach(() => {
    mockRefs.drawerApi.open.mockClear();
    mockRefs.drawerApi.setData.mockClear();
    mockRefs.drawerPayloads.length = 0;
    mockRefs.getErrorData.mockClear();
    mockRefs.getErrorStatus.mockClear();
    mockRefs.messageError.mockReset();
    mockRefs.messageSuccess.mockReset();
    mockRefs.modalApi.open.mockClear();
    mockRefs.modalApi.setData.mockClear();
    mockRefs.modalConfirm.mockClear();
    mockRefs.modalPayloads.length = 0;
    mockRefs.requestDelete.mockReset();
    mockRefs.requestDelete.mockResolvedValue(undefined);
    mockRefs.requestGet.mockReset();
    mockRefs.requestGet.mockRejectedValue({ response: { status: 404 } });
    mockRefs.setConfirmMode('ok');
    mockRefs.showDependencyBlockModal.mockClear();
    mockRefs.showDependencyPreviewModal.mockClear();
    mockRefs.showDependencyPreviewModal.mockResolvedValue(true);
    mockRefs.showRequestError.mockClear();
  });

  afterEach(() => {
    Reflect.deleteProperty(document, 'hidden');
    vi.useRealTimers();
  });

  it('loads array data with client filtering and default array adapter', async () => {
    const listApi = vi.fn().mockResolvedValue([
      { id: 1, name: 'Alpha' },
      { id: 2, name: 'Beta' },
      { id: 3, name: 'Alpine' },
    ]);
    const vm = mountCrudList({
      api: {
        list: listApi,
        resource: '/admin/items',
      },
      clientFilter: (item, keyword) =>
        (item.name ?? '').toLowerCase().includes(keyword),
      defaultFilters: { scope: 'all' },
      defaultSort: 'name',
    });

    await flushPromises();

    expect(listApi).toHaveBeenCalledWith({
      'page[size]': 9999,
      scope: 'all',
      sort: 'name',
    });
    expect(vm.list).toEqual([
      { id: 1, name: 'Alpha' },
      { id: 2, name: 'Beta' },
      { id: 3, name: 'Alpine' },
    ]);
    expect(vm.total).toBe(3);

    vm.searchKeyword = 'al';
    await nextTick();

    expect(vm.filteredList).toEqual([
      { id: 1, name: 'Alpha' },
      { id: 3, name: 'Alpine' },
    ]);
  });

  it('adapts custom paginated responses and handles load failures', async () => {
    const responseAdapter: NonNullable<
      UseCrudListOptions<Item>['responseAdapter']
    > = vi.fn((data: unknown) => {
      const paginated = data as { records: Item[]; totalCount: number };
      return {
        items: paginated.records,
        total: paginated.totalCount,
      };
    });
    const successListApi = vi.fn().mockResolvedValue({
      records: [{ id: 9, name: 'Gamma' }],
      totalCount: 1,
    });

    const successVm = mountCrudList({
      api: {
        list: successListApi,
        resource: '/admin/items',
      },
      responseAdapter,
    });

    await flushPromises();

    expect(responseAdapter).toHaveBeenCalledWith({
      records: [{ id: 9, name: 'Gamma' }],
      totalCount: 1,
    });
    expect(successVm.list).toEqual([{ id: 9, name: 'Gamma' }]);
    expect(successVm.total).toBe(1);
    expect(successVm.loading).toBe(false);

    const failedVm = mountCrudList({
      api: {
        list: vi.fn().mockRejectedValue(new Error('load failed')),
        resource: '/admin/items',
      },
    });

    await flushPromises();

    expect(failedVm.list).toEqual([]);
    expect(failedVm.total).toBe(0);
    expect(failedVm.loading).toBe(false);
  });

  it('passes processed server-side search params and resets paging actions', async () => {
    const listApi = vi.fn().mockResolvedValue({
      items: [{ id: 1, name: 'Alpha' }],
      total: 1,
    });
    const vm = mountCrudList({
      api: {
        list: listApi,
        resource: '/admin/items',
      },
      defaultFilters: { tenant_id: 7 },
      pageSize: 20,
    });

    await flushPromises();

    vm.onPageChange(3);
    await flushPromises();

    expect(vm.currentPage).toBe(3);
    expect(listApi).toHaveBeenLastCalledWith({
      'page[number]': 3,
      'page[size]': 20,
      sort: '-created_at',
      tenant_id: 7,
    });

    vm.onSearch({
      _dateRange_created_at: ['2026-01-01', '2026-01-31'],
      keyword: 'Alpha',
      empty: '',
      nil: null,
    });
    await flushPromises();

    expect(vm.currentPage).toBe(1);
    expect(vm.searchParams).toEqual({
      _dateRange_created_at: ['2026-01-01', '2026-01-31'],
      empty: '',
      keyword: 'Alpha',
      nil: null,
    });
    expect(listApi).toHaveBeenLastCalledWith({
      'filter[created_at][between]': '2026-01-01,2026-01-31',
      'page[number]': 1,
      'page[size]': 20,
      keyword: 'Alpha',
      sort: '-created_at',
      tenant_id: 7,
    });

    vm.onPageSizeChange(50);
    await flushPromises();

    expect(vm.pageSize).toBe(50);
    expect(vm.currentPage).toBe(1);
    expect(listApi).toHaveBeenLastCalledWith({
      'filter[created_at][between]': '2026-01-01,2026-01-31',
      'page[number]': 1,
      'page[size]': 50,
      keyword: 'Alpha',
      sort: '-created_at',
      tenant_id: 7,
    });

    vm.onPageChange(4);
    await flushPromises();
    await vm.reload();

    expect(vm.currentPage).toBe(1);
    expect(listApi).toHaveBeenLastCalledWith({
      'filter[created_at][between]': '2026-01-01,2026-01-31',
      'page[number]': 1,
      'page[size]': 50,
      keyword: 'Alpha',
      sort: '-created_at',
      tenant_id: 7,
    });
  });

  it('manages selection with defaultSelect and manual onSelect', async () => {
    const listApi = vi.fn().mockResolvedValue({
      items: [
        { id: 1, name: 'Alpha' },
        { id: 2, name: 'Beta' },
      ],
      total: 2,
    });
    const vm = mountCrudList({
      api: {
        list: listApi,
        resource: '/admin/items',
      },
      selectable: true,
    });

    await flushPromises();

    expect(vm.selectedId).toBe(1);
    expect(vm.selectedItem).toEqual({ id: 1, name: 'Alpha' });

    vm.onSelect({ id: 2, name: 'Beta' });
    await nextTick();

    expect(vm.selectedId).toBe(2);
    expect(vm.selectedItem).toEqual({ id: 2, name: 'Beta' });

    const noDefaultSelectVm = mountCrudList({
      api: {
        list: vi.fn().mockResolvedValue({
          items: [{ id: 11, name: 'Solo' }],
          total: 1,
        }),
        resource: '/admin/items',
      },
      defaultSelect: 'none',
      selectable: true,
    });

    await flushPromises();

    expect(noDefaultSelectVm.selectedId).toBeNull();
    expect(noDefaultSelectVm.selectedItem).toBeNull();
  });

  it('uses modal form api and supports function/object form defaults', async () => {
    const modalVm = mountCrudList({
      formDefaults: () => ({ enabled: true }),
      formType: 'modal',
    });
    await flushPromises();

    modalVm.onCreate();

    expect(modalVm.FormDrawer).toBeTruthy();
    expect(modalVm.formApi).toBe(mockRefs.modalApi);
    expect(mockRefs.modalPayloads.at(-1)).toMatchObject({
      _defaults: { enabled: true },
      _resource: '/admin/items',
      mode: 'add',
    });

    const drawerVm = mountCrudList({
      formDefaults: { category: 'default' },
    });
    await flushPromises();

    drawerVm.onCreate();

    expect(mockRefs.drawerPayloads.at(-1)).toMatchObject({
      _defaults: { category: 'default' },
      _resource: '/admin/items',
      mode: 'add',
    });
  });

  it('handles toggle success, cancel, missing api, and status shortcut', async () => {
    const listApi = vi.fn().mockResolvedValue({
      items: [{ id: 1, name: 'Alpha', is_active: true }],
      total: 1,
    });
    const toggleFeatured = vi.fn().mockResolvedValue(undefined);
    const toggleStatus = vi.fn().mockResolvedValue(undefined);
    const vm = mountCrudList({
      api: {
        list: listApi,
        resource: '/admin/items',
        toggles: {
          featured: toggleFeatured,
          is_active: toggleStatus,
        },
      },
    });

    await flushPromises();

    const featuredResult = await vm.onToggleField('featured', true, {
      id: 1,
      name: 'Alpha',
    });

    expect(featuredResult).toBe(true);
    expect(toggleFeatured).toHaveBeenCalledWith(1, { featured: true });
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.common.enableui.actionMessage.operationSuccess',
    );

    mockRefs.setConfirmMode('cancel');
    const cancelResult = await vm.onToggleField('featured', false, {
      id: 1,
      name: 'Alpha',
    });

    expect(cancelResult).toBe(false);
    expect(toggleFeatured).toHaveBeenCalledTimes(1);

    mockRefs.setConfirmMode('ok');
    const statusResult = await vm.onToggleStatus(false, {
      id: 1,
      name: 'Alpha',
    });

    expect(statusResult).toBe(true);
    expect(toggleStatus).toHaveBeenCalledWith(1, { is_active: false });
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.common.disableui.actionMessage.operationSuccess',
    );

    const missingResult = await vm.onToggleField('missing', true, {
      id: 1,
      name: 'Alpha',
    });

    expect(missingResult).toBe(false);
    expect(listApi).toHaveBeenCalledTimes(3);
  });

  it('dispatches custom, edit, and delete menu actions', async () => {
    const customAction = vi.fn();
    const customDelete = vi.fn().mockResolvedValue(undefined);
    const vm = mountCrudList({
      api: {
        delete: customDelete,
        list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
        resource: '/admin/items',
      },
      customActions: {
        archive: customAction,
      },
    });

    await flushPromises();

    vm.handleMenuAction('archive', { id: 8, name: 'Row 8' });
    expect(customAction).toHaveBeenCalledWith({ id: 8, name: 'Row 8' });

    vm.handleMenuAction('edit', { id: 7, name: 'Row 7' });
    expect(mockRefs.drawerPayloads.at(-1)).toMatchObject({
      _resource: '/admin/items',
      id: 7,
      mode: 'edit',
      name: 'Row 7',
    });

    vm.handleMenuAction('delete', { id: 9, name: 'Row 9' });
    await flushPromises();

    expect(customDelete).toHaveBeenCalledWith(9);
  });

  it('skips auto refresh when hidden or already loading and stops cleanly', async () => {
    vi.useFakeTimers();
    setDocumentHidden(false);

    const firstLoad = createDeferred<{ items: Item[]; total: number }>();
    const listApi = vi
      .fn()
      .mockImplementationOnce(() => firstLoad.promise)
      .mockResolvedValue({ items: [{ id: 1, name: 'Alpha' }], total: 1 });
    const vm = mountCrudList({
      api: {
        list: listApi,
        resource: '/admin/items',
      },
      autoRefreshInterval: 1000,
    });

    await vi.advanceTimersByTimeAsync(1000);
    expect(listApi).toHaveBeenCalledTimes(1);

    firstLoad.resolve({ items: [{ id: 1, name: 'Alpha' }], total: 1 });
    await flushPromises();

    setDocumentHidden(true);
    await vi.advanceTimersByTimeAsync(1000);
    expect(listApi).toHaveBeenCalledTimes(1);

    setDocumentHidden(false);
    await vi.advanceTimersByTimeAsync(1000);
    await flushPromises();
    expect(listApi).toHaveBeenCalledTimes(2);

    vm.stopAutoRefresh();
    await vi.advanceTimersByTimeAsync(2000);
    expect(listApi).toHaveBeenCalledTimes(2);
  });

  it('shows an error when delete preview fails with non-404', async () => {
    const vm = mountCrudList();
    await flushPromises();

    mockRefs.requestGet.mockRejectedValue({
      response: {
        data: { message: 'preview failed' },
        status: 500,
      },
    });

    await vm.onDelete({ id: 3, name: 'Row 3' });

    expect(mockRefs.messageError).toHaveBeenCalledWith('preview failed');
    expect(mockRefs.requestDelete).not.toHaveBeenCalled();
  });

  it('shows success feedback when custom delete api resolves', async () => {
    const customDelete = vi.fn().mockResolvedValue(undefined);
    const vm = mountCrudList({
      api: {
        delete: customDelete,
        list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
        resource: '/admin/items',
      },
    });
    await flushPromises();

    await vm.onDelete({ id: 5, name: 'Row 5' });

    expect(customDelete).toHaveBeenCalledWith(5);
    expect(mockRefs.requestDelete).not.toHaveBeenCalled();
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.test.messages.deleteSuccess',
    );
  });

  it('does not inject legacy _aiPageKey into form popup payload', async () => {
    const vm = mountCrudList();
    await flushPromises();

    vm.onCreate();
    const createPayload = mockRefs.drawerPayloads.at(-1);
    expect(createPayload?._aiPageKey).toBeUndefined();
    expect(createPayload).toMatchObject({
      _resource: '/admin/items',
      mode: 'add',
    });

    vm.onEdit({ id: 7, name: 'Row 7' });
    const editPayload = mockRefs.drawerPayloads.at(-1);
    expect(editPayload?._aiPageKey).toBeUndefined();
    expect(editPayload).toMatchObject({
      _resource: '/admin/items',
      id: 7,
      mode: 'edit',
      name: 'Row 7',
    });
  });
});
