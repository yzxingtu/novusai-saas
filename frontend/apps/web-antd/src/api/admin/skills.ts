/**
 * Admin skill management API / 管理端技能管理 API
 * Backend: /admin/ai/skills/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Skill info (admin includes tenant_id) / 技能信息（管理端含 tenant_id） */
export interface AdminSkillInfo {
  id: number;
  tenant_id: null | number;
  package_id: number;
  name: string;
  description: null | string;
  avatar: null | string;
  type: string;
  config: null | Record<string, unknown>;
  input_schema: null | Record<string, unknown>;
  output_schema: null | Record<string, unknown>;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  timeout: number;
  toolkit_content: null | string;
  toolkit_meta: null | Record<string, unknown>;
  created_at: string;
  updated_at: string;
  source_plugin: null | string;
  plugin_tools: null | PluginToolDefinition[];
}

/** Create skill request / 创建技能请求 */
export interface AdminSkillCreateRequest {
  package_id: number;
  name: string;
  description?: null | string;
  avatar?: null | string;
  type?: string;
  config?: null | Record<string, unknown>;
  input_schema?: null | Record<string, unknown>;
  output_schema?: null | Record<string, unknown>;
  is_active?: boolean;
  sort_order?: number;
  timeout?: number;
  toolkit_content?: null | string;
}

/** Update skill request / 更新技能请求 */
export interface AdminSkillUpdateRequest {
  name?: null | string;
  description?: null | string;
  avatar?: null | string;
  type?: null | string;
  config?: null | Record<string, unknown>;
  input_schema?: null | Record<string, unknown>;
  output_schema?: null | Record<string, unknown>;
  is_active?: boolean | null;
  sort_order?: null | number;
  timeout?: null | number;
  toolkit_content?: null | string;
}

/** Skill type option / 技能类型选项 */
export interface SkillTypeOption {
  value: string;
  label: string;
}

/** Skill list paginated response / 技能列表分页响应 */
interface AdminSkillPageResponse {
  items: AdminSkillInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** Agent skill binding picker option extra / 智能体技能绑定选择器 extra */
export interface AdminSkillSelectOptionExtra {
  description: null | string;
  is_active: boolean;
  is_system: boolean;
  package_id: number;
  package_name: string;
  skill_key: null | string;
  skill_type: string;
  source_plugin: null | string;
  tenant_id: null | number;
}

/** Agent skill binding picker option / 智能体技能绑定选择器选项 */
export interface AdminSkillSelectOption {
  disabled?: boolean;
  extra?: AdminSkillSelectOptionExtra;
  label: string;
  value: number;
}

/** Agent skill binding picker response / 智能体技能绑定选择器分页响应 */
export interface AdminSkillBindingSelectResponse {
  has_more?: boolean;
  items: AdminSkillSelectOption[];
  page?: number;
  page_size?: number;
  total?: number;
}

// ============================================================
// API functions / API 接口
// ============================================================

const PREFIX = '/admin/ai/skills';

/** Get available skill types / 获取可用技能类型列表 */
export async function getSkillTypesApi(
  options?: ApiRequestOptions,
): Promise<SkillTypeOption[]> {
  return requestClient.get<SkillTypeOption[]>(`${PREFIX}/skill-types`, options);
}

/** Paginated skills for admin agent binding picker / 管理端智能体技能绑定选择器 */
export async function getSkillBindingSelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AdminSkillBindingSelectResponse> {
  return requestClient.get<AdminSkillBindingSelectResponse>(
    `${PREFIX}/select`,
    {
      params,
      ...options,
    },
  );
}

/** Get skill list (all tenants) / 获取技能列表（全企业） */
export async function getSkillListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AdminSkillPageResponse> {
  return requestClient.get<AdminSkillPageResponse>(PREFIX, {
    params,
    ...options,
  });
}

/** Get skill detail / 获取技能详情 */
export async function getSkillDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AdminSkillInfo> {
  return requestClient.get<AdminSkillInfo>(`${PREFIX}/${id}`, options);
}

/** Create skill / 创建技能 */
export async function createSkillApi(
  data: AdminSkillCreateRequest,
  options?: ApiRequestOptions,
): Promise<AdminSkillInfo> {
  return requestClient.post<AdminSkillInfo>(PREFIX, data, options);
}

/** Update skill / 更新技能 */
export async function updateSkillApi(
  id: number,
  data: AdminSkillUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AdminSkillInfo> {
  return requestClient.put<AdminSkillInfo>(`${PREFIX}/${id}`, data, options);
}

/** Delete skill / 删除技能 */
export async function deleteSkillApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** Skill test result / 技能测试结果 */
export interface AdminSkillTestResult {
  success: boolean;
  message: string;
  details: null | Record<string, unknown>;
}

/** Plugin skill tool definition / 插件技能工具定义 */
export interface PluginToolDefinition {
  name: string;
  description: string;
  parameters: Array<{
    default?: unknown;
    description: string;
    name: string;
    required: boolean;
    type: string;
  }>;
  timeout?: number;
}

/** Get skill tool definitions (plugin skills) / 获取技能工具定义列表 */
export async function getSkillToolsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<PluginToolDefinition[]> {
  return requestClient.get<PluginToolDefinition[]>(
    `${PREFIX}/${id}/tools`,
    options,
  );
}

/** Test skill config / 测试技能配置 */
export async function testSkillApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AdminSkillTestResult> {
  return requestClient.post<AdminSkillTestResult>(
    `${PREFIX}/${id}/test`,
    {},
    options,
  );
}

/** Toggle skill status / 切换技能状态 */
export async function toggleSkillStatusApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AdminSkillInfo> {
  return requestClient.put<AdminSkillInfo>(
    `${PREFIX}/${id}/status`,
    {},
    options,
  );
}

/** Skill call statistics / 技能调用统计 */
export interface AdminSkillStats {
  skill_id: number;
  total_calls: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  avg_duration_ms: number;
  last_called_at: null | string;
}

/** Skill call statistics overview item / 技能调用统计概览项 */
export interface AdminSkillStatsOverviewItem {
  skill_id: number;
  skill_name: string;
  skill_type: string;
  total_calls: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  avg_duration_ms: number;
  last_called_at: null | string;
}

/** Get skill call statistics / 获取技能调用统计 */
export async function getSkillStatsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AdminSkillStats> {
  return requestClient.get<AdminSkillStats>(`${PREFIX}/${id}/stats`, options);
}

/** Skill export item / 导出技能结果项 */
export interface SkillExportItem {
  name: string;
  description: null | string;
  avatar: null | string;
  type: string;
  config: null | Record<string, unknown>;
  input_schema: null | Record<string, unknown>;
  output_schema: null | Record<string, unknown>;
  timeout: number;
  is_active: boolean;
}

/** Skill import result / 导入技能结果 */
export interface SkillImportResult {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

/** Batch export skills / 批量导出技能 */
export async function exportSkillsApi(
  skillIds: number[],
  options?: ApiRequestOptions,
): Promise<SkillExportItem[]> {
  return requestClient.post<SkillExportItem[]>(
    `${PREFIX}/export`,
    { skill_ids: skillIds },
    options,
  );
}

/** Batch import skills / 批量导入技能 */
export async function importSkillsApi(
  items: SkillExportItem[],
  tenantId?: null | number,
  conflictMode: string = 'skip',
  packageId?: null | number,
  options?: ApiRequestOptions,
): Promise<SkillImportResult> {
  return requestClient.post<SkillImportResult>(
    `${PREFIX}/import`,
    {
      items,
      tenant_id: tenantId,
      conflict_mode: conflictMode,
      package_id: packageId,
    },
    options,
  );
}

/** Get all skill statistics overview / 获取全部技能统计概览 */
export async function getSkillsStatsOverviewApi(
  options?: ApiRequestOptions,
): Promise<AdminSkillStatsOverviewItem[]> {
  return requestClient.get<AdminSkillStatsOverviewItem[]>(
    `${PREFIX}/stats/overview`,
    options,
  );
}

// ============================================================
// Toolkit parsing API / Toolkit 解析 API
// ============================================================

/** Tool in toolkit parse result / Toolkit 解析结果中的 Tool */
export interface ToolkitToolInfo {
  name: string;
  description: string;
  parameters: Array<{
    default?: unknown;
    description: string;
    name: string;
    required: boolean;
    type: string;
  }>;
  is_async: boolean;
}

/** Toolkit parse response / Toolkit 解析响应 */
export interface ToolkitParseResult {
  title?: string;
  description?: string;
  version?: string;
  author?: string;
  requirements?: string[];
  tools: ToolkitToolInfo[];
  valves_schema: Record<string, unknown>;
  errors: string[];
}

/** Parse toolkit source code / 解析 Toolkit 源码 */
export async function parseToolkitApi(
  source: string,
  options?: ApiRequestOptions,
): Promise<ToolkitParseResult> {
  return requestClient.post<ToolkitParseResult>(
    `${PREFIX}/toolkit/parse`,
    { source },
    options,
  );
}
