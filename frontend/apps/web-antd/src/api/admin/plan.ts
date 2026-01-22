/**
 * 套餐管理 API
 * 对接后端 /admin/plans/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 计费周期 */
export type BillingCycle =
  | 'lifetime'
  | 'monthly'
  | 'one_time'
  | 'quarterly'
  | 'yearly';

/** 配额配置 */
export interface QuotaSchema {
  /** 是否允许自定义域名 */
  allowCustomDomain?: boolean | null;
  /** 每月 API 调用次数 */
  apiCallsPerMonth?: null | number;
  /** 最大管理员数 */
  maxAdmins?: null | number;
  /** 最大自定义域名数 */
  maxCustomDomains?: null | number;
  /** 最大文件大小(MB) */
  maxFileSizeMb?: null | number;
  /** 最大用户数 */
  maxUsers?: null | number;
  /** 存储限制(GB) */
  storageLimitGb?: null | number;
}

/** 后端配额格式 (snake_case) */
interface QuotaSchemaRaw {
  allow_custom_domain?: boolean | null;
  api_calls_per_month?: null | number;
  max_admins?: null | number;
  max_custom_domains?: null | number;
  max_file_size_mb?: null | number;
  max_users?: null | number;
  storage_limit_gb?: null | number;
}

/** 特性标记 */
export interface FeaturesSchema {
  /** 高级分析 */
  advancedAnalytics?: boolean | null;
  /** AI 功能 */
  aiEnabled?: boolean | null;
  /** 优先支持 */
  prioritySupport?: boolean | null;
  /** 白标支持 */
  whiteLabel?: boolean | null;
}

/** 后端特性格式 (snake_case) */
interface FeaturesSchemaRaw {
  advanced_analytics?: boolean | null;
  ai_enabled?: boolean | null;
  priority_support?: boolean | null;
  white_label?: boolean | null;
}

/** 套餐信息（后端原始格式 snake_case） */
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

/** 套餐信息（前端格式 camelCase） */
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

/** 创建套餐请求 */
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

/** 更新套餐请求 */
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

/** 切换状态请求 */
export interface TenantPlanStatusRequest {
  is_active: boolean;
}

/** 设置权限请求 */
export interface TenantPlanPermissionsRequest {
  permission_ids: number[];
}

/** 权限信息 */
export interface PermissionInfo {
  children?: PermissionInfo[];
  code: string;
  id: number;
  name: string;
  parentId?: null | number;
}

/** 后端权限格式 */
interface PermissionInfoRaw {
  children?: PermissionInfoRaw[];
  code: string;
  id: number;
  name: string;
  parent_id?: null | number;
}

/** 套餐列表查询参数 */
export type TenantPlanListParams = Record<string, unknown>;

/** 分页列表响应 */
export interface TenantPlanListResponse {
  items: TenantPlanInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** 下拉选项（遵循通用远程下拉方案） */
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
// 转换函数
// ============================================================

/** 转换配额 snake_case -> camelCase */
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

/** 转换特性 snake_case -> camelCase */
function transformFeatures(
  raw?: FeaturesSchemaRaw | null,
): FeaturesSchema | null {
  if (!raw) return null;
  return {
    advancedAnalytics: raw.advanced_analytics,
    aiEnabled: raw.ai_enabled,
    prioritySupport: raw.priority_support,
    whiteLabel: raw.white_label,
  };
}

/** 将后端 snake_case 转换为前端 camelCase */
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

/** 转换权限树 */
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
// API 接口
// ============================================================

const API_PREFIX = '/admin/plans';

/**
 * 获取套餐列表
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
 * 获取套餐详情
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
 * 创建套餐
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
 * 更新套餐
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
 * 删除套餐
 * DELETE /admin/plans/{plan_id}
 */
export async function deleteTenantPlanApi(
  planId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${planId}`, options);
}

/**
 * 重新排序套餐
 * PUT /admin/plans/reorder
 */
export async function reorderTenantPlansApi(
  ids: number[],
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(`${API_PREFIX}/reorder`, { ids }, options);
}

/**
 * 切换套餐状态
 * PUT /admin/plans/{plan_id}/status (假设有此接口，否则使用 update)
 */
export async function toggleTenantPlanStatusApi(
  planId: number,
  data: TenantPlanStatusRequest,
  options?: ApiRequestOptions,
): Promise<TenantPlanInfo> {
  // 使用 update 接口切换状态
  const raw = await requestClient.put<TenantPlanInfoRaw>(
    `${API_PREFIX}/${planId}`,
    data,
    options,
  );
  return transformTenantPlanInfo(raw);
}

/** 套餐下拉选项响应 */
export interface TenantPlanSelectResponse {
  items: TenantPlanSelectOption[];
  total?: number;
  page?: number;
  page_size?: number;
  has_more?: boolean;
}

/**
 * 获取套餐下拉选项
 * GET /admin/plans/select
 *
 * 返回结构遵循《通用远程下拉方案》: { data: { items: [{label, value, extra}] } }
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
 * 获取可分配的权限列表
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
 * 获取套餐权限
 * GET /admin/plans/{plan_id}/permissions
 */
export async function getTenantPlanPermissionsApi(
  planId: number,
  options?: ApiRequestOptions,
): Promise<number[]> {
  return requestClient.get<number[]>(
    `${API_PREFIX}/${planId}/permissions`,
    options,
  );
}

/**
 * 设置套餐权限
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
