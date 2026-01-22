/**
 * 平台管理员管理 API
 * 对接后端 /admin/admins/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 管理员列表查询参数 */
export type AdminListParams = Record<string, unknown>;

/** 创建管理员请求 */
export interface AdminCreateRequest {
  username: string;
  email: string;
  password: string;
  phone?: null | string;
  nickname?: null | string;
  is_active?: boolean;
  is_super?: boolean;
  role_id?: null | number;
}

/** 更新管理员请求 */
export interface AdminUpdateRequest {
  email?: null | string;
  phone?: null | string;
  nickname?: null | string;
  avatar?: null | string;
  is_active?: boolean | null;
  is_super?: boolean | null;
  role_id?: null | number;
}

/** 重置密码请求 */
export interface AdminResetPasswordRequest {
  new_password: string;
}

/** 切换状态请求 */
export interface AdminStatusRequest {
  is_active: boolean;
}

/** 角色信息 */
export interface RoleBasicInfo {
  id: number;
  code: string;
  name: string;
}

/** 管理员信息（后端原始格式 snake_case） */
export interface AdminInfoRaw {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active: boolean;
  is_super: boolean;
  role_id?: null | number;
  role_name?: null | string;
  last_login_at?: string;
  created_at: string;
  updated_at?: string;
}

/** 管理员信息（前端格式 camelCase） */
export interface AdminInfo {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  isActive: boolean;
  isSuper: boolean;
  roleId?: null | number;
  roleName?: null | string;
  lastLoginAt?: string;
  createdAt: string;
  updatedAt?: string;
}

/** 分页列表响应 */
export interface AdminListResponse {
  items: AdminInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
function transformAdminInfo(raw: AdminInfoRaw): AdminInfo {
  return {
    id: raw.id,
    username: raw.username,
    email: raw.email,
    phone: raw.phone,
    nickname: raw.nickname,
    avatar: raw.avatar,
    isActive: raw.is_active,
    isSuper: raw.is_super,
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

const API_PREFIX = '/admin/admins';

/**
 * 获取管理员列表
 * GET /admin/admins
 */
export async function getAdminListApi(
  params?: AdminListParams,
  options?: ApiRequestOptions,
): Promise<AdminListResponse> {
  const response = await requestClient.get<{
    items: AdminInfoRaw[];
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
 * GET /admin/admins/{admin_id}
 */
export async function getAdminDetailApi(
  adminId: number,
  options?: ApiRequestOptions,
): Promise<AdminInfo> {
  const raw = await requestClient.get<AdminInfoRaw>(
    `${API_PREFIX}/${adminId}`,
    options,
  );
  return transformAdminInfo(raw);
}

/**
 * 创建管理员
 * POST /admin/admins
 */
export async function createAdminApi(
  data: AdminCreateRequest,
  options?: ApiRequestOptions,
): Promise<AdminInfo> {
  const raw = await requestClient.post<AdminInfoRaw>(API_PREFIX, data, options);
  return transformAdminInfo(raw);
}

/**
 * 更新管理员
 * PUT /admin/admins/{admin_id}
 */
export async function updateAdminApi(
  adminId: number,
  data: AdminUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AdminInfo> {
  const raw = await requestClient.put<AdminInfoRaw>(
    `${API_PREFIX}/${adminId}`,
    data,
    options,
  );
  return transformAdminInfo(raw);
}

/**
 * 删除管理员
 * DELETE /admin/admins/{admin_id}
 */
export async function deleteAdminApi(
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${adminId}`, options);
}

/**
 * 重置管理员密码
 * PUT /admin/admins/{admin_id}/reset-password
 */
export async function resetAdminPasswordApi(
  adminId: number,
  data: AdminResetPasswordRequest,
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
 * PUT /admin/admins/{admin_id}/status?is_active=true/false
 */
export async function toggleAdminStatusApi(
  adminId: number,
  data: AdminStatusRequest,
  options?: ApiRequestOptions,
): Promise<AdminInfo> {
  const raw = await requestClient.put<AdminInfoRaw>(
    `${API_PREFIX}/${adminId}/status`,
    {},
    { params: data, ...options },
  );
  return transformAdminInfo(raw);
}
