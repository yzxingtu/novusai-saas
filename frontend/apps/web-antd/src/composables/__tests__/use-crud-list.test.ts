import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useCrudList } from '../use-crud-list';

const mockRefs = vi.hoisted(() => ({
  appendPageOperations: vi.fn(() => vi.fn()),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  registerPageContext: vi.fn(() => vi.fn()),
  registerPageContextExtras: vi.fn(() => vi.fn()),
  requestDelete: vi.fn(),
  requestGet: vi.fn(),
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
    meta: {},
    path: '/admin/items',
  }),
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    confirm: vi.fn(),
    warning: vi.fn(),
  },
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

vi.mock('#/components/business/ai-slide-panel', () => ({
  appendPageOperations: mockRefs.appendPageOperations,
  registerPageContext: mockRefs.registerPageContext,
  registerPageContextExtras: mockRefs.registerPageContextExtras,
}));

vi.mock('#/components/business/ai-slide-panel/page-key-utils', () => ({
  normalizePageKey: (value: string) => value,
}));

vi.mock('#/components/business/ai-slide-panel/page-context-registry', () => ({
  registerPageContext: mockRefs.registerPageContext,
}));

vi.mock('../use-ai-operations', () => ({
  createStandardOperations: () => [],
  extractFormParams: () => ({}),
}));

vi.mock('../use-form-state-tracker', () => ({
  formStateTracker: {
    close: vi.fn(),
    isOpen: vi.fn(() => false),
  },
}));

function mountCrudList(options: Record<string, unknown> = {}) {
  const wrapper = mount(
    defineComponent({
      name: 'UseCrudListHarness',
      setup() {
        return useCrudList({
          api: {
            list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
            resource: '/admin/items',
          },
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

describe('useCrudList', () => {
  beforeEach(() => {
    mockRefs.appendPageOperations.mockClear();
    mockRefs.requestGet.mockReset();
    mockRefs.requestDelete.mockReset();
    mockRefs.messageError.mockReset();
    mockRefs.messageSuccess.mockReset();
    mockRefs.registerPageContext.mockClear();
    mockRefs.registerPageContextExtras.mockClear();
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

    mockRefs.requestGet.mockRejectedValue({ response: { status: 404 } });

    await vm.onDelete({ id: 5, name: 'Row 5' });

    expect(customDelete).toHaveBeenCalledWith(5);
    expect(mockRefs.requestDelete).not.toHaveBeenCalled();
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.test.messages.deleteSuccess',
    );
  });

  it('auto-registers page AI when ai config is omitted', async () => {
    mountCrudList();
    await flushPromises();

    expect(mockRefs.appendPageOperations).toHaveBeenCalled();
    expect(mockRefs.registerPageContext).toHaveBeenCalled();
    expect(mockRefs.registerPageContextExtras).toHaveBeenCalled();
  });

  it('skips page AI registration when ai is false', async () => {
    mountCrudList({ ai: false });
    await flushPromises();

    expect(mockRefs.appendPageOperations).not.toHaveBeenCalled();
    expect(mockRefs.registerPageContext).not.toHaveBeenCalled();
    expect(mockRefs.registerPageContextExtras).not.toHaveBeenCalled();
  });
});
