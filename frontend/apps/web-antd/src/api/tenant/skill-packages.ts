/**
 * Tenant skill package catalog API / 企业端技能包目录 API
 */
import type { SkillInfo } from '#/api/tenant/skills';

import { requestClient } from '#/utils/request';

const BASE_URL = '/tenant/ai/skill-packages';

export interface SkillPackageSummaryInfo {
  package_role_key: string;
  source_summary: string;
  runtime_binding_mode: string;
  valves_field_count: number;
  configured_valves_count: number;
}

/** Skill package info / 技能包信息 */
export interface TenantSkillPackageInfo extends SkillPackageSummaryInfo {
  id: number;
  tenant_id: null | number;
  name: string;
  description: null | string;
  avatar: null | string;
  is_recommended: boolean;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  skill_count: number;
  source_plugin: null | string;
  valves_schema: null | Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Get package catalog list / 获取技能包目录列表 */
export function getSkillPackageListApi(params?: Record<string, unknown>) {
  return requestClient.get<{ items: TenantSkillPackageInfo[]; total: number }>(
    BASE_URL,
    { params },
  );
}

/** Get package catalog detail / 获取技能包目录详情 */
export function getSkillPackageDetailApi(id: number) {
  return requestClient.get<TenantSkillPackageInfo>(`${BASE_URL}/${id}`);
}

/** Get skills within skill package / 获取技能包内的技能列表 */
export function getSkillPackageSkillsApi(
  packageId: number,
  params?: Record<string, unknown>,
) {
  return requestClient.get<{ items: SkillInfo[]; total: number }>(
    `${BASE_URL}/${packageId}/skills`,
    { params },
  );
}

export interface ResolvedToolParameter {
  description: string;
  name: string;
  required: boolean;
  type: string;
}

export interface SkillPackageResolvedToolInfo {
  description: string;
  name: string;
  parameters: ResolvedToolParameter[];
  source_plugin?: null | string;
  source_skill_id: number;
  source_skill_name: string;
  tool_type?: string;
}

export interface SkillPackageResolvedToolsInfo {
  package_id: number;
  package_name: string;
  source_plugin: null | string;
  tool_count: number;
  tools: SkillPackageResolvedToolInfo[];
}

/** Get resolved tools within skill package / 获取技能包解析后的工具列表 */
export function getSkillPackageResolvedToolsApi(packageId: number) {
  return requestClient.get<SkillPackageResolvedToolsInfo>(
    `${BASE_URL}/${packageId}/resolved-tools`,
  );
}
