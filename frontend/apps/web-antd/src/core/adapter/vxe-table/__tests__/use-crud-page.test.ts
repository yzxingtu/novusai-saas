/* eslint-disable vue/one-component-per-file */
import type { PropType } from 'vue';

import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useCrudPage } from '../use-crud-page';

const mockRefs = vi.hoisted(() => ({
  appendPageOperations: vi.fn(() => vi.fn()),
  createStandardOperations: vi.fn(() => []),
  crudGridProps: [] as Array<Record<string, unknown>>,
  gridFactoryOptions: [] as Array<Record<string, unknown>>,
  gridQuery: vi.fn(),
  gridReload: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  registerPageContext: vi.fn(() => vi.fn()),
  registerPageContextExtras: vi.fn(() => vi.fn()),
  requestDelete: vi.fn(),
  requestGet: vi.fn(),
  showDependencyBlockModal: vi.fn(),
  showDependencyPreviewModal: vi.fn(),
}));

vi.mock('@vben/common-ui', () => ({
  useVbenDrawer: () => [
    defineComponent({ name: 'MockDrawer', render: () => null }),
    {},
  ],
  useVbenModal: () => [
    defineComponent({ name: 'MockModal', render: () => null }),
    {},
  ],
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({
    path: '/admin/items',
    meta: {},
  }),
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

vi.mock('#/components/business/ai-slide-panel', () => ({
  appendPageOperations: mockRefs.appendPageOperations,
  registerPageContextExtras: mockRefs.registerPageContextExtras,
}));

vi.mock('#/components/business/ai-slide-panel/page-context-registry', () => ({
  registerPageContext: mockRefs.registerPageContext,
}));

vi.mock('#/composables/use-ai-operations', () => ({
  buildCrudListSummary: () => undefined,
  buildCrudPaginationState: () => ({
    current_page: 1,
    page_size: 15,
    total_pages: 1,
    total_rows: 0,
    has_next_page: false,
    has_previous_page: false,
  }),
  compactCrudContextValues: (value: Record<string, unknown>) => value,
  createFormOperations: () => [],
  createStandardOperations: mockRefs.createStandardOperations,
  extractFormParams: () => ({}),
}));

vi.mock('#/composables/use-form-state-tracker', () => ({
  formStateTracker: {
    close: vi.fn(),
    isOpen: vi.fn(() => false),
  },
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
          i18nPrefix: 'admin.test',
          ...options,
        });
      },
      render: () => null,
    }),
  );

  return wrapper.vm as {
    onDelete: (row: { id: number; name?: string }) => Promise<void>;
  };
}

describe('useCrudPage', () => {
  beforeEach(() => {
    mockRefs.appendPageOperations.mockClear();
    mockRefs.createStandardOperations.mockClear();
    mockRefs.crudGridProps.length = 0;
    mockRefs.gridFactoryOptions.length = 0;
    mockRefs.requestGet.mockReset();
    mockRefs.requestDelete.mockReset();
    mockRefs.messageError.mockReset();
    mockRefs.messageSuccess.mockReset();
    mockRefs.gridQuery.mockReset();
    mockRefs.gridReload.mockReset();
    mockRefs.registerPageContext.mockClear();
    mockRefs.registerPageContextExtras.mockClear();
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

  it('auto-registers page AI when ai config is omitted', () => {
    mountCrudPage({});

    expect(mockRefs.appendPageOperations).toHaveBeenCalled();
    expect(mockRefs.registerPageContext).toHaveBeenCalled();
    expect(mockRefs.registerPageContextExtras).toHaveBeenCalled();
  });

  it('passes export modal opener to standard AI ops when export is enabled', () => {
    mountCrudPage({});

    expect(mockRefs.createStandardOperations).toHaveBeenCalled();
    const latestCall = mockRefs.createStandardOperations.mock.calls.at(-1) as
      | [Record<string, unknown>]
      | undefined;
    const latestArgs = latestCall?.[0];
    expect(latestArgs?.openExportModal).toBeTypeOf('function');
  });

  it('skips page AI registration when ai is false', () => {
    mountCrudPage({ ai: false });

    expect(mockRefs.appendPageOperations).not.toHaveBeenCalled();
    expect(mockRefs.registerPageContext).not.toHaveBeenCalled();
    expect(mockRefs.registerPageContextExtras).not.toHaveBeenCalled();
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
