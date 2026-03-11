/**
 * Form adapter layer
 * 表单适配层
 *
 * Unified export of form-related functionality
 * 统一导出表单相关功能
 */

// Schema helper functions / Schema 辅助函数
export {
  apiSelect,
  dateField,
  dividerField,
  iconField,
  inputField,
  numberField,
  searchDateRange,
  searchInput,
  // General helper functions / 通用辅助函数
  select,
  statusSelect,
  switchField,
  textareaField,
  treeSelect,
} from './schema-helpers';
// Type exports / 类型导出
export type {
  ApiSelectOptions,
  SearchDateRangeOptions,
  SearchInputOptions,
  StatusSelectOptions,
} from './schema-helpers';

// Core form Hook and types / 核心表单 Hook 和类型
export { initSetupVbenForm, useVbenForm, z } from './setup';

export type { VbenFormProps, VbenFormSchema } from './setup';
