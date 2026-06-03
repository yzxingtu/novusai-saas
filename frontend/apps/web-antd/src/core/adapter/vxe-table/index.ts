/**
 * Declarative table module
 * 声明式表格模块
 *
 * Unified export of all table-related functionality
 * 统一导出所有表格相关功能
 */

// Export modal components / 导出弹窗组件
export { ExportModal, useExportModal } from './components';

// Drag sort / 拖拽排序
export {
  dragColumn,
  type DragSortConfig,
  type GridGetter,
  useAutoTableDragSort,
  useTableDragSort,
} from './drag-sort';

// ============ Extensions / 扩展功能 ============
// Batch selection / 批量选择
export {
  checkboxColumn,
  clearSelection,
  getSelectedIds,
  getSelectedRows,
  seqColumn,
} from './extensions';

// Excel export / Excel 导出
export {
  type ExportColumn,
  type ExportOptions,
  exportToExcel,
} from './extensions';

// Expandable rows / 展开行
export {
  createExpandConfig,
  expandColumn,
  type ExpandConfig,
} from './extensions';

// ============ Initialization (called at app startup) / 初始化（应用启动时调用） ============
export { setupVxeTable } from './setup';

// ============ Type Definitions / 类型定义 ============
export type {
  BaseRow,
  ColumnsFactory,
  CrudApiConfig,
  FormMode,
  GridOptionsConfig,
  OnActionClickFn,
  OnActionClickParams,
  QuickSearchConfig,
  QuickSearchFieldOption,
  SearchConfig,
  ToolbarConfig,
  UseCrudPageOptions,
  VxeTableGridOptions,
} from './types';

// ============ Core Hooks / 核心 Hook ============
// Recommend useCrudPage - one-liner for list pages / 推荐使用 useCrudPage，一行代码搞定列表页
export { useCrudPage } from './use-crud-page';

// Base Hooks (used internally by useCrudPage, can also be used standalone) / 基础 Hook（useCrudPage 内部使用，也可单独使用）
export {
  useGridOptions,
  useGridSearchFormOptions,
  useVbenVxeGrid,
} from './use-vxe-grid';

// ============ Export base types from vben plugin / 从 vben 插件导出基础类型 ============
export type * from '@vben/plugins/vxe-table';
