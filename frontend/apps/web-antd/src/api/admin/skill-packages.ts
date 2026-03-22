/**
 * Platform skill package management API / 平台端技能包管理 API
 */
import type { AdminSkillInfo } from '#/api/admin/skills';

import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/ai/skill-packages';

export interface SkillPackageSummaryInfo {
  package_role_key: string;
  source_summary: string;
  runtime_binding_mode: string;
  valves_field_count: number;
  configured_valves_count: number;
}

/** Skill package info / 技能包信息 */
export interface AdminSkillPackageInfo extends SkillPackageSummaryInfo {
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

/** Create skill package request / 创建技能包请求 */
export interface SkillPackageCreateParams {
  name: string;
  description?: null | string;
  avatar?: null | string;
  is_recommended?: boolean;
  is_active?: boolean;
  sort_order?: number;
}

/** Update skill package request / 更新技能包请求 */
export interface SkillPackageUpdateParams {
  name?: string;
  description?: null | string;
  avatar?: null | string;
  is_recommended?: boolean;
  is_active?: boolean;
  sort_order?: number;
}

/** Select API wraps options in `items` (SelectResponse) / 下拉接口使用 SelectResponse.items */
export interface AdminSkillPackageSelectOption {
  disabled?: boolean;
  extra?: null | Record<string, unknown>;
  label: string;
  value: number | string;
}

export interface AdminSkillPackageSelectResponse {
  has_more?: boolean;
  items: AdminSkillPackageSelectOption[];
  page?: number;
  page_size?: number;
  total?: number;
}

/** Get skill package select options / 获取技能包下拉选项 */
export function getSkillPackageSelectApi(params?: Record<string, unknown>) {
  return requestClient.get<AdminSkillPackageSelectResponse>(`${BASE_URL}/select`, {
    params,
  });
}

/** Get skill package list / 获取技能包列表 */
export function getSkillPackageListApi(params?: Record<string, unknown>) {
  return requestClient.get<{ items: AdminSkillPackageInfo[]; total: number }>(
    BASE_URL,
    { params },
  );
}

/** Get skill package detail / 获取技能包详情 */
export function getSkillPackageDetailApi(id: number) {
  return requestClient.get<AdminSkillPackageInfo>(`${BASE_URL}/${id}`);
}

/** Create skill package / 创建技能包 */
export function createSkillPackageApi(data: SkillPackageCreateParams) {
  return requestClient.post<AdminSkillPackageInfo>(BASE_URL, data);
}

/** Update skill package / 更新技能包 */
export function updateSkillPackageApi(
  id: number,
  data: SkillPackageUpdateParams,
) {
  return requestClient.put<AdminSkillPackageInfo>(`${BASE_URL}/${id}`, data);
}

/** Delete skill package / 删除技能包 */
export function deleteSkillPackageApi(id: number) {
  return requestClient.delete(`${BASE_URL}/${id}`);
}

/** Get recommended skill packages / 获取推荐技能包列表 */
export function getRecommendedSkillPackagesApi() {
  return requestClient.get<AdminSkillPackageInfo[]>(`${BASE_URL}/recommended`);
}

/** Toggle skill package status / 切换技能包状态 */
export function toggleSkillPackageStatusApi(id: number) {
  return requestClient.put<AdminSkillPackageInfo>(`${BASE_URL}/${id}/status`);
}

/** Upload skill ZIP package / 上传技能 ZIP 包 */
export function uploadSkillPackageApi(file: File, isSystem = false) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post<AdminSkillPackageInfo>(
    `${BASE_URL}/upload?is_system=${isSystem}`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
}

/** Get recycle bin count / 获取回收站数量 */
export function getSkillPackageRecycleBinCountApi() {
  return requestClient.get<{ count: number }>(`${BASE_URL}/recycle-bin/count`);
}

/** Get recycle bin list / 获取回收站列表 */
export function getSkillPackageRecycleBinApi(params?: Record<string, unknown>) {
  return requestClient.get<{ items: AdminSkillPackageInfo[]; total: number }>(
    `${BASE_URL}/recycle-bin`,
    { params },
  );
}

/** Restore skill package / 恢复技能包 */
export function restoreSkillPackageApi(id: number) {
  return requestClient.post(`${BASE_URL}/recycle-bin/${id}/restore`);
}

/** Permanently delete skill package / 永久删除技能包 */
export function permanentDeleteSkillPackageApi(id: number) {
  return requestClient.delete(`${BASE_URL}/recycle-bin/${id}`);
}

/** Valves property definition / Valves 属性定义 */
interface ValvesProperty {
  type: string;
  description?: string;
  default?: unknown;
}

/** Valves config response / Valves 配置响应 */
export interface SkillPackageValvesInfo {
  valves_schema: null | {
    properties: Record<string, ValvesProperty>;
    required?: string[];
    type: string;
  };
  valves_config: null | Record<string, unknown>;
}

/** Get skill package Valves config / 获取技能包 Valves 配置 */
export function getSkillPackageValvesApi(packageId: number) {
  return requestClient.get<SkillPackageValvesInfo>(
    `${BASE_URL}/${packageId}/valves`,
  );
}

/** Update skill package Valves config / 更新技能包 Valves 配置 */
export function updateSkillPackageValvesApi(
  packageId: number,
  data: { valves_config: Record<string, unknown> },
) {
  return requestClient.put<SkillPackageValvesInfo>(
    `${BASE_URL}/${packageId}/valves`,
    data,
  );
}

/** Get skills in skill package / 获取技能包内的技能列表 */
export function getSkillPackageSkillsApi(
  packageId: number,
  params?: Record<string, unknown>,
) {
  return requestClient.get<{ items: AdminSkillInfo[]; total: number }>(
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

/** Get resolved tools in skill package / 获取技能包解析出的工具列表 */
export function getSkillPackageResolvedToolsApi(packageId: number) {
  return requestClient.get<SkillPackageResolvedToolsInfo>(
    `${BASE_URL}/${packageId}/resolved-tools`,
  );
}

/** Clone skill package / 克隆技能包 */
export function cloneSkillPackageApi(
  packageId: number,
  data?: {
    new_name?: string;
    target_tenant_id?: null | number;
  },
) {
  return requestClient.post<{
    package_id: number;
    package_name: string;
    skills_created: number;
    status: string;
  }>(`${BASE_URL}/${packageId}/clone`, data ?? {});
}

/** Export skill package JSON / 导出技能包 JSON */
export function exportSkillPackageApi(packageId: number) {
  return requestClient.get<Record<string, unknown>>(
    `${BASE_URL}/${packageId}/export`,
  );
}

/** Import skill package JSON / 导入技能包 JSON */
export function importSkillPackageApi(data: {
  conflict_mode?: 'rename' | 'skip';
  export_data: Record<string, unknown>;
  target_tenant_id?: null | number;
}) {
  return requestClient.post<{
    package_id: number;
    package_name: string;
    skills_created: number;
    status: string;
  }>(`${BASE_URL}/import`, data);
}
