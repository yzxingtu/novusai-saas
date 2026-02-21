/**
 * 租户端技能包管理 API
 */
import type { SkillInfo } from '#/api/tenant/skills';

import { requestClient } from '#/utils/request';

const BASE_URL = '/tenant/ai/skill-packages';

/** 技能包信息 */
export interface TenantSkillPackageInfo {
  id: number;
  tenant_id: number;
  name: string;
  description: string | null;
  avatar: string | null;
  scope: string;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  skill_count: number;
  source_plugin: string | null;
  valves_schema: Record<string, unknown> | null;
  valves_config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** 创建技能包请求 */
export interface SkillPackageCreateParams {
  name: string;
  description?: string | null;
  avatar?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

/** 更新技能包请求 */
export interface SkillPackageUpdateParams {
  name?: string;
  description?: string | null;
  avatar?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

/** 获取技能包列表 */
export function getSkillPackageListApi(params?: Record<string, unknown>) {
  return requestClient.get<{ items: TenantSkillPackageInfo[]; total: number }>(
    BASE_URL,
    { params },
  );
}

/** 获取技能包详情 */
export function getSkillPackageDetailApi(id: number) {
  return requestClient.get<TenantSkillPackageInfo>(`${BASE_URL}/${id}`);
}

/** 创建技能包 */
export function createSkillPackageApi(data: SkillPackageCreateParams) {
  return requestClient.post<TenantSkillPackageInfo>(BASE_URL, data);
}

/** 更新技能包 */
export function updateSkillPackageApi(
  id: number,
  data: SkillPackageUpdateParams,
) {
  return requestClient.put<TenantSkillPackageInfo>(`${BASE_URL}/${id}`, data);
}

/** 删除技能包 */
export function deleteSkillPackageApi(id: number) {
  return requestClient.delete(`${BASE_URL}/${id}`);
}

/** 获取技能包下拉选项 */
export function getSkillPackageSelectApi(params?: Record<string, unknown>) {
  return requestClient.get<Array<{ label: string; value: number }>>(
    `${BASE_URL}/select`,
    { params },
  );
}

/** 可绑定技能包选项（含 admin 共享包） */
export interface AvailablePackageOption {
  label: string;
  value: number;
  scope: string;
  description: string | null;
  is_system: boolean;
}

/** 获取可绑定的技能包列表（自有 + admin 共享） */
export function getAvailablePackagesApi() {
  return requestClient.get<AvailablePackageOption[]>(
    `${BASE_URL}/available`,
  );
}

/** 上传技能 ZIP 包 */
export function uploadSkillPackageApi(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post<TenantSkillPackageInfo>(
    `${BASE_URL}/upload`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
}

/** Valves 属性定义 */
interface ValvesProperty {
  type: string;
  description?: string;
  default?: unknown;
}

/** Valves 配置响应 */
export interface SkillPackageValvesInfo {
  valves_schema: {
    type: string;
    properties: Record<string, ValvesProperty>;
    required?: string[];
  } | null;
  valves_config: Record<string, unknown> | null;
}

/** 获取技能包 Valves 配置 */
export function getSkillPackageValvesApi(packageId: number) {
  return requestClient.get<SkillPackageValvesInfo>(
    `${BASE_URL}/${packageId}/valves`,
  );
}

/** 更新技能包 Valves 配置 */
export function updateSkillPackageValvesApi(
  packageId: number,
  data: { valves_config: Record<string, unknown> },
) {
  return requestClient.put<SkillPackageValvesInfo>(
    `${BASE_URL}/${packageId}/valves`,
    data,
  );
}

/** 获取技能包内的技能列表 */
export function getSkillPackageSkillsApi(
  packageId: number,
  params?: Record<string, unknown>,
) {
  return requestClient.get<{ items: SkillInfo[]; total: number }>(
    `${BASE_URL}/${packageId}/skills`,
    { params },
  );
}
