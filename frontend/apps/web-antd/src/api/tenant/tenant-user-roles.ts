/**
 * Tenant user role management API / 租户用户角色管理 API
 * Backend: /tenant/user-roles/* / 对接后端 /tenant/user-roles/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** User role list query params / 用户角色列表查询参数 */
export type TenantUserRoleListParams = Record<string, unknown>;

/** Create user role request / 创建用户角色请求 */
export interface TenantUserRoleCreateRequest {
  name: string;
  code: string;
  description?: null | string;
  is_active?: boolean;
  sort_order?: number;
  permission_ids?: number[];
}

/** Update user role request / 更新用户角色请求 */
export interface TenantUserRoleUpdateRequest {
  name?: null | string;
  code?: null | string;
  description?: null | string;
  is_active?: boolean | null;
  sort_order?: null | number;
  permission_ids?: null | number[];
}

/** Assign permissions request / 分配权限请求 */
export interface TenantUserRolePermissionsRequest {
  permission_ids: number[];
}

/** User role info (backend raw format snake_case) / 用户角色信息（后端原始格式） */
export interface TenantUserRoleInfoRaw {
  id: number;
  tenant_id: number;
  name: string;
  code: string;
  description?: null | string;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  permissions_count: number;
  member_count: number;
  permission_ids?: number[];
  permission_codes?: string[];
  created_at: string;
  updated_at?: null | string;
}

/** User role info (frontend format camelCase) / 用户角色信息（前端格式） */
export interface TenantUserRoleInfo {
  id: number;
  tenantId: number;
  name: string;
  code: string;
  description?: null | string;
  isSystem: boolean;
  isActive: boolean;
  sortOrder: number;
  permissionsCount: number;
  memberCount: number;
  permissionIds?: number[];
  permissionCodes?: string[];
  createdAt: string;
  updatedAt?: null | string;
}

/** Paginated list response / 分页列表响应 */
export interface TenantUserRoleListResponse {
  items: TenantUserRoleInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Convert backend snake_case to frontend camelCase / 后端转前端格式 */
function transformUserRoleInfo(raw: TenantUserRoleInfoRaw): TenantUserRoleInfo {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    name: raw.name,
    code: raw.code,
    description: raw.description,
    isSystem: raw.is_system,
    isActive: raw.is_active,
    sortOrder: raw.sort_order,
    permissionsCount: raw.permissions_count,
    memberCount: raw.member_count,
    permissionIds: raw.permission_ids,
    permissionCodes: raw.permission_codes,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/tenant/user-roles';

/**
 * Get user role list / 获取用户角色列表
 * GET /tenant/user-roles
 */
export async function getTenantUserRoleListApi(
  params?: TenantUserRoleListParams,
  options?: ApiRequestOptions,
): Promise<TenantUserRoleListResponse> {
  const response = await requestClient.get<{
    items: TenantUserRoleInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformUserRoleInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * Get user role detail / 获取用户角色详情
 * GET /tenant/user-roles/{role_id}
 */
export async function getTenantUserRoleDetailApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<TenantUserRoleInfo> {
  const raw = await requestClient.get<TenantUserRoleInfoRaw>(
    `${API_PREFIX}/${roleId}`,
    options,
  );
  return transformUserRoleInfo(raw);
}

/**
 * Create user role / 创建用户角色
 * POST /tenant/user-roles
 */
export async function createTenantUserRoleApi(
  data: TenantUserRoleCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantUserRoleInfo> {
  const raw = await requestClient.post<TenantUserRoleInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformUserRoleInfo(raw);
}

/**
 * Update user role / 更新用户角色
 * PUT /tenant/user-roles/{role_id}
 */
export async function updateTenantUserRoleApi(
  roleId: number,
  data: TenantUserRoleUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantUserRoleInfo> {
  const raw = await requestClient.put<TenantUserRoleInfoRaw>(
    `${API_PREFIX}/${roleId}`,
    data,
    options,
  );
  return transformUserRoleInfo(raw);
}

/**
 * Delete user role / 删除用户角色
 * DELETE /tenant/user-roles/{role_id}
 */
export async function deleteTenantUserRoleApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${roleId}`, options);
}

/**
 * Toggle user role status / 切换用户角色状态
 * PUT /tenant/user-roles/{role_id}/status?is_active=true/false
 */
export async function toggleTenantUserRoleStatusApi(
  roleId: number,
  isActive: boolean,
  options?: ApiRequestOptions,
): Promise<TenantUserRoleInfo> {
  const raw = await requestClient.put<TenantUserRoleInfoRaw>(
    `${API_PREFIX}/${roleId}/status`,
    {},
    { params: { is_active: isActive }, ...options },
  );
  return transformUserRoleInfo(raw);
}

/**
 * Assign user role permissions / 分配用户角色权限
 * PUT /tenant/user-roles/{role_id}/permissions
 */
export async function assignTenantUserRolePermissionsApi(
  roleId: number,
  data: TenantUserRolePermissionsRequest,
  options?: ApiRequestOptions,
): Promise<TenantUserRoleInfo> {
  const raw = await requestClient.put<TenantUserRoleInfoRaw>(
    `${API_PREFIX}/${roleId}/permissions`,
    data,
    options,
  );
  return transformUserRoleInfo(raw);
}
