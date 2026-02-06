/**
 * 租户管理 API
 * 对接后端 /admin/tenants/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 套餐类型 */
export type TenantPlan = 'basic' | 'enterprise' | 'free' | 'pro';

/** 租户列表查询参数 */
export type TenantListParams = Record<string, unknown>;

/** 创建租户请求 */
export interface TenantCreateRequest {
  /** 租户编码（可选，后端自动生成） */
  code?: string;
  name: string;
  contact_name?: null | string;
  contact_phone?: null | string;
  contact_email?: null | string;
  plan?: TenantPlan;
  quota?: null | Record<string, any>;
  expires_at?: null | string;
  remark?: null | string;
}

/** 更新租户请求 */
export interface TenantUpdateRequest {
  name?: null | string;
  contact_name?: null | string;
  contact_phone?: null | string;
  contact_email?: null | string;
  plan?: null | TenantPlan;
  quota?: null | Record<string, any>;
  expires_at?: null | string;
  remark?: null | string;
}

/** 切换状态请求 */
export interface TenantStatusRequest {
  is_active: boolean;
}

/** 域名简要信息（后端原始格式） */
export interface TenantDomainBriefRaw {
  id: number;
  tenant_id: number;
  domain: string;
  is_verified: boolean;
  verified_at: null | string;
  is_primary: boolean;
  ssl_status: 'active' | 'failed' | 'pending';
  ssl_expires_at: null | string;
  cname_target: null | string;
  remark: null | string;
  created_at: string;
  updated_at: string;
}

/** 域名简要信息（前端格式） */
export interface TenantDomainBrief {
  id: number;
  domain: string;
  domainType: 'custom' | 'default';
  isPrimary: boolean;
  verificationStatus: 'pending' | 'verified';
  sslStatus: 'active' | 'failed' | 'pending';
  cnameTarget?: null | string;
}

/** 套餐简要信息（后端原始格式） */
export interface TenantPlanBriefRaw {
  id: number;
  code: string;
  name: string;
}

/** 套餐简要信息（前端格式） */
export interface TenantPlanBrief {
  id: number;
  code: string;
  name: string;
}

/** 租户信息（后端原始格式 snake_case） */
export interface TenantInfoRaw {
  id: number;
  code: string;
  name: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  plan?: null | TenantPlan;
  plan_id?: null | number;
  plan_info?: null | TenantPlanBriefRaw;
  quota?: Record<string, any>;
  is_active: boolean;
  expires_at?: string;
  remark?: string;
  created_at: string;
  updated_at?: string;
  // 域名信息
  primary_domain?: null | TenantDomainBriefRaw;
  domain_count?: number;
  domains?: TenantDomainBriefRaw[];
}

/** 租户信息（前端格式 camelCase） */
export interface TenantInfo {
  id: number;
  code: string;
  name: string;
  contactName?: string;
  contactPhone?: string;
  contactEmail?: string;
  plan?: null | TenantPlan;
  planId?: null | number;
  planInfo?: null | TenantPlanBrief;
  quota?: Record<string, any>;
  isActive: boolean;
  expiresAt?: string;
  remark?: string;
  createdAt: string;
  updatedAt?: string;
  // 域名信息
  primaryDomain?: null | TenantDomainBrief;
  domainCount?: number;
  domains?: TenantDomainBrief[];
}

/** 分页列表响应 */
export interface TenantListResponse {
  items: TenantInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// 转换函数
// ============================================================

/** 转换域名简要信息 */
function transformDomainBrief(raw: TenantDomainBriefRaw): TenantDomainBrief {
  return {
    id: raw.id,
    domain: raw.domain,
    // 根据 remark 或其他逻辑推断类型，因为后端未返回 domain_type
    domainType: raw.remark?.includes('默认') ? 'default' : 'custom',
    isPrimary: raw.is_primary,
    verificationStatus: raw.is_verified ? 'verified' : 'pending',
    sslStatus: raw.ssl_status,
    cnameTarget: raw.cname_target,
  };
}

/** 将后端 snake_case 转换为前端 camelCase */
function transformTenantInfo(raw: TenantInfoRaw): TenantInfo {
  return {
    id: raw.id,
    code: raw.code,
    name: raw.name,
    contactName: raw.contact_name,
    contactPhone: raw.contact_phone,
    contactEmail: raw.contact_email,
    plan: raw.plan,
    planId: raw.plan_id,
    planInfo: raw.plan_info || null,
    quota: raw.quota,
    isActive: raw.is_active,
    expiresAt: raw.expires_at,
    remark: raw.remark,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    // 域名信息
    primaryDomain: raw.primary_domain
      ? transformDomainBrief(raw.primary_domain)
      : null,
    domainCount: raw.domain_count,
    domains: raw.domains?.map((d) => transformDomainBrief(d)),
  };
}

// ============================================================
// API 接口
// ============================================================

const API_PREFIX = '/admin/tenants';

/** 租户下拉选项结果 */
export interface TenantSelectOption {
  label: string;
  value: number;
  extra?: {
    code?: string;
    isActive?: boolean;
  };
}

/**
 * 获取租户下拉选项
 * GET /admin/tenants/select
 *
 * 权限: tenant:select
 */
export async function getTenantSelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<{ items: TenantSelectOption[] }> {
  return requestClient.get<{ items: TenantSelectOption[] }>(
    `${API_PREFIX}/select`,
    { params, ...options },
  );
}

/**
 * 获取租户列表
 * GET /admin/tenants
 */
export async function getTenantListApi(
  params?: TenantListParams,
  options?: ApiRequestOptions,
): Promise<TenantListResponse> {
  const response = await requestClient.get<{
    items: TenantInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformTenantInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * 获取租户详情
 * GET /admin/tenants/{tenant_id}
 */
export async function getTenantDetailApi(
  tenantId: number,
  options?: ApiRequestOptions,
): Promise<TenantInfo> {
  const raw = await requestClient.get<TenantInfoRaw>(
    `${API_PREFIX}/${tenantId}`,
    options,
  );
  return transformTenantInfo(raw);
}

/**
 * 创建租户
 * POST /admin/tenants
 */
export async function createTenantApi(
  data: TenantCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantInfo> {
  const raw = await requestClient.post<TenantInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformTenantInfo(raw);
}

/**
 * 更新租户
 * PUT /admin/tenants/{tenant_id}
 */
export async function updateTenantApi(
  tenantId: number,
  data: TenantUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantInfo> {
  const raw = await requestClient.put<TenantInfoRaw>(
    `${API_PREFIX}/${tenantId}`,
    data,
    options,
  );
  return transformTenantInfo(raw);
}

/**
 * 删除租户
 * DELETE /admin/tenants/{tenant_id}
 */
export async function deleteTenantApi(
  tenantId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${tenantId}`, options);
}

/**
 * 切换租户状态
 * PUT /admin/tenants/{tenant_id}/status
 */
export async function toggleTenantStatusApi(
  tenantId: number,
  data: TenantStatusRequest,
  options?: ApiRequestOptions,
): Promise<TenantInfo> {
  const raw = await requestClient.put<TenantInfoRaw>(
    `${API_PREFIX}/${tenantId}/status`,
    data,
    options,
  );
  return transformTenantInfo(raw);
}

/** 重置租户管理员密码请求 */
export interface ResetTenantOwnerPasswordRequest {
  new_password: string;
}

/**
 * 重置租户管理员密码
 * PUT /admin/tenants/{tenant_id}/reset-owner-password
 */
export async function resetTenantOwnerPasswordApi(
  tenantId: number,
  data: ResetTenantOwnerPasswordRequest,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${tenantId}/reset-owner-password`,
    data,
    options,
  );
}

// ============================================================
// 一键登录相关
// ============================================================

/** 一键登录请求 */
export interface TenantImpersonateRequest {
  role_id?: null | number;
}

/** 一键登录响应 */
export interface TenantImpersonateResponse {
  impersonateToken: string;
  tenantCode: string;
  tenantName: string;
  expiresIn: number;
}

/** 后端原始响应 */
interface TenantImpersonateResponseRaw {
  impersonate_token: string;
  tenant_code: string;
  tenant_name: string;
  expires_in: number;
}

/**
 * 一键登录租户后台
 * POST /admin/tenants/{tenant_id}/impersonate
 * 生成一键登录 Token（60秒过期，一次性使用）
 */
export async function tenantImpersonateApi(
  tenantId: number,
  data?: TenantImpersonateRequest,
  options?: ApiRequestOptions,
): Promise<TenantImpersonateResponse> {
  const raw = await requestClient.post<TenantImpersonateResponseRaw>(
    `${API_PREFIX}/${tenantId}/impersonate`,
    data || {},
    options,
  );
  return {
    impersonateToken: raw.impersonate_token,
    tenantCode: raw.tenant_code,
    tenantName: raw.tenant_name,
    expiresIn: raw.expires_in,
  };
}
