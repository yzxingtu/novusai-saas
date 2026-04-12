// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
import type { PropType } from 'vue';

import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useCrudPage } from '../use-crud-page';

const mockRoute = {
  path: '/admin/items',
  meta: {},
};

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
}));

const mockRefs = vi.hoisted(() => {
  const drawerPayloads: Array<Record<string, unknown>> = [];
  const drawerApi = {
    open: vi.fn(),
    setData: vi.fn(),
  };
  drawerApi.setData.mockImplementation((payload: Record<string, unknown>) => {
    drawerPayloads.push(payload);
    return drawerApi;
  });

  return {
    crudGridProps: [] as Array<Record<string, unknown>>,
    drawerApi,
    drawerPayloads,
    gridFactoryOptions: [] as Array<Record<string, unknown>>,
    gridQuery: vi.fn(),
    gridReload: vi.fn(),
    messageError: vi.fn(),
    messageSuccess: vi.fn(),
    requestDelete: vi.fn(),
    requestGet: vi.fn(),
    showDependencyBlockModal: vi.fn(),
    showDependencyPreviewModal: vi.fn(),
  };
});

vi.mock('@vben/common-ui', () => ({
  useVbenDrawer: () => [
    defineComponent({ name: 'MockDrawer', render: () => null }),
    mockRefs.drawerApi,
  ],
  useVbenModal: () => [
    defineComponent({ name: 'MockModal', render: () => null }),
    {
      open: vi.fn(),
      setData: vi.fn(),
    },
  ],
}));

vi.mock('ant-design-vue', () => ({
  Modal: { confirm: vi.fn() },
  message: {
    error: mockRefs.messageError,
    success: mockRefs.messageSuccess,
    warning: vi.fn(),
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    delete: mockRefs.requestDelete,
    get: mockRefs.requestGet,
  },
}));

vi.mock('#/components/business/dependency-block-modal/service', () => ({
  showDependencyBlockModal: mockRefs.showDependencyBlockModal,
  showDependencyPreviewModal: mockRefs.showDependencyPreviewModal,
}));

vi.mock('../components', () => ({
  CrudGrid: defineComponent({
    name: 'MockCrudGrid',
    props: {
      createLabel: { default: '', type: String },
      createPermission: { default: '', type: String },
      onCreate: { default: undefined, type: Function as PropType<() => void> },
      quickSearch: {
        default: undefined,
        type: Object as PropType<Record<string, unknown>>,
      },
    },
    setup(props) {
      mockRefs.crudGridProps.push(props as unknown as Record<string, unknown>);
      return () => null;
    },
  }),
  RecycleBinDrawer: defineComponent({
    name: 'MockRecycleBinDrawer',
    setup(_, { expose }) {
      expose({
        deletedCount: 0,
        open: vi.fn(),
        refreshCount: vi.fn(),
      });
      return () => null;
    },
  }),
  useExportModal: () => ({
    ExportModal: defineComponent({
      name: 'MockExportModal',
      render: () => null,
    }),
    openExportModal: vi.fn(),
  }),
}));

vi.mock('../use-vxe-grid', () => ({
  useGridSearchFormOptions: vi.fn(() => ({})),
  useVbenVxeGrid: (options: Record<string, unknown>) => {
    mockRefs.gridFactoryOptions.push(options);
    return [
      defineComponent({ name: 'MockGrid', render: () => null }),
      {
        formApi: {
          setValues: vi.fn(),
        },
        grid: {},
        query: mockRefs.gridQuery,
        reload: mockRefs.gridReload,
      },
    ];
  },
}));

function mountCrudPage(options: Record<string, unknown>) {
  const wrapper = mount(
    defineComponent({
      name: 'UseCrudPageHarness',
      setup() {
        return useCrudPage({
          api: {
            list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
            resource: '/admin/items',
          },
          columns: () => [],
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

  return wrapper.vm as {
    onCreate: () => void;
    onDelete: (row: { id: number; name?: string }) => Promise<void>;
    onEdit: (row: { id: number; name?: string }) => void;
  };
}

describe('useCrudPage', () => {
  beforeEach(() => {
    mockRefs.crudGridProps.length = 0;
    mockRefs.drawerApi.open.mockClear();
    mockRefs.drawerApi.setData.mockClear();
    mockRefs.drawerPayloads.length = 0;
    mockRefs.gridFactoryOptions.length = 0;
    mockRefs.gridQuery.mockReset();
    mockRefs.gridReload.mockReset();
    mockRefs.messageError.mockReset();
    mockRefs.messageSuccess.mockReset();
    mockRefs.requestDelete.mockReset();
    mockRefs.requestGet.mockReset();
    mockRefs.showDependencyBlockModal.mockReset();
    mockRefs.showDependencyPreviewModal.mockReset();
  });

  it('uses custom delete api when provided', async () => {
    const customDelete = vi.fn().mockResolvedValue(undefined);
    mockRefs.requestGet.mockRejectedValue({ response: { status: 404 } });

    const vm = mountCrudPage({
      api: {
        delete: customDelete,
        list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
        resource: '/admin/items',
      },
    });

    await vm.onDelete({ id: 7, name: 'Row 7' });

    expect(customDelete).toHaveBeenCalledWith(7);
    expect(mockRefs.requestDelete).not.toHaveBeenCalled();
    expect(mockRefs.gridQuery).toHaveBeenCalledOnce();
    expect(mockRefs.messageError).not.toHaveBeenCalled();
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.test.messages.deleteSuccess',
    );
  });

  it('shows an error when delete preview fails with non-404', async () => {
    mockRefs.requestGet.mockRejectedValue({
      response: {
        data: { message: 'preview failed' },
        status: 500,
      },
    });

    const vm = mountCrudPage({});

    await vm.onDelete({ id: 9, name: 'Row 9' });

    expect(mockRefs.messageError).toHaveBeenCalledWith('preview failed');
    expect(mockRefs.requestDelete).not.toHaveBeenCalled();
    expect(mockRefs.gridQuery).not.toHaveBeenCalled();
  });

  it('does not expose create handler when createPermission is missing', async () => {
    const vm = mount(
      defineComponent({
        name: 'UseCrudPageGridHarness',
        setup() {
          return useCrudPage({
            api: {
              list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
              resource: '/admin/items',
            },
            columns: () => [],
            formComponent: defineComponent({
              name: 'InlineForm',
              render: () => null,
            }),
            i18nPrefix: 'admin.test',
          });
        },
        render() {
          const Grid = (
            this as unknown as { Grid: ReturnType<typeof defineComponent> }
          ).Grid;
          return Grid ? h(Grid) : null;
        },
      }),
    );

    await vm.vm.$nextTick();

    const latestProps = mockRefs.crudGridProps.at(-1);
    expect(latestProps?.onCreate).toBeUndefined();
    expect(latestProps?.createPermission).toBe('');
  });

  it('does not inject legacy _aiPageKey into form popup payload', () => {
    const vm = mountCrudPage({});

    vm.onCreate();
    const createPayload = mockRefs.drawerPayloads.at(-1);
    expect(createPayload?._aiPageKey).toBeUndefined();
    expect(createPayload).toMatchObject({
      _resource: '/admin/items',
      mode: 'add',
    });

    vm.onEdit({ id: 8, name: 'Row 8' });
    const editPayload = mockRefs.drawerPayloads.at(-1);
    expect(editPayload?._aiPageKey).toBeUndefined();
    expect(editPayload).toMatchObject({
      _resource: '/admin/items',
      id: 8,
      mode: 'edit',
      name: 'Row 8',
    });
  });

  it('injects _pageKey by default for AI-enabled pages', () => {
    mockRoute.path = '/admin/items';
    const vm = mountCrudPage({});

    vm.onCreate();
    const createPayload = mockRefs.drawerPayloads.at(-1);
    expect(createPayload?._pageKey).toBe('admin.items');
    expect(createPayload?._aiPageKey).toBeUndefined();

    vm.onEdit({ id: 9, name: 'Row 9' });
    const editPayload = mockRefs.drawerPayloads.at(-1);
    expect(editPayload?._pageKey).toBe('admin.items');
  });

  it('respects explicit ai.pageKey override', () => {
    const vm = mountCrudPage({
      ai: { pageKey: 'custom.page' },
    });

    vm.onCreate();
    const createPayload = mockRefs.drawerPayloads.at(-1);
    expect(createPayload?._pageKey).toBe('custom.page');
  });

  it('skips _pageKey when ai is false', () => {
    const vm = mountCrudPage({
      ai: false,
    });

    vm.onCreate();
    const createPayload = mockRefs.drawerPayloads.at(-1);
    expect(createPayload?._pageKey).toBeUndefined();
  });

  it('passes search defaultOpen and quick search config to grid wrapper', async () => {
    const vm = mount(
      defineComponent({
        name: 'UseCrudPageSearchHarness',
        setup() {
          return useCrudPage({
            api: {
              list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
              resource: '/admin/items',
            },
            columns: () => [],
            i18nPrefix: 'admin.test',
            search: {
              defaultOpen: false,
              quickSearch: true,
            },
            searchSchema: [
              {
                component: 'Input',
                componentProps: {
                  placeholder: 'Search name',
                },
                fieldName: 'filter[name][ilike]',
                label: 'Name',
              },
            ],
          });
        },
        render() {
          const Grid = (
            this as unknown as { Grid: ReturnType<typeof defineComponent> }
          ).Grid;
          return Grid ? h(Grid) : null;
        },
      }),
    );

    await vm.vm.$nextTick();

    expect(mockRefs.gridFactoryOptions.at(-1)?.searchPanelAnimation).toBe(
      false,
    );
    expect(mockRefs.gridFactoryOptions.at(-1)?.showSearchForm).toBe(false);
    expect(
      (
        mockRefs.crudGridProps.at(-1)?.quickSearch as
          | Record<string, unknown>
          | undefined
      )?.activeField,
    ).toBe('filter[name][ilike]');
    expect(
      (
        mockRefs.crudGridProps.at(-1)?.quickSearch as
          | undefined
          | { options?: Array<Record<string, unknown>> }
      )?.options?.[0]?.placeholder,
    ).toBe('Search name');
  });

  it('passes animated search panel opt-in to grid wrapper', async () => {
    const vm = mount(
      defineComponent({
        name: 'UseCrudPageAnimatedSearchHarness',
        setup() {
          return useCrudPage({
            api: {
              list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
              resource: '/admin/items',
            },
            columns: () => [],
            i18nPrefix: 'admin.test',
            search: {
              animatePanel: true,
            },
            searchSchema: [
              {
                component: 'Input',
                fieldName: 'filter[name][ilike]',
                label: 'Name',
              },
            ],
          });
        },
        render() {
          const Grid = (
            this as unknown as { Grid: ReturnType<typeof defineComponent> }
          ).Grid;
          return Grid ? h(Grid) : null;
        },
      }),
    );

    await vm.vm.$nextTick();

    expect(mockRefs.gridFactoryOptions.at(-1)?.searchPanelAnimation).toBe(true);
    expect(mockRefs.gridFactoryOptions.at(-1)?.showSearchForm).toBe(true);
  });
});
