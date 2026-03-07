/**
 * 租户用户管理 API
 * 对接后端 /tenant/users/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 用户列表查询参数 */
export type TenantUserListParams = Record<string, unknown>;

/** 创建用户请求 */
export interface TenantUserCreateRequest {
  username: string;
  email: string;
  password: string;
  phone?: null | string;
  nickname?: null | string;
  is_active?: boolean;
  role_id?: null | number;
}

/** 更新用户请求 */
export interface TenantUserUpdateRequest {
  email?: null | string;
  phone?: null | string;
  nickname?: null | string;
  avatar?: null | string;
  is_active?: boolean | null;
  role_id?: null | number;
  gender?: null | number;
}

/** 重置密码请求 */
export interface TenantUserResetPasswordRequest {
  new_password: string;
}

/** 用户信息（后端原始格式 snake_case） */
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
  role_id?: null | number;
  role_name?: null | string;
  last_login_at?: null | string;
  created_at: string;
  updated_at?: null | string;
}

/** 用户信息（前端格式 camelCase） */
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
  roleId?: null | number;
  roleName?: null | string;
  lastLoginAt?: null | string;
  createdAt: string;
  updatedAt?: null | string;
}

/** 分页列表响应 */
export interface TenantUserListResponse {
  items: TenantUserInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
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
    roleId: raw.role_id,
    roleName: raw.role_name,
    lastLoginAt: raw.last_login_at,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

// ============================================================
// API 接口
// ============================================================

const API_PREFIX = '/tenant/users';

/**
 * 获取用户列表
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
 * 获取用户详情
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
 * 创建用户
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
 * 更新用户
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
 * 删除用户
 * DELETE /tenant/users/{user_id}
 */
export async function deleteTenantUserApi(
  userId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${userId}`, options);
}

/**
 * 重置用户密码
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
 * 切换用户状态
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
 * 审批通过用户
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
 * 审批拒绝用户
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
