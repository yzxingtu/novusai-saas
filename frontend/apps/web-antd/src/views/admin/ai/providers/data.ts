/**
 * AI 供应商管理 - 表格列、搜索和表单配置
 * AI provider admin — columns, search and form config
 */
export {
  getDefaultProviderType,
  getProviderTypeText,
  hasMultipleAdapterTypeOptions,
  loadAdapterTypes,
} from './provider-adapter-types';
export {
  getProviderWireApiOptions,
  getProviderWireApiText,
  hasForbiddenProviderEndpointSuffix,
  hasLikelyMissingProviderApiVersion,
  normalizeProviderBaseUrlInput,
  type OpenAICompatibleWireApi,
  resolveProviderWireApi,
} from './provider-connection';
export {
  getFormDefaults,
  useColumns,
  useFormSchema,
  useGridFormSchema,
} from './provider-schema';
export {
  buildProviderWebSearchConfigFromForm,
  getProviderWebSearchPublicProviderOptions,
  getProviderWebSearchRuntimeSummary,
  getProviderWebSearchStrategyOptions,
  getProviderWebSearchStrategyText,
  type ProviderWebSearchConfigWithAdvancedFields,
  type ProviderWebSearchStrategy,
  type PublicWebSearchProvider,
  resolveProviderWebSearchConfig,
  shouldWarnProviderWebSearchAutoFallback,
} from './provider-web-search';
