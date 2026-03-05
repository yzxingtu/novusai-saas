/**
 * 表格拖拽排序功能
 * 基于 sortablejs 实现，与 vxe-table 配合使用
 *
 * 设计特点：
 * 1. 每个实例独立状态，支持多表格场景
 * 2. 通过 gridApi 精确定位 DOM，不依赖全局选择器
 * 3. 提供自动初始化版本，减少模板代码
 */
import type { VxeGridInstance } from 'vxe-table';

import { nextTick, onMounted, onUnmounted } from 'vue';

import { message } from 'ant-design-vue';
import Sortable from 'sortablejs';

import { $t } from '#/locales';

/**
 * 拖拽排序配置
 */
export interface DragSortConfig {
  /**
   * 更新排序的 API 函数 (单条模式)
   * @param id 记录 ID
   * @param sortOrder 新的排序值
   * @deprecated 推荐使用 onBatchUpdate
   */
  onUpdate?: (id: number | string, sortOrder: number) => Promise<any>;

  /**
   * 批量更新排序 API (推荐)
   * @param ids 有序的 ID 列表
   */
  onBatchUpdate?: (ids: (number | string)[]) => Promise<any>;

  /**
   * 主键字段名
   * @default 'id'
   */
  keyField?: string;

  /**
   * 成功提示文本
   */
  successMessage?: string;

  /**
   * 失败提示文本
   */
  errorMessage?: string;

  /**
   * 是否禁用拖拽
   * @default false
   */
  disabled?: boolean;
}

/**
 * Grid 获取器类型
 * 支持 getter 函数或 ref 对象
 */
export type GridGetter =
  | (() => undefined | VxeGridInstance)
  | { value: undefined | VxeGridInstance };

/**
 * 拖拽排序 Composable
 *
 * 每次调用都会创建独立的状态，支持同一页面多个表格
 *
 * @example
 * ```ts
 * // 基础用法 - 需要手动初始化
 * const { initDragSort } = useTableDragSort(
 *   () => gridApi.grid,
 *   { onUpdate: (id, sortOrder) => api.updateSort(id, { sort_order: sortOrder }) }
 * );
 *
 * // 监听数据加载后初始化
 * watch(() => gridApi.grid, (grid) => {
 *   if (grid) nextTick(() => initDragSort());
 * }, { immediate: true });
 * ```
 */
export function useTableDragSort(
  gridGetter: GridGetter,
  config: DragSortConfig,
) {
  // 实例状态（闭包隔离，支持多表格）
  let sortableInstance: null | Sortable = null;
  let isInitialized = false;

  const {
    keyField = 'id',
    onUpdate,
    onBatchUpdate,
    successMessage,
    errorMessage,
  } = config;

  /** 获取 grid 实例 */
  function getGrid(): undefined | VxeGridInstance {
    return typeof gridGetter === 'function' ? gridGetter() : gridGetter.value;
  }

  /**
   * 获取表格 tbody 元素
   * 通过 grid 实例的 $el 精确定位，避免全局选择器在多表格场景下冲突
   */
  function getTableBody(): HTMLElement | null {
    const grid = getGrid();
    if (!grid?.$el) return null;
    return grid.$el.querySelector('.vxe-table--body tbody');
  }

  /** 销毁 Sortable 实例 */
  function destroy() {
    if (sortableInstance) {
      sortableInstance.destroy();
      sortableInstance = null;
    }
    isInitialized = false;
  }

  /** 刷新表格（重新查询数据） */
  async function refreshTable() {
    destroy();
    const grid = getGrid();
    if (grid) {
      grid.loadData([]);
      await nextTick();
      await grid.commitProxy('query');
      // 数据加载完成后重新初始化拖拽
      await nextTick();
      initDragSort();
    }
  }

  /** 处理拖拽结束事件 */
  async function handleDragEnd(evt: Sortable.SortableEvent) {
    const { oldIndex, newIndex } = evt;
    if (
      oldIndex === undefined ||
      newIndex === undefined ||
      oldIndex === newIndex
    ) {
      return;
    }

    const grid = getGrid();
    if (!grid) return;

    // 获取全量数据并模拟移动
    const { fullData } = grid.getTableData();
    const tableData = [...(fullData || [])];
    if (tableData.length === 0) return;

    const movedItem = tableData.splice(oldIndex, 1)[0];
    if (!movedItem) return;
    tableData.splice(newIndex, 0, movedItem);

    // 更新排序
    try {
      if (onBatchUpdate) {
        // 批量模式：发送当前页所有 ID 的新顺序
        const ids = tableData.map((item: any) => item[keyField]);
        await onBatchUpdate(ids);
      } else if (onUpdate) {
        // 单条模式：仅更新受影响的行
        const minIdx = Math.min(oldIndex, newIndex);
        const maxIdx = Math.max(oldIndex, newIndex);
        const updates: Array<{ id: number | string; sortOrder: number }> = [];

        for (let i = minIdx; i <= maxIdx; i++) {
          const item = tableData[i];
          updates.push({ id: (item as any)[keyField], sortOrder: i });
        }
        await Promise.all(updates.map((u) => onUpdate(u.id, u.sortOrder)));
      }
      message.success(successMessage || $t('shared.common.sortSuccess'));
    } catch {
      message.error(errorMessage || $t('shared.common.sortFailed'));
    } finally {
      await refreshTable();
    }
  }

  /**
   * 初始化拖拽功能
   * 在表格数据加载完成后调用
   */
  function initDragSort() {
    destroy();

    if (config.disabled) return;

    const gridEl = getTableBody();
    if (!gridEl) return;

    sortableInstance = Sortable.create(gridEl, {
      animation: 150,
      handle: '.drag-handle',
      ghostClass: 'sortable-ghost',
      onEnd: handleDragEnd,
    });

    isInitialized = true;
  }

  // 组件卸载时清理
  onUnmounted(() => {
    destroy();
  });

  return {
    /** 初始化拖拽（在数据加载完成后调用） */
    initDragSort,
    /** 销毁拖拽实例 */
    destroy,
    /** 刷新表格 */
    refreshTable,
    /** 是否已初始化 */
    get isInitialized() {
      return isInitialized;
    },
  };
}

/**
 * 拖拽排序 Composable（自动初始化版本）
 *
 * 自动等待 grid 实例可用后初始化拖拽
 * 注：gridApi.grid 不是响应式的，所以使用轮询等待
 *
 * @example
 * ```ts
 * // 与 useCrudPage 配合 - 最简用法
 * const { Grid, gridApi } = useCrudPage({ ... });
 *
 * useAutoTableDragSort(
 *   () => gridApi.grid,
 *   { onUpdate: (id, sortOrder) => api.updateSort(id, { sort_order: sortOrder }) }
 * );
 * ```
 */
export function useAutoTableDragSort(
  gridGetter: GridGetter,
  config: DragSortConfig,
) {
  const dragSort = useTableDragSort(gridGetter, config);

  let pollTimer: null | ReturnType<typeof setInterval> = null;
  let attempts = 0;
  const MAX_ATTEMPTS = 50; // 最多尝试 5 秒 (50 * 100ms)

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    attempts = 0;
  }

  /**
   * 轮询等待 grid 实例可用且数据已加载
   * gridApi.grid 不是响应式的，无法用 watch 监听
   */
  function startPolling() {
    stopPolling();

    pollTimer = setInterval(() => {
      attempts++;
      const grid =
        typeof gridGetter === 'function' ? gridGetter() : gridGetter.value;

      // 检查 grid 是否已挂载
      if (grid?.$el) {
        // 检查是否有 tbody 元素（说明表格已渲染）
        const tbody = grid.$el.querySelector('.vxe-table--body tbody');
        if (tbody) {
          // 检查是否有 drag-handle（说明数据已加载）
          const handles = tbody.querySelectorAll('.drag-handle');
          if (handles.length > 0) {
            stopPolling();
            nextTick(() => {
              dragSort.initDragSort();
            });
            return;
          }
        }
      }

      // 超时处理
      if (attempts >= MAX_ATTEMPTS) {
        stopPolling();
      }
    }, 100);
  }

  // 组件挂载后开始轮询
  onMounted(() => {
    startPolling();
  });

  // 组件卸载时清理
  onUnmounted(() => {
    stopPolling();
    dragSort.destroy();
  });

  const hot = (
    import.meta as ImportMeta & { hot?: { dispose: (cb: () => void) => void } }
  ).hot;
  if (hot) {
    hot.dispose(() => {
      stopPolling();
      dragSort.destroy();
    });
  }

  return dragSort;
}

/**
 * 拖拽列定义
 *
 * 在列配置中添加此列以显示拖拽手柄
 * 注：DragHandle 渲染器在 renderers.ts 中注册
 *
 * @example
 * ```ts
 * const columns = [
 *   dragColumn,  // 拖拽手柄列
 *   { field: 'name', title: '名称' },
 *   // ...
 * ];
 * ```
 */
export const dragColumn = {
  field: '_drag',
  title: '',
  width: 40,
  align: 'center' as const,
  cellRender: {
    name: 'DragHandle',
  },
};
