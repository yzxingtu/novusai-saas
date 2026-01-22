/**
 * Composables 统一导出
 */

// 声明式表格相关（从 vxe-table 模块重新导出）
export {
  type BaseRow,
  type ColumnsFactory,
  type CrudApiConfig,
  type FormMode,
  type ToolbarConfig,
  useCrudPage,
  type UseCrudPageOptions,
} from '#/adapter/vxe-table';

export { useCrudDrawer, type UseCrudDrawerOptions } from './use-crud-form';
