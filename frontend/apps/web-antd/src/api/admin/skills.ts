/**
 * 管理端技能管理 API
 * 对接后端 /admin/ai/skills/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 技能信息（管理端含 tenant_id） */
export interface AdminSkillInfo {
  id: number;
  tenant_id: number | null;
  package_id: number;
  name: string;
  description: string | null;
  avatar: string | null;
  type: string;
  config: Record<string, unknown> | null;
  input_schema: Record<string, unknown> | null;
  output_schema: Record<string, unknown> | null;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  timeout: number;
  toolkit_content: string | null;
  toolkit_meta: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** 创建技能请求 */
export interface AdminSkillCreateRequest {
  package_id: number;
  name: string;
  description?: string | null;
  avatar?: string | null;
  type?: string;
  config?: Record<string, unknown> | null;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
  is_active?: boolean;
  sort_order?: number;
  timeout?: number;
  toolkit_content?: string | null;
}

/** 更新技能请求 */
export interface AdminSkillUpdateRequest {
  name?: string | null;
  description?: string | null;
  avatar?: string | null;
  type?: string | null;
  config?: Record<string, unknown> | null;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
  is_active?: boolean | null;
  sort_order?: number | null;
  timeout?: number | null;
  toolkit_content?: string | null;
}

/** 技能类型选项 */
export interface SkillTypeOption {
  value: string;
  label: string;
}

/** 技能列表分页响应 */
interface AdminSkillPageResponse {
  items: AdminSkillInfo[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/admin/ai/skills';

/** 获取可用技能类型列表 */
export async function getSkillTypesApi(
  options?: ApiRequestOptions,
): Promise<SkillTypeOption[]> {
  return requestClient.get<SkillTypeOption[]>(
    `${PREFIX}/skill-types`,
    options,
  );
}

/** 获取技能列表（全租户） */
export async function getSkillListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<AdminSkillPageResponse> {
  return requestClient.get<AdminSkillPageResponse>(
    PREFIX,
    { params, ...options },
  );
}

/** 获取技能详情 */
export async function getSkillDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AdminSkillInfo> {
  return requestClient.get<AdminSkillInfo>(
    `${PREFIX}/${id}`,
    options,
  );
}

/** 创建技能 */
export async function createSkillApi(
  data: AdminSkillCreateRequest,
  options?: ApiRequestOptions,
): Promise<AdminSkillInfo> {
  return requestClient.post<AdminSkillInfo>(
    PREFIX,
    data,
    options,
  );
}

/** 更新技能 */
export async function updateSkillApi(
  id: number,
  data: AdminSkillUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AdminSkillInfo> {
  return requestClient.put<AdminSkillInfo>(
    `${PREFIX}/${id}`,
    data,
    options,
  );
}

/** 删除技能 */
export async function deleteSkillApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** 技能测试结果 */
export interface AdminSkillTestResult {
  success: boolean;
  message: string;
  details: Record<string, unknown> | null;
}

/** 插件技能工具定义 */
export interface PluginToolDefinition {
  name: string;
  description: string;
  parameters: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
    default?: unknown;
  }>;
  timeout?: number;
}

/** 获取技能工具定义列表（插件技能） */
export async function getSkillToolsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<PluginToolDefinition[]> {
  return requestClient.get<PluginToolDefinition[]>(
    `${PREFIX}/${id}/tools`,
    options,
  );
}

/** 测试技能配置 */
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

/** 切换技能状态 */
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

/** 技能调用统计 */
export interface AdminSkillStats {
  skill_id: number;
  total_calls: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  avg_duration_ms: number;
  last_called_at: string | null;
}

/** 技能调用统计概览项 */
export interface AdminSkillStatsOverviewItem {
  skill_id: number;
  skill_name: string;
  skill_type: string;
  total_calls: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  avg_duration_ms: number;
  last_called_at: string | null;
}

/** 获取技能调用统计 */
export async function getSkillStatsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AdminSkillStats> {
  return requestClient.get<AdminSkillStats>(
    `${PREFIX}/${id}/stats`,
    options,
  );
}

/** 导出技能结果项 */
export interface SkillExportItem {
  name: string;
  description: string | null;
  avatar: string | null;
  type: string;
  config: Record<string, unknown> | null;
  input_schema: Record<string, unknown> | null;
  output_schema: Record<string, unknown> | null;
  timeout: number;
  is_active: boolean;
}

/** 导入技能结果 */
export interface SkillImportResult {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

/** 批量导出技能 */
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

/** 批量导入技能 */
export async function importSkillsApi(
  items: SkillExportItem[],
  tenantId?: number | null,
  conflictMode: string = 'skip',
  packageId?: number | null,
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

/** 获取全部技能统计概览 */
export async function getSkillsStatsOverviewApi(
  options?: ApiRequestOptions,
): Promise<AdminSkillStatsOverviewItem[]> {
  return requestClient.get<AdminSkillStatsOverviewItem[]>(
    `${PREFIX}/stats/overview`,
    options,
  );
}

// ============================================================
// Toolkit 解析 API
// ============================================================

/** Toolkit 解析结果中的 Tool */
export interface ToolkitToolInfo {
  name: string;
  description: string;
  parameters: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
    default?: unknown;
  }>;
  is_async: boolean;
}

/** Toolkit 解析响应 */
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

/** 解析 Toolkit 源码 */
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
