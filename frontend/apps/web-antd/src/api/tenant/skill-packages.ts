/**
 * Tenant skill package management API / 企业端技能包管理 API
 */
import type { SkillInfo } from '#/api/tenant/skills';

import { requestClient } from '#/utils/request';

const BASE_URL = '/tenant/ai/skill-packages';

/** Skill package info / 技能包信息 */
export interface TenantSkillPackageInfo {
  id: number;
  tenant_id: number;
  name: string;
  description: null | string;
  avatar: null | string;
  target_audience: string;
  is_recommended: boolean;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  skill_count: number;
  source_plugin: null | string;
  valves_schema: null | Record<string, unknown>;
  valves_config: null | Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Create skill package request / 创建技能包请求 */
export interface SkillPackageCreateParams {
  name: string;
  description?: null | string;
  avatar?: null | string;
  is_active?: boolean;
  sort_order?: number;
}

/** Update skill package request / 更新技能包请求 */
export interface SkillPackageUpdateParams {
  name?: string;
  description?: null | string;
  avatar?: null | string;
  is_active?: boolean;
  sort_order?: number;
}

/** Recommended skill package info / 推荐技能包信息 */
export interface RecommendedSkillPackageInfo {
  id: number;
  name: string;
  description: null | string;
  avatar: null | string;
  target_audience: string;
  is_recommended: boolean;
  is_system: boolean;
  skill_count: number;
  source_plugin: null | string;
}

/** Get recommended skill package list / 获取推荐技能包列表 */
export function getRecommendedSkillPackagesApi() {
  return requestClient.get<RecommendedSkillPackageInfo[]>(
    `${BASE_URL}/recommended`,
  );
}

/** Get skill package list / 获取技能包列表 */
export function getSkillPackageListApi(params?: Record<string, unknown>) {
  return requestClient.get<{ items: TenantSkillPackageInfo[]; total: number }>(
    BASE_URL,
    { params },
  );
}

/** Get skill package detail / 获取技能包详情 */
export function getSkillPackageDetailApi(id: number) {
  return requestClient.get<TenantSkillPackageInfo>(`${BASE_URL}/${id}`);
}

/** Create skill package / 创建技能包 */
export function createSkillPackageApi(data: SkillPackageCreateParams) {
  return requestClient.post<TenantSkillPackageInfo>(BASE_URL, data);
}

/** Update skill package / 更新技能包 */
export function updateSkillPackageApi(
  id: number,
  data: SkillPackageUpdateParams,
) {
  return requestClient.put<TenantSkillPackageInfo>(`${BASE_URL}/${id}`, data);
}

/** Delete skill package / 删除技能包 */
export function deleteSkillPackageApi(id: number) {
  return requestClient.delete(`${BASE_URL}/${id}`);
}

/** Get skill package select options / 获取技能包下拉选项 */
export function getSkillPackageSelectApi(params?: Record<string, unknown>) {
  return requestClient.get<Array<{ label: string; value: number }>>(
    `${BASE_URL}/select`,
    { params },
  );
}

/** Available package option (including admin shared packages) / 可绑定技能包选项 */
export interface AvailablePackageOption {
  label: string;
  value: number;
  description: null | string;
  is_system: boolean;
}

/** Get available package list (own + admin shared) / 获取可绑定的技能包列表 */
export function getAvailablePackagesApi() {
  return requestClient.get<AvailablePackageOption[]>(`${BASE_URL}/available`);
}

/** Upload skill ZIP package / 上传技能 ZIP 包 */
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

/** Get recycle bin count / 获取回收站数量 */
export function getSkillPackageRecycleBinCountApi() {
  return requestClient.get<{ count: number }>(`${BASE_URL}/recycle-bin/count`);
}

/** Get recycle bin list / 获取回收站列表 */
export function getSkillPackageRecycleBinApi(params?: Record<string, unknown>) {
  return requestClient.get<{ items: TenantSkillPackageInfo[]; total: number }>(
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

/** Clone skill package from template / 从模板克隆技能包 */
export function cloneFromTemplateApi(
  packageId: number,
  data?: { new_name?: string },
) {
  return requestClient.post<{
    package_id: number;
    package_name: string;
    skills_created: number;
    status: string;
  }>(`${BASE_URL}/from-template/${packageId}`, data ?? {});
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
