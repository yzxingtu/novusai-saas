/**
 * 声明式表格模块
 *
 * 统一导出所有表格相关功能
 */

// 拖拽排序
export {
  dragColumn,
  type DragSortConfig,
  type GridGetter,
  useAutoTableDragSort,
  useTableDragSort,
} from './drag-sort';

// ============ 扩展功能 ============
// 批量选择
export {
  checkboxColumn,
  clearSelection,
  getSelectedIds,
  getSelectedRows,
  seqColumn,
} from './extensions';

// Excel 导出
export {
  type ExportColumn,
  type ExportOptions,
  exportToExcel,
} from './extensions';

// 导出弹窗组件
export { ExportModal, useExportModal } from './components';

// 展开行
export {
  createExpandConfig,
  expandColumn,
  type ExpandConfig,
} from './extensions';

// ============ 初始化（应用启动时调用） ============
export { setupVxeTable } from './setup';

// ============ 类型定义 ============
export type {
  BaseRow,
  ColumnsFactory,
  CrudApiConfig,
  FormMode,
  GridOptionsConfig,
  OnActionClickFn,
  OnActionClickParams,
  ToolbarConfig,
  UseCrudPageOptions,
  VxeTableGridOptions,
} from './types';

// ============ 核心 Hook ============
// 推荐使用 useCrudPage，一行代码搞定列表页
export { useCrudPage } from './use-crud-page';

// 基础 Hook（useCrudPage 内部使用，也可单独使用）
export {
  useGridOptions,
  useGridSearchFormOptions,
  useVbenVxeGrid,
} from './use-vxe-grid';

// ============ 从 vben 插件导出基础类型 ============
export type * from '@vben/plugins/vxe-table';
