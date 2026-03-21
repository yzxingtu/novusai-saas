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
  type UploadOptions,
  type UploadResult,
  useFileUpload,
} from './use-file-upload';

export { useAIPermission } from './use-ai-permission';
export { useCurrentPageAIPolicy } from './use-ai-page-policy';
export {
  usePageAIAnchor,
  usePageAIContext,
  usePageAIOperations,
  usePageAIRegistration,
} from './use-page-ai-registration';
export {
  buildPageAIFormExtraData,
  createCreateRecordPageOperation,
  createKeywordSearchPageOperation,
  createOpenCurrentPageOperation,
  createOpenPageOperation,
  createOpenRecordPageOperation,
  createParameterizedPageOperation,
  createPrefilledCreatePageOperation,
  createRefreshPageOperation,
  createRecordActionPageOperation,
  createSavePageOperation,
  createSimplePageOperation,
  createStructuredSearchPageOperation,
  createViewDetailPageOperation,
} from './use-page-ai-operation-helpers';
