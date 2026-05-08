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
  buildProviderConfigWithPrimaryWireApi,
  getProviderWireApiOptions,
  getProviderWireApiText,
  hasForbiddenProviderEndpointSuffix,
  hasLikelyMissingProviderApiVersion,
  normalizeProviderBaseUrlInput,
  type OpenAICompatibleWireApi,
  resolveProviderPrimaryWireApi,
} from './provider-connection';
export {
  getFormDefaults,
  useColumns,
  useFormSchema,
  useGridFormSchema,
} from './provider-schema';
