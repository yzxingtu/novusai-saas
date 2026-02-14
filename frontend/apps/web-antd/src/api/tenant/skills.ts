/**
 * 租户端技能管理 API
 * 对接后端 /tenant/ai/skills/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 技能信息 */
export interface SkillInfo {
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
export interface SkillCreateRequest {
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
export interface SkillUpdateRequest {
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
interface SkillPageResponse {
  items: SkillInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** 技能下拉选项 */
export interface SkillSelectOption {
  id: number;
  name: string;
  type: string;
  description: string | null;
}

// ============================================================
// API 接口
// ============================================================

const PREFIX = '/tenant/ai/skills';

/** 获取可用技能类型列表 */
export async function getSkillTypesApi(
  options?: ApiRequestOptions,
): Promise<SkillTypeOption[]> {
  return requestClient.get<SkillTypeOption[]>(
    `${PREFIX}/skill-types`,
    options,
  );
}

/** 获取技能列表 */
export async function getSkillListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SkillPageResponse> {
  return requestClient.get<SkillPageResponse>(
    PREFIX,
    { params, ...options },
  );
}

/** 获取技能下拉选项 */
export async function getSkillSelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SkillSelectOption[]> {
  return requestClient.get<SkillSelectOption[]>(
    `${PREFIX}/select`,
    { params, ...options },
  );
}

/** 获取技能详情 */
export async function getSkillDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.get<SkillInfo>(
    `${PREFIX}/${id}`,
    options,
  );
}

/** 创建技能 */
export async function createSkillApi(
  data: SkillCreateRequest,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.post<SkillInfo>(
    PREFIX,
    data,
    options,
  );
}

/** 更新技能 */
export async function updateSkillApi(
  id: number,
  data: SkillUpdateRequest,
  options?: ApiRequestOptions,
): Promise<SkillInfo> {
  return requestClient.put<SkillInfo>(
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
export interface SkillTestResult {
  success: boolean;
  message: string;
  details: Record<string, unknown> | null;
}

/** 测试技能配置 */
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

/** 技能调用统计 */
export interface SkillStats {
  skill_id: number;
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
): Promise<SkillStats> {
  return requestClient.get<SkillStats>(
    `${PREFIX}/${id}/stats`,
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
