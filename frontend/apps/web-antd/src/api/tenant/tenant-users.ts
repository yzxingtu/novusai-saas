import type { SelectResponse } from '#/api/shared/types';
/**
 * Tenant user management API / 企业用户管理 API
 * Backend: /tenant/users/* / 对接后端 /tenant/users/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** User list query params / 用户列表查询参数 */
export type TenantUserListParams = Record<string, unknown>;

/** Create user request / 创建用户请求 */
export interface TenantUserCreateRequest {
  username: string;
  email: string;
  password: string;
  phone?: null | string;
  nickname?: null | string;
  is_active?: boolean;
  org_node_id?: null | number;
  role_id?: null | number;
}

/** Update user request / 更新用户请求 */
export interface TenantUserUpdateRequest {
  email?: null | string;
  phone?: null | string;
  nickname?: null | string;
  avatar?: null | string;
  is_active?: boolean | null;
  org_node_id?: null | number;
  role_id?: null | number;
  gender?: null | number;
}

/** Reset password request / 重置密码请求 */
export interface TenantUserResetPasswordRequest {
  new_password: string;
}

/** User info (backend raw format snake_case) / 用户信息（后端原始格式） */
export interface TenantUserInfoRaw {
  id: number;
  tenant_id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  gender: number;
  is_active: boolean;
  approval_status: string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  role_id?: null | number;
  role_name?: null | string;
  last_login_at?: null | string;
  created_at: string;
  updated_at?: null | string;
}

/** User info (frontend format camelCase) / 用户信息（前端格式） */
export interface TenantUserInfo {
  id: number;
  tenantId: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  gender: number;
  isActive: boolean;
  approvalStatus: string;
  orgNodeId?: null | number;
  orgNodeName?: null | string;
  roleId?: null | number;
  roleName?: null | string;
  lastLoginAt?: null | string;
  createdAt: string;
  updatedAt?: null | string;
}

export interface TenantUserIdentitySelectExtra {
  avatar?: null | string;
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
  nickname?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  role_name?: null | string;
  user_type?: null | string;
  username?: null | string;
}

/** Paginated list response / 分页列表响应 */
export interface TenantUserListResponse {
  items: TenantUserInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Convert backend snake_case to frontend camelCase / 后端转前端格式 */
function transformUserInfo(raw: TenantUserInfoRaw): TenantUserInfo {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    username: raw.username,
    email: raw.email,
    phone: raw.phone,
    nickname: raw.nickname,
    avatar: raw.avatar,
    gender: raw.gender,
    isActive: raw.is_active,
    approvalStatus: raw.approval_status,
    orgNodeId: raw.org_node_id,
    orgNodeName: raw.org_node_name,
    roleId: raw.role_id,
    roleName: raw.role_name,
    lastLoginAt: raw.last_login_at,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/tenant/users';

/**
 * Get user list / 获取用户列表
 * GET /tenant/users
 */
export async function getTenantUserListApi(
  params?: TenantUserListParams,
  options?: ApiRequestOptions,
): Promise<TenantUserListResponse> {
  const response = await requestClient.get<{
    items: TenantUserInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformUserInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * Get tenant user identity select options / 获取企业用户身份下拉
 * GET /tenant/users/select
 */
export async function getTenantUserIdentitySelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SelectResponse<TenantUserIdentitySelectExtra>> {
  return requestClient.get<SelectResponse<TenantUserIdentitySelectExtra>>(
    `${API_PREFIX}/select`,
    { params, ...options },
  );
}

/**
 * Get user detail / 获取用户详情
 * GET /tenant/users/{user_id}
 */
export async function getTenantUserDetailApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<TenantUserInfo> {
  const raw = await requestClient.get<TenantUserInfoRaw>(
    `${API_PREFIX}/${userId}`,
    options,
  );
  return transformUserInfo(raw);
}

/**
 * Create user / 创建用户
 * POST /tenant/users
 */
export async function createTenantUserApi(
  data: TenantUserCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantUserInfo> {
  const raw = await requestClient.post<TenantUserInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformUserInfo(raw);
}

/**
 * Update user / 更新用户
 * PUT /tenant/users/{user_id}
 */
export async function updateTenantUserApi(
  userId: number,
  data: TenantUserUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantUserInfo> {
  const raw = await requestClient.put<TenantUserInfoRaw>(
    `${API_PREFIX}/${userId}`,
    data,
    options,
  );
  return transformUserInfo(raw);
}

/**
 * Delete user / 删除用户
 * DELETE /tenant/users/{user_id}
 */
export async function deleteTenantUserApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${userId}`, options);
}

/**
 * Force logout tenant user / 强制下线企业用户
 * POST /tenant/users/{user_id}/force-logout
 */
export async function forceLogoutTenantUserApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(`${API_PREFIX}/${userId}/force-logout`, {}, options);
}

/**
 * Reset user password / 重置用户密码
 * PUT /tenant/users/{user_id}/reset-password
 */
export async function resetTenantUserPasswordApi(
  userId: number,
  data: TenantUserResetPasswordRequest,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${userId}/reset-password`,
    data,
    options,
  );
}

/**
 * Toggle user status / 切换用户状态
 * PUT /tenant/users/{user_id}/status?is_active=true/false
 */
export async function toggleTenantUserStatusApi(
  userId: number,
  isActive: boolean,
  options?: ApiRequestOptions,
): Promise<TenantUserInfo> {
  const raw = await requestClient.put<TenantUserInfoRaw>(
    `${API_PREFIX}/${userId}/status`,
    {},
    { params: { is_active: isActive }, ...options },
  );
  return transformUserInfo(raw);
}

/**
 * Approve user / 审批通过用户
 * PUT /tenant/users/{user_id}/approve
 */
export async function approveTenantUserApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<TenantUserInfo> {
  const raw = await requestClient.put<TenantUserInfoRaw>(
    `${API_PREFIX}/${userId}/approve`,
    {},
    options,
  );
  return transformUserInfo(raw);
}

/**
 * Reject user / 审批拒绝用户
 * PUT /tenant/users/{user_id}/reject
 */
export async function rejectTenantUserApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<TenantUserInfo> {
  const raw = await requestClient.put<TenantUserInfoRaw>(
    `${API_PREFIX}/${userId}/reject`,
    {},
    options,
  );
  return transformUserInfo(raw);
}

/**
 * Batch approve users / 批量审批通过用户
 * PUT /tenant/users/batch/approve
 */
export async function batchApproveTenantUserApi(
  ids: number[],
  options?: ApiRequestOptions,
): Promise<TenantUserInfo[]> {
  const rawList = await requestClient.put<TenantUserInfoRaw[]>(
    `${API_PREFIX}/batch/approve`,
    { ids },
    options,
  );
  return rawList.map((raw) => transformUserInfo(raw));
}

/**
 * Batch reject users / 批量审批拒绝用户
 * PUT /tenant/users/batch/reject
 */
export async function batchRejectTenantUserApi(
  ids: number[],
  options?: ApiRequestOptions,
): Promise<TenantUserInfo[]> {
  const rawList = await requestClient.put<TenantUserInfoRaw[]>(
    `${API_PREFIX}/batch/reject`,
    { ids },
    options,
  );
  return rawList.map((raw) => transformUserInfo(raw));
}
