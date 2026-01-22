/**
 * 表单适配层
 *
 * 统一导出表单相关功能
 */

// Schema 辅助函数
export {
  apiSelect,
  dateField,
  dividerField,
  inputField,
  numberField,
  searchDateRange,
  searchInput,
  // 通用辅助函数
  select,
  statusSelect,
  switchField,
  textareaField,
  treeSelect,
} from './schema-helpers';
// 类型导出
export type {
  ApiSelectOptions,
  SearchDateRangeOptions,
  SearchInputOptions,
  StatusSelectOptions,
} from './schema-helpers';

// 核心表单 Hook 和类型
export { initSetupVbenForm, useVbenForm, z } from './setup';

export type { VbenFormProps, VbenFormSchema } from './setup';
