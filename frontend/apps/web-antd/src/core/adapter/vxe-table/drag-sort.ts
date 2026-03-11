/**
 * Table drag-sort feature, based on sortablejs, works with vxe-table
 * 表格拖拽排序功能，基于 sortablejs 实现，与 vxe-table 配合使用
 *
 * Design features:
 * 设计特点：
 * 1. Independent state per instance, supports multi-table scenarios / 每个实例独立状态，支持多表格场景
 * 2. Precisely locates DOM via gridApi, no global selectors / 通过 gridApi 精确定位 DOM，不依赖全局选择器
 * 3. Provides auto-init version to reduce boilerplate / 提供自动初始化版本，减少模板代码
 */
import type { VxeGridInstance } from 'vxe-table';

import { nextTick, onMounted, onUnmounted } from 'vue';

import { message } from 'ant-design-vue';
import Sortable from 'sortablejs';

import { $t } from '#/locales';

/**
 * Drag sort configuration / 拖拽排序配置
 */
export interface DragSortConfig {
  /**
   * Update sort API function (single-item mode)
   * 更新排序的 API 函数 (单条模式)
   * @param id Record ID / 记录 ID
   * @param sortOrder New sort value / 新的排序值
   * @deprecated Recommend using onBatchUpdate / 推荐使用 onBatchUpdate
   */
  onUpdate?: (id: number | string, sortOrder: number) => Promise<any>;

  /**
   * Batch update sort API (recommended)
   * 批量更新排序 API (推荐)
   * @param ids Ordered ID list / 有序的 ID 列表
   */
  onBatchUpdate?: (ids: (number | string)[]) => Promise<any>;

  /**
   * Primary key field name / 主键字段名
   * @default 'id'
   */
  keyField?: string;

  /**
   * Success message text / 成功提示文本
   */
  successMessage?: string;

  /**
   * Error message text / 失败提示文本
   */
  errorMessage?: string;

  /**
   * Whether to disable drag / 是否禁用拖拽
   * @default false
   */
  disabled?: boolean;
}

/**
 * Grid getter type, supports getter function or ref object
 * Grid 获取器类型，支持 getter 函数或 ref 对象
 */
export type GridGetter =
  | (() => undefined | VxeGridInstance)
  | { value: undefined | VxeGridInstance };

/**
 * Drag sort composable
 * 拖拽排序 Composable
 *
 * Each call creates independent state, supports multiple tables on same page
 * 每次调用都会创建独立的状态，支持同一页面多个表格
 *
 * @example
 * ```ts
 * // Basic usage - manual init / 基础用法 - 需要手动初始化
 * const { initDragSort } = useTableDragSort(
 *   () => gridApi.grid,
 *   { onUpdate: (id, sortOrder) => api.updateSort(id, { sort_order: sortOrder }) }
 * );
 *
 * // Watch data load then init / 监听数据加载后初始化
 * watch(() => gridApi.grid, (grid) => {
 *   if (grid) nextTick(() => initDragSort());
 * }, { immediate: true });
 * ```
 */
export function useTableDragSort(
  gridGetter: GridGetter,
  config: DragSortConfig,
) {
  // Instance state (closure-isolated, supports multi-table) / 实例状态（闭包隔离，支持多表格）
  let sortableInstance: null | Sortable = null;
  let isInitialized = false;

  const {
    keyField = 'id',
    onUpdate,
    onBatchUpdate,
    successMessage,
    errorMessage,
  } = config;

  /** Get grid instance / 获取 grid 实例 */
  function getGrid(): undefined | VxeGridInstance {
    return typeof gridGetter === 'function' ? gridGetter() : gridGetter.value;
  }

  /**
   * Get table tbody element. Precisely locates via grid instance's $el, avoiding global selector conflicts in multi-table scenarios.
   * 获取表格 tbody 元素。通过 grid 实例的 $el 精确定位，避免全局选择器在多表格场景下冲突
   */
  function getTableBody(): HTMLElement | null {
    const grid = getGrid();
    if (!grid?.$el) return null;
    return grid.$el.querySelector('.vxe-table--body tbody');
  }

  /** Destroy Sortable instance / 销毁 Sortable 实例 */
  function destroy() {
    if (sortableInstance) {
      sortableInstance.destroy();
      sortableInstance = null;
    }
    isInitialized = false;
  }

  /** Refresh table (re-query data) / 刷新表格（重新查询数据） */
  async function refreshTable() {
    destroy();
    const grid = getGrid();
    if (grid) {
      grid.loadData([]);
      await nextTick();
      await grid.commitProxy('query');
      // Re-init drag after data loaded / 数据加载完成后重新初始化拖拽
      await nextTick();
      initDragSort();
    }
  }

  /** Handle drag end event / 处理拖拽结束事件 */
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

    // Get full data and simulate move / 获取全量数据并模拟移动
    const { fullData } = grid.getTableData();
    const tableData = [...(fullData || [])];
    if (tableData.length === 0) return;

    const movedItem = tableData.splice(oldIndex, 1)[0];
    if (!movedItem) return;
    tableData.splice(newIndex, 0, movedItem);

    // Update sort / 更新排序
    try {
      if (onBatchUpdate) {
        // Batch mode: send new order of all IDs on current page / 批量模式：发送当前页所有 ID 的新顺序
        const ids = tableData.map((item: any) => item[keyField]);
        await onBatchUpdate(ids);
      } else if (onUpdate) {
        // Single-item mode: only update affected rows / 单条模式：仅更新受影响的行
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
   * Initialize drag feature, call after table data is loaded
   * 初始化拖拽功能，在表格数据加载完成后调用
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

  // Clean up on component unmount / 组件卸载时清理
  onUnmounted(() => {
    destroy();
  });

  return {
    /** Init drag (call after data loaded) / 初始化拖拽（在数据加载完成后调用） */
    initDragSort,
    /** Destroy drag instance / 销毁拖拽实例 */
    destroy,
    /** Refresh table / 刷新表格 */
    refreshTable,
    /** Whether initialized / 是否已初始化 */
    get isInitialized() {
      return isInitialized;
    },
  };
}

/**
 * Drag sort composable (auto-init version)
 * 拖拽排序 Composable（自动初始化版本）
 *
 * Auto-waits for grid instance to be available then initializes drag.
 * 自动等待 grid 实例可用后初始化拖拽
 * Note: gridApi.grid is not reactive, so polling is used.
 * 注：gridApi.grid 不是响应式的，所以使用轮询等待
 *
 * @example
 * ```ts
 * // Works with useCrudPage - simplest usage / 与 useCrudPage 配合 - 最简用法
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
  const MAX_ATTEMPTS = 50; // Max 5 seconds (50 * 100ms) / 最多尝试 5 秒

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    attempts = 0;
  }

  /**
   * Poll waiting for grid instance available and data loaded. gridApi.grid is not reactive, cannot use watch.
   * 轮询等待 grid 实例可用且数据已加载。gridApi.grid 不是响应式的，无法用 watch 监听
   */
  function startPolling() {
    stopPolling();

    pollTimer = setInterval(() => {
      attempts++;
      const grid =
        typeof gridGetter === 'function' ? gridGetter() : gridGetter.value;

      // Check if grid is mounted / 检查 grid 是否已挂载
      if (grid?.$el) {
        // Check if tbody exists (table rendered) / 检查是否有 tbody 元素（说明表格已渲染）
        const tbody = grid.$el.querySelector('.vxe-table--body tbody');
        if (tbody) {
          // Check if drag-handle exists (data loaded) / 检查是否有 drag-handle（说明数据已加载）
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

      // Timeout handling / 超时处理
      if (attempts >= MAX_ATTEMPTS) {
        stopPolling();
      }
    }, 100);
  }

  // Start polling after component mounted / 组件挂载后开始轮询
  onMounted(() => {
    startPolling();
  });

  // Clean up on component unmount / 组件卸载时清理
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
 * Drag column definition
 * 拖拽列定义
 *
 * Add this column to column config to show drag handle.
 * 在列配置中添加此列以显示拖拽手柄
 * Note: DragHandle renderer is registered in renderers.ts
 * 注：DragHandle 渲染器在 renderers.ts 中注册
 *
 * @example
 * ```ts
 * const columns = [
 *   dragColumn,  // Drag handle column / 拖拽手柄列
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
