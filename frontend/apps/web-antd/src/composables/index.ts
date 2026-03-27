/**
 * Composables unified exports / Composables 统一导出
 */

// Declarative table related (re-exported from vxe-table module) / 声明式表格相关（从 vxe-table 模块重新导出）
export {
  type BaseRow,
  type ColumnsFactory,
  type CrudApiConfig,
  type FormMode,
  type ToolbarConfig,
  useCrudPage,
  type UseCrudPageOptions,
} from '#/adapter/vxe-table';

export { useCurrentPageAIPolicy } from './use-ai-page-policy';

export { useAIPermission } from './use-ai-permission';

export { useCrudDrawer, type UseCrudDrawerOptions } from './use-crud-form';

export {
  type CrudListApiConfig,
  useCrudList,
  type UseCrudListOptions,
  type UseCrudListReturn,
} from './use-crud-list';
export {
  type FileValidationResult,
  type FileValidationRules,
  useFileUpload,
} from './use-file-upload';
export {
  buildPageAIFormExtraData,
  createCreateRecordPageOperation,
  createKeywordSearchPageOperation,
  createOpenCurrentPageOperation,
  createOpenPageOperation,
  createOpenRecordPageOperation,
  createParameterizedPageOperation,
  createPrefilledCreatePageOperation,
  createRecordActionPageOperation,
  createRefreshPageOperation,
  createSavePageOperation,
  createSimplePageOperation,
  createStructuredSearchPageOperation,
  createViewDetailPageOperation,
} from './use-page-ai-operation-helpers';
export {
  usePageAIAnchor,
  usePageAIContext,
  usePageAIOperations,
  usePageAIRegistration,
} from './use-page-ai-registration';
