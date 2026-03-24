import type { SortableOptions } from 'sortablejs';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useSortable } from '../use-sortable';

describe('useSortable', () => {
  beforeEach(() => {
    vi.mock('sortablejs/modular/sortable.complete.esm.js', () => ({
      default: {
        create: vi.fn(),
      },
    }));
  });
  it('should call Sortable.create with the correct options', async () => {
    // Create a mock element / 模拟容器 DOM
    const mockElement = document.createElement('div') as HTMLDivElement;

    // Define custom options / 自定义 Sortable 选项
    const customOptions: SortableOptions = {
      group: 'test-group',
      sort: false,
    };

    // Use the useSortable function / 调用 composable
    const { initializeSortable } = useSortable(mockElement, customOptions);

    // Initialize sortable / 创建实例
    await initializeSortable();

    // Import sortablejs to access the mocked create function / 取 mock 的 create
    const Sortable =
      await import('sortablejs/modular/sortable.complete.esm.js');

    // Verify that Sortable.create was called with the correct parameters / 断言参数合并默认项
    expect(Sortable.default.create).toHaveBeenCalledTimes(1);
    expect(Sortable.default.create).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        animation: 300,
        delay: 400,
        delayOnTouchOnly: true,
        ...customOptions,
      }),
    );
  });
});
