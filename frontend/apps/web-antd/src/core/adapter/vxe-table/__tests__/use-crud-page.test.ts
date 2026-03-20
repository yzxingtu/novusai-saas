import { defineComponent, h } from 'vue';

import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  crudGridProps: [] as Array<Record<string, unknown>>,
  gridQuery: vi.fn(),
  gridReload: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  requestDelete: vi.fn(),
  requestGet: vi.fn(),
}));

vi.mock('@vben/common-ui', () => ({
  useVbenDrawer: () => [defineComponent({ name: 'MockDrawer', render: () => null }), {}],
  useVbenModal: () => [defineComponent({ name: 'MockModal', render: () => null }), {}],
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

vi.mock('#/components/business/dependency-block-modal/index.vue', () => ({
  default: defineComponent({
    name: 'MockDependencyBlockModal',
    setup(_, { expose }) {
      expose({
        open: vi.fn(),
        openPreview: vi.fn(),
      });
      return () => null;
    },
  }),
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
  createStandardOperations: () => [],
  extractFormParams: () => ({}),
}));

vi.mock('#/composables/use-form-state-tracker', () => ({
  formStateTracker: {
    close: vi.fn(),
  },
}));

vi.mock('../components', () => ({
  CrudGrid: defineComponent({
    name: 'MockCrudGrid',
    props: {
      createLabel: { default: '' },
      createPermission: { default: '' },
      onCreate: { default: undefined },
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
    ExportModal: defineComponent({ name: 'MockExportModal', render: () => null }),
    openExportModal: vi.fn(),
  }),
}));

vi.mock('../use-vxe-grid', () => ({
  useGridSearchFormOptions: vi.fn(() => ({})),
  useVbenVxeGrid: () => [
    defineComponent({ name: 'MockGrid', render: () => null }),
    {
      grid: {},
      query: mockRefs.gridQuery,
      reload: mockRefs.gridReload,
    },
  ],
}));

import { useCrudPage } from '../use-crud-page';

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
    mockRefs.crudGridProps.length = 0;
    mockRefs.requestGet.mockReset();
    mockRefs.requestDelete.mockReset();
    mockRefs.messageError.mockReset();
    mockRefs.messageSuccess.mockReset();
    mockRefs.gridQuery.mockReset();
    mockRefs.gridReload.mockReset();
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
            formComponent: defineComponent({ name: 'InlineForm', render: () => null }),
            i18nPrefix: 'admin.test',
          });
        },
        render() {
          const Grid = (this as unknown as { Grid: ReturnType<typeof defineComponent> }).Grid;
          return Grid ? h(Grid) : null;
        },
      }),
    );

    await vm.vm.$nextTick();

    const latestProps = mockRefs.crudGridProps.at(-1);
    expect(latestProps?.onCreate).toBeUndefined();
    expect(latestProps?.createPermission).toBe('');
  });
});
