/**
 * Plan management API / 套餐管理 API
 * Backend: /admin/plans/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Billing cycle / 计费周期 */
export type BillingCycle =
  | 'custom'
  | 'lifetime'
  | 'monthly'
  | 'one_time'
  | 'quarterly'
  | 'yearly';

/** Quota config / 配额配置 */
export interface QuotaSchema {
  /** Allow custom domain / 是否允许自定义域名 */
  allowCustomDomain?: boolean | null;
  /** Monthly API call count / 每月 API 调用次数 */
  apiCallsPerMonth?: null | number;
  /** Max admins / 最大管理员数 */
  maxAdmins?: null | number;
  /** Max custom domains / 最大自定义域名数 */
  maxCustomDomains?: null | number;
  /** Max file size (MB) / 最大文件大小 */
  maxFileSizeMb?: null | number;
  /** Max users / 最大用户数 */
  maxUsers?: null | number;
  /** Storage limit (GB) / 存储限制 */
  storageLimitGb?: null | number;
}

/** Backend quota format (snake_case) / 后端配额格式 */
interface QuotaSchemaRaw {
  allow_custom_domain?: boolean | null;
  api_calls_per_month?: null | number;
  max_admins?: null | number;
  max_custom_domains?: null | number;
  max_file_size_mb?: null | number;
  max_users?: null | number;
  storage_limit_gb?: null | number;
}

/** Feature flags / 特性标记 */
export interface FeaturesSchema {
  /** Advanced analytics / 高级分析 */
  advancedAnalytics?: boolean | null;
  /** AI enabled / AI 功能 */
  aiEnabled?: boolean | null;
  /** Priority support / 优先支持 */
  prioritySupport?: boolean | null;
  /** Storage billing enabled / 对象存储账单对账收费 */
  storageBillingEnabled?: boolean | null;
  /** White label / 白标支持 */
  whiteLabel?: boolean | null;
}

/** Backend feature format (snake_case) / 后端特性格式 */
interface FeaturesSchemaRaw {
  advanced_analytics?: boolean | null;
  ai_enabled?: boolean | null;
  priority_support?: boolean | null;
  storage_billing_enabled?: boolean | null;
  white_label?: boolean | null;
}

/** Plan info (backend raw snake_case) / 套餐信息（后端原始） */
export interface TenantPlanInfoRaw {
  billing_cycle: BillingCycle;
  code: string;
  created_at: string;
  description?: null | string;
  features?: FeaturesSchemaRaw | null;
  id: number;
  is_active: boolean;
  name: string;
  price?: null | number | string;
  quota?: null | QuotaSchemaRaw;
  sort_order: number;
  updated_at?: string;
}

/** Plan info (frontend camelCase) / 套餐信息（前端） */
export interface TenantPlanInfo {
  billingCycle: BillingCycle;
  code: string;
  createdAt: string;
  description?: null | string;
  features?: FeaturesSchema | null;
  id: number;
  isActive: boolean;
  name: string;
  price?: null | number | string;
  quota?: null | QuotaSchema;
  sortOrder: number;
  updatedAt?: string;
}

/** Create plan request / 创建套餐请求 */
export interface TenantPlanCreateRequest {
  billing_cycle?: BillingCycle;
  code: string;
  description?: null | string;
  features?: FeaturesSchemaRaw | null;
  is_active?: boolean;
  name: string;
  price?: null | number | string;
  quota?: null | QuotaSchemaRaw;
  sort_order?: number;
}

/** Update plan request / 更新套餐请求 */
export interface TenantPlanUpdateRequest {
  billing_cycle?: BillingCycle | null;
  description?: null | string;
  features?: FeaturesSchemaRaw | null;
  is_active?: boolean | null;
  name?: null | string;
  price?: null | number | string;
  quota?: null | QuotaSchemaRaw;
  sort_order?: null | number;
}

/** Toggle status request / 切换状态请求 */
export interface TenantPlanStatusRequest {
  is_active: boolean;
}

/** Set permissions request / 设置权限请求 */
export interface TenantPlanPermissionsRequest {
  permission_ids: number[];
}

/** Permission info (tree structure) / 权限信息（树形） */
export interface PermissionInfo {
  children?: PermissionInfo[];
  code: string;
  id: number;
  name: string;
  parentId?: null | number;
}

/** Permission simple info (plan assigned permissions) / 权限简要信息 */
export interface PermissionSimpleInfo {
  code: string;
  id: number;
  name: string;
  resource: string;
  type: string;
}

/** Backend permission format / 后端权限格式 */
interface PermissionInfoRaw {
  children?: PermissionInfoRaw[];
  code: string;
  id: number;
  name: string;
  parent_id?: null | number;
}

/** Plan list query params / 套餐列表查询参数 */
export type TenantPlanListParams = Record<string, unknown>;

/** Paginated list response / 分页列表响应 */
export interface TenantPlanListResponse {
  items: TenantPlanInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** Dropdown option (follows generic remote select pattern) / 下拉选项 */
export interface TenantPlanSelectOption {
  label: string;
  value: number;
  extra?: null | {
    billing_cycle?: string;
    code?: string;
  };
  disabled?: boolean;
  children?: null;
  is_leaf?: boolean | null;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Transform quota snake_case -> camelCase / 转换配额 */
function transformQuota(raw?: null | QuotaSchemaRaw): null | QuotaSchema {
  if (!raw) return null;
  return {
    allowCustomDomain: raw.allow_custom_domain,
    apiCallsPerMonth: raw.api_calls_per_month,
    maxAdmins: raw.max_admins,
    maxCustomDomains: raw.max_custom_domains,
    maxFileSizeMb: raw.max_file_size_mb,
    maxUsers: raw.max_users,
    storageLimitGb: raw.storage_limit_gb,
  };
}

/** Transform features snake_case -> camelCase / 转换特性 */
function transformFeatures(
  raw?: FeaturesSchemaRaw | null,
): FeaturesSchema | null {
  if (!raw) return null;
  return {
    advancedAnalytics: raw.advanced_analytics,
    aiEnabled: raw.ai_enabled,
    prioritySupport: raw.priority_support,
    storageBillingEnabled: raw.storage_billing_enabled,
    whiteLabel: raw.white_label,
  };
}

/** Convert backend snake_case to frontend camelCase / 将后端转换为前端格式 */
function transformTenantPlanInfo(raw: TenantPlanInfoRaw): TenantPlanInfo {
  return {
    billingCycle: raw.billing_cycle,
    code: raw.code,
    createdAt: raw.created_at,
    description: raw.description,
    features: transformFeatures(raw.features),
    id: raw.id,
    isActive: raw.is_active,
    name: raw.name,
    price: raw.price,
    quota: transformQuota(raw.quota),
    sortOrder: raw.sort_order,
    updatedAt: raw.updated_at,
  };
}

/** Transform permission tree / 转换权限树 */
function transformPermission(raw: PermissionInfoRaw): PermissionInfo {
  return {
    children: raw.children?.map((child) => transformPermission(child)),
    code: raw.code,
    id: raw.id,
    name: raw.name,
    parentId: raw.parent_id,
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/admin/plans';

/**
 * Get plan list / 获取套餐列表
 * GET /admin/plans
 */
export async function getTenantPlanListApi(
  params?: TenantPlanListParams,
  options?: ApiRequestOptions,
): Promise<TenantPlanListResponse> {
  const response = await requestClient.get<{
    items: TenantPlanInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformTenantPlanInfo(item)),
    page: response.page,
    page_size: response.page_size,
    total: response.total,
  };
}

/**
 * Get plan detail / 获取套餐详情
 * GET /admin/plans/{plan_id}
 */
export async function getTenantPlanDetailApi(
  planId: number,
  options?: ApiRequestOptions,
): Promise<TenantPlanInfo> {
  const raw = await requestClient.get<TenantPlanInfoRaw>(
    `${API_PREFIX}/${planId}`,
    options,
  );
  return transformTenantPlanInfo(raw);
}

/**
 * Create plan / 创建套餐
 * POST /admin/plans
 */
export async function createTenantPlanApi(
  data: TenantPlanCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantPlanInfo> {
  const raw = await requestClient.post<TenantPlanInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformTenantPlanInfo(raw);
}

/**
 * Update plan / 更新套餐
 * PUT /admin/plans/{plan_id}
 */
export async function updateTenantPlanApi(
  planId: number,
  data: TenantPlanUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantPlanInfo> {
  const raw = await requestClient.put<TenantPlanInfoRaw>(
    `${API_PREFIX}/${planId}`,
    data,
    options,
  );
  return transformTenantPlanInfo(raw);
}

/**
 * Delete plan / 删除套餐
 * DELETE /admin/plans/{plan_id}
 */
export async function deleteTenantPlanApi(
  planId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${planId}`, options);
}

/**
 * Reorder plans / 重新排序套餐
 * PUT /admin/plans/reorder
 */
export async function reorderTenantPlansApi(
  ids: number[],
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(`${API_PREFIX}/reorder`, { ids }, options);
}

/**
 * Toggle plan status / 切换套餐状态
 * PUT /admin/plans/{plan_id}/status
 */
export async function toggleTenantPlanStatusApi(
  planId: number,
  data: TenantPlanStatusRequest,
  options?: ApiRequestOptions,
): Promise<TenantPlanInfo> {
  // Use update API to toggle status / 使用 update 接口切换状态
  const raw = await requestClient.put<TenantPlanInfoRaw>(
    `${API_PREFIX}/${planId}`,
    data,
    options,
  );
  return transformTenantPlanInfo(raw);
}

/** Plan select option response / 套餐下拉选项响应 */
export interface TenantPlanSelectResponse {
  items: TenantPlanSelectOption[];
  total?: number;
  page?: number;
  page_size?: number;
  has_more?: boolean;
}

/**
 * Get plan select options / 获取套餐下拉选项
 * GET /admin/plans/select
 *
 * Response follows generic remote select pattern: { data: { items: [{label, value, extra}] } }
 */
export async function getTenantPlanSelectApi(params?: {
  is_active?: string;
  page?: number;
  page_size?: number;
  search?: string;
}): Promise<TenantPlanSelectResponse> {
  return requestClient.get<TenantPlanSelectResponse>(`${API_PREFIX}/select`, {
    params,
  });
}

/**
 * Get available permissions / 获取可分配的权限列表
 * GET /admin/plans/available-permissions
 */
export async function getAvailablePermissionsApi(
  options?: ApiRequestOptions,
): Promise<PermissionInfo[]> {
  const raw = await requestClient.get<PermissionInfoRaw[]>(
    `${API_PREFIX}/available-permissions`,
    options,
  );
  return raw.map((item) => transformPermission(item));
}

/**
 * Get plan permissions / 获取套餐权限
 * GET /admin/plans/{plan_id}/permissions
 *
 * Backend returns PermissionSimpleInfo[], frontend extracts id array for PermissionSelector
 */
export async function getTenantPlanPermissionsApi(
  planId: number,
  options?: ApiRequestOptions,
): Promise<PermissionSimpleInfo[]> {
  return requestClient.get<PermissionSimpleInfo[]>(
    `${API_PREFIX}/${planId}/permissions`,
    options,
  );
}

/**
 * Set plan permissions / 设置套餐权限
 * PUT /admin/plans/{plan_id}/permissions
 */
export async function setTenantPlanPermissionsApi(
  planId: number,
  data: TenantPlanPermissionsRequest,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(`${API_PREFIX}/${planId}/permissions`, data, {
    showSuccessMessage: true,
    ...options,
  });
}
