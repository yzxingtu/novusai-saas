/**
 * 租户管理员管理 API
 * 对接后端 /tenant/admins/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 管理员列表查询参数 */
export type TenantAdminListParams = Record<string, unknown>;

/** 创建管理员请求 */
export interface TenantAdminCreateRequest {
  username: string;
  email: string;
  password: string;
  phone?: null | string;
  nickname?: null | string;
  is_active?: boolean;
  is_owner?: boolean;
  role_id?: null | number;
}

/** 更新管理员请求 */
export interface TenantAdminUpdateRequest {
  email?: null | string;
  phone?: null | string;
  nickname?: null | string;
  avatar?: null | string;
  is_active?: boolean | null;
  is_owner?: boolean | null;
  role_id?: null | number;
}

/** 重置密码请求 */
export interface TenantAdminResetPasswordRequest {
  new_password: string;
}

/** 切换状态请求 */
export interface TenantAdminStatusRequest {
  is_active: boolean;
}

/** 管理员信息（后端原始格式 snake_case） */
export interface TenantAdminInfoRaw {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active: boolean;
  is_owner: boolean;
  role_id?: null | number;
  role_name?: null | string;
  last_login_at?: string;
  created_at: string;
  updated_at?: string;
}

/** 管理员信息（前端格式 camelCase） */
export interface TenantAdminInfo {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  isActive: boolean;
  isOwner: boolean;
  roleId?: null | number;
  roleName?: null | string;
  lastLoginAt?: string;
  createdAt: string;
  updatedAt?: string;
}

/** 分页列表响应 */
export interface TenantAdminListResponse {
  items: TenantAdminInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
function transformAdminInfo(raw: TenantAdminInfoRaw): TenantAdminInfo {
  return {
    id: raw.id,
    username: raw.username,
    email: raw.email,
    phone: raw.phone,
    nickname: raw.nickname,
    avatar: raw.avatar,
    isActive: raw.is_active,
    isOwner: raw.is_owner,
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

const API_PREFIX = '/tenant/admins';

/**
 * 获取管理员列表
 * GET /tenant/admins
 */
export async function getTenantAdminListApi(
  params?: TenantAdminListParams,
  options?: ApiRequestOptions,
): Promise<TenantAdminListResponse> {
  const response = await requestClient.get<{
    items: TenantAdminInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformAdminInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * 获取管理员详情
 * GET /tenant/admins/{admin_id}
 */
export async function getTenantAdminDetailApi(
  adminId: number,
  options?: ApiRequestOptions,
): Promise<TenantAdminInfo> {
  const raw = await requestClient.get<TenantAdminInfoRaw>(
    `${API_PREFIX}/${adminId}`,
    options,
  );
  return transformAdminInfo(raw);
}

/**
 * 创建管理员
 * POST /tenant/admins
 */
export async function createTenantAdminApi(
  data: TenantAdminCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantAdminInfo> {
  const raw = await requestClient.post<TenantAdminInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformAdminInfo(raw);
}

/**
 * 更新管理员
 * PUT /tenant/admins/{admin_id}
 */
export async function updateTenantAdminApi(
  adminId: number,
  data: TenantAdminUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantAdminInfo> {
  const raw = await requestClient.put<TenantAdminInfoRaw>(
    `${API_PREFIX}/${adminId}`,
    data,
    options,
  );
  return transformAdminInfo(raw);
}

/**
 * 删除管理员
 * DELETE /tenant/admins/{admin_id}
 */
export async function deleteTenantAdminApi(
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${adminId}`, options);
}

/**
 * 重置管理员密码
 * PUT /tenant/admins/{admin_id}/reset-password
 */
export async function resetTenantAdminPasswordApi(
  adminId: number,
  data: TenantAdminResetPasswordRequest,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${adminId}/reset-password`,
    data,
    options,
  );
}

/**
 * 切换管理员状态
 * PUT /tenant/admins/{admin_id}/status?is_active=true/false
 */
export async function toggleTenantAdminStatusApi(
  adminId: number,
  data: TenantAdminStatusRequest,
  options?: ApiRequestOptions,
): Promise<TenantAdminInfo> {
  const raw = await requestClient.put<TenantAdminInfoRaw>(
    `${API_PREFIX}/${adminId}/status`,
    {},
    { params: data, ...options },
  );
  return transformAdminInfo(raw);
}
