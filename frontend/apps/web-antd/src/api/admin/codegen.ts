/**
 * CRUD 代码生成器管理 API / Codegen Admin API
 *
 * 21 个端点，DEBUG 模式下可用 / 21 endpoints, available in DEBUG mode only
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';
import { downloadBlob } from '#/utils/download';

const PREFIX = '/admin/codegen';

// ============================================================
// 类型定义 / Type definitions
// ============================================================

/** 代码生成配置信息 / Codegen config info */
export interface CodegenConfigInfo {
  id: number;
  name: string;
  resource: string;
  module: string;
  display_name: string;
  display_name_en: string;
  status: string;
  config_json: Record<string, unknown>;
  last_generated_at: null | string;
  generation_count: number;
  generated_files: null | Record<string, unknown>;
  config_hash: null | string;
  last_error: null | string;
  created_at: string;
  updated_at: string;
}

/** 创建配置请求 / Create config request */
export interface CodegenConfigCreateInput {
  name: string;
  resource: string;
  module: string;
  display_name: string;
  display_name_en: string;
  config_json?: Record<string, unknown>;
}

/** 更新配置请求 / Update config request */
export interface CodegenConfigUpdateInput {
  name?: string;
  resource?: string;
  module?: string;
  display_name?: string;
  display_name_en?: string;
  config_json?: Record<string, unknown>;
}

/** 预览文件 / Preview file */
export interface PreviewFile {
  path: string;
  type: string;
  language: string;
  content: string;
  line_count: number;
  original_content?: null | string;
  new_content?: null | string;
  diff?: null | string;
}

/** 预览结果 / Preview result */
export interface PreviewResult {
  success: boolean;
  error?: string;
  files: PreviewFile[];
  summary: {
    create_count: number;
    modify_count: number;
    backend_files: number;
    frontend_files: number;
    total_lines: number;
  };
  warnings: string[];
  conflicts: Array<Record<string, string>>;
}

/** 生成结果 / Generate result */
export interface GenerateResult {
  success: boolean;
  files_created: string[];
  files_modified: string[];
  conflicts: Array<Record<string, string>>;
  errors: string[];
  backup_dir: null | string;
}

/** 回滚结果 / Rollback result */
export interface RollbackResult {
  success: boolean;
  files_deleted: string[];
  files_modified: string[];
  files_skipped: Array<Record<string, unknown>>;
  manual_steps: string[];
  errors: string[];
}

/** 校验错误 / Validation error */
export interface ValidationError {
  code: string;
  message: string;
  path: string;
  field: string;
}

/** 校验结果 / Validation result */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: string[];
}

/** 表信息 / Table info */
export interface TableInfo {
  name: string;
  comment: null | string;
  row_count: number;
  has_model: boolean;
}

/** 列信息 / Column info */
export interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  default: null | string;
  primary_key: boolean;
  unique: boolean;
  comment: null | string;
  foreign_keys: Array<Record<string, unknown>>;
  suggested_config: Record<string, unknown>;
}

/** 类型信息 / Type info */
export interface TypeInfo {
  type: string;
  python_type: string;
  ts_type: string;
  form_component: string;
  search_type: null | string;
}

/** 组件信息 / Component info */
export interface ComponentInfo {
  name: string;
  label: string;
  category: string;
}

/** 预设信息 / Preset info */
export interface PresetInfo {
  name: string;
  label_zh: string;
  label_en: string;
  description_zh?: string;
  description_en?: string;
}

// ============================================================
// 配置 CRUD / Config CRUD
// ============================================================

/** 获取配置列表 / Get config list */
export async function getCodegenConfigListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<{ items: CodegenConfigInfo[]; total: number; page: number; page_size: number }> {
  return requestClient.get(PREFIX + '/configs', { params, ...options });
}

/** 获取配置详情 / Get config detail */
export async function getCodegenConfigDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<CodegenConfigInfo> {
  return requestClient.get(`${PREFIX}/configs/${id}`, options);
}

/** 创建配置 / Create config */
export async function createCodegenConfigApi(
  data: CodegenConfigCreateInput,
  options?: ApiRequestOptions,
): Promise<CodegenConfigInfo> {
  return requestClient.post(PREFIX + '/configs', data, options);
}

/** 更新配置 / Update config */
export async function updateCodegenConfigApi(
  id: number,
  data: CodegenConfigUpdateInput,
  options?: ApiRequestOptions,
): Promise<CodegenConfigInfo> {
  return requestClient.put(`${PREFIX}/configs/${id}`, data, options);
}

/** 删除配置 / Delete config */
export async function deleteCodegenConfigApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  return requestClient.delete(`${PREFIX}/configs/${id}`, options);
}

/** 复制配置 / Duplicate config */
export async function duplicateCodegenConfigApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<CodegenConfigInfo> {
  return requestClient.post(`${PREFIX}/configs/${id}/duplicate`, {}, options);
}

/** 配置版本项 / Config version item */
export interface CodegenVersionItem {
  id: number;
  config_id: number;
  created_at: null | string;
  note: null | string;
}

/** 获取配置版本列表 / Get config version list */
export async function getCodegenConfigVersionsApi(
  id: number,
  params?: { limit?: number },
  options?: ApiRequestOptions,
): Promise<CodegenVersionItem[]> {
  return requestClient.get(`${PREFIX}/configs/${id}/versions`, { params, ...options });
}

/** 获取配置的指定版本 config_json / Get config version's config_json */
export async function getCodegenConfigVersionApi(
  id: number,
  vid: number,
  options?: ApiRequestOptions,
): Promise<{ config_json: Record<string, unknown> }> {
  return requestClient.get(`${PREFIX}/configs/${id}/versions/${vid}`, options);
}

/** 恢复到指定版本 / Restore config to version */
export async function postCodegenConfigRestoreVersionApi(
  id: number,
  vid: number,
  options?: ApiRequestOptions,
): Promise<CodegenConfigInfo> {
  return requestClient.post(`${PREFIX}/configs/${id}/versions/${vid}/restore`, {}, options);
}

// ============================================================
// 元数据 / Metadata
// ============================================================

/** 获取类型列表 / Get type list */
export async function getCodegenTypesApi(
  options?: ApiRequestOptions,
): Promise<TypeInfo[]> {
  return requestClient.get(PREFIX + '/types', options);
}

/** 获取组件列表 / Get component list */
export async function getCodegenComponentsApi(
  options?: ApiRequestOptions,
): Promise<ComponentInfo[]> {
  return requestClient.get(PREFIX + '/components', options);
}

/** 获取模型列表 / Get model list */
export async function getCodegenModelsApi(
  options?: ApiRequestOptions,
): Promise<string[]> {
  return requestClient.get(PREFIX + '/models', options);
}

/** 获取预设列表（预设名称）/ Get preset list (preset names) */
export async function getCodegenPresetsApi(
  options?: ApiRequestOptions,
): Promise<string[]> {
  return requestClient.get(PREFIX + '/presets', options);
}

/** 预设详情响应 / Preset detail response */
export interface PresetDetailResponse {
  name: string;
  content: string;
  parsed: Record<string, unknown>;
}

/** 获取预设详情 / Get preset detail */
export async function getCodegenPresetApi(
  name: string,
  options?: ApiRequestOptions,
): Promise<PresetDetailResponse> {
  const data = await requestClient.get<PresetDetailResponse>(
    `${PREFIX}/presets/${encodeURIComponent(name)}`,
    options,
  );
  return data;
}

/** 获取父资源列表（字符串数组）/ Get parent resource list (string array) */
export async function getCodegenParentResourcesApi(
  options?: ApiRequestOptions,
): Promise<string[]> {
  return requestClient.get(PREFIX + '/parent-resources', options);
}

/** 代码生成器选项（parent_resources、system_modules、field_templates）/ Codegen options */
export interface CodegenOptions {
  parent_resources: string[];
  system_modules: string[];
  field_templates: Record<string, Array<Record<string, unknown>>>;
}

export async function getCodegenOptionsApi(
  options?: ApiRequestOptions,
): Promise<CodegenOptions> {
  return requestClient.get(PREFIX + '/options', options);
}

// ============================================================
// DB 反射 / DB introspection
// ============================================================

/** 获取数据库表列表 / Get DB table list */
export async function getCodegenDbTablesApi(
  options?: ApiRequestOptions,
): Promise<TableInfo[]> {
  return requestClient.get(PREFIX + '/db/tables', options);
}

/** 获取表列信息 / Get table columns */
export async function getCodegenDbColumnsApi(
  tableName: string,
  options?: ApiRequestOptions,
): Promise<ColumnInfo[]> {
  return requestClient.get(
    `${PREFIX}/db/tables/${encodeURIComponent(tableName)}/columns`,
    options,
  );
}

/** 表行项（关联下拉用）/ Table row item for relation select */
export interface CodegenDbTableRowItem {
  value: number | string;
  label: string;
}

/** 获取表行数据（供关联下拉预览）/ Get table rows for relation select preview */
export async function getCodegenDbTableRowsApi(
  tableName: string,
  params?: {
    value_field?: string;
    display_field?: string;
    limit?: number;
    search?: string;
  },
  options?: ApiRequestOptions,
): Promise<{ items: CodegenDbTableRowItem[]; total: number }> {
  return requestClient.get(
    `${PREFIX}/db/tables/${encodeURIComponent(tableName)}/rows`,
    { params: params ?? {}, ...options },
  );
}

/** 从表导入配置 / Import config from table */
export async function postCodegenDbImportApi(
  body: { table_name: string },
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return requestClient.post(PREFIX + '/db/import', body, options);
}

// ============================================================
// 核心操作 / Core operations
// ============================================================

/** 校验配置 / Validate config */
export async function postCodegenValidateApi(
  body: { config_json: Record<string, unknown> },
  options?: ApiRequestOptions,
): Promise<ValidationResult> {
  return requestClient.post(PREFIX + '/validate', body, options);
}

/** 预览生成 / Preview generation */
export async function postCodegenPreviewApi(
  body: { config_json: Record<string, unknown> },
  params?: { step?: 'model' | 'controller' | 'frontend' },
  options?: ApiRequestOptions,
): Promise<PreviewResult> {
  return requestClient.post(PREFIX + '/preview', body, {
    ...options,
    params,
  });
}

/** 预览 ZIP 下载（不写入项目）/ Preview ZIP download (no write) */
export async function downloadCodegenPreviewZipApi(
  body: { config_json: Record<string, unknown> },
  params?: { step?: 'model' | 'controller' | 'frontend' },
): Promise<void> {
  const blob = await requestClient.download<Blob>(
    PREFIX + '/preview/download',
    {
      method: 'POST',
      data: body,
      params,
    },
  );
  downloadBlob(blob, { filename: 'codegen_preview.zip' });
}

/** 执行生成 / Execute generation */
export async function postCodegenGenerateApi(
  body: { config_id?: number; config_json?: Record<string, unknown>; force?: boolean },
  options?: ApiRequestOptions,
): Promise<GenerateResult> {
  return requestClient.post(PREFIX + '/generate', body, options);
}

/** 下载生成代码 ZIP / Download generated code ZIP */
export async function downloadCodegenZipApi(configId: number): Promise<void> {
  const blob = await requestClient.download<Blob>(
    `${PREFIX}/download/${configId}`,
  );
  downloadBlob(blob, { filename: `codegen_${configId}.zip` });
}

/** 获取生成历史 / Get generation history */
export async function getCodegenHistoryApi(
  params?: { resource?: string },
  options?: ApiRequestOptions,
): Promise<
  Array<{
    resource: string;
    module: string;
    generated_at: string;
    config_id: number;
    file_count: number;
  }>
> {
  return requestClient.get(PREFIX + '/history', { params, ...options });
}

// ============================================================
// 回滚 / Rollback
// ============================================================

/** 回滚生成的代码 / Rollback generated code */
export async function deleteCodegenRollbackApi(
  id: number,
  params?: { force?: boolean; dry_run?: boolean },
  options?: ApiRequestOptions,
): Promise<RollbackResult> {
  return requestClient.delete(`${PREFIX}/configs/${id}/rollback`, {
    ...options,
    params,
  });
}
