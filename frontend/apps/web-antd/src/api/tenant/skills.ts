/**
 * Tenant skill management API / 企业端技能管理 API
 * Backend: /tenant/ai/skills/* / 对接后端 /tenant/ai/skills/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Skill info / 技能信息 */
/** Plugin skill tool definition / 插件技能工具定义 */
export interface PluginToolDefinition {
  name: string;
  description: string;
  parameters: Array<{
    description: string;
    name: string;
    required: boolean;
    type: string;
  }>;
}

/** Skill info / 技能信息 */
export interface SkillInfo {
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
export interface SkillCreateRequest {
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
export interface SkillUpdateRequest {
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
interface SkillPageResponse {
  items: SkillInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** Skill select option / 技能下拉选项 */
export interface SkillSelectOption {
  id: number;
  name: string;
  type: string;
  description: null | string;
}

// ============================================================
// API functions / API 接口
// ============================================================

const PREFIX = '/tenant/ai/skills';

/** Get available skill types / 获取可用技能类型列表 */
export async function getSkillTypesApi(
  options?: ApiRequestOptions,
): Promise<SkillTypeOption[]> {
  return requestClient.get<SkillTypeOption[]>(`${PREFIX}/skill-types`, options);
}

/** Get skill list / 获取技能列表 */
export async function getSkillListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SkillPageResponse> {
  return requestClient.get<SkillPageResponse>(PREFIX, { params, ...options });
}

/** Get skill select options / 获取技能下拉选项 */
export async function getSkillSelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SkillSelectOption[]> {
  return requestClient.get<SkillSelectOption[]>(`${PREFIX}/select`, {
    params,
    ...options,
  });
}

/** Get skill detail / 获取技能详情 */
export async function getSkillDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.get<SkillInfo>(`${PREFIX}/${id}`, options);
}

/** Create skill / 创建技能 */
export async function createSkillApi(
  data: SkillCreateRequest,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.post<SkillInfo>(PREFIX, data, options);
}

/** Update skill / 更新技能 */
export async function updateSkillApi(
  id: number,
  data: SkillUpdateRequest,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.put<SkillInfo>(`${PREFIX}/${id}`, data, options);
}

/** Delete skill / 删除技能 */
export async function deleteSkillApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${PREFIX}/${id}`, options);
}

/** Skill test result / 技能测试结果 */
export interface SkillTestResult {
  success: boolean;
  message: string;
  details: null | Record<string, unknown>;
}

/** Test skill configuration / 测试技能配置 */
export async function testSkillApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<SkillTestResult> {
  return requestClient.post<SkillTestResult>(
    `${PREFIX}/${id}/test`,
    {},
    options,
  );
}

/** Skill invocation statistics / 技能调用统计 */
export interface SkillStats {
  skill_id: number;
  total_calls: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  avg_duration_ms: number;
  last_called_at: null | string;
}

/** Get skill invocation statistics / 获取技能调用统计 */
export async function getSkillStatsApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<SkillStats> {
  return requestClient.get<SkillStats>(`${PREFIX}/${id}/stats`, options);
}

// ============================================================
// Toolkit parsing API / Toolkit 解析 API
// ============================================================

/** Tool from Toolkit parse result / Toolkit 解析结果中的 Tool */
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

/** Parse Toolkit source code / 解析 Toolkit 源码 */
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
