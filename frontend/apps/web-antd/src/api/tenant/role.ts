/**
 * 租户角色管理 API
 * 对接后端 /tenant/roles/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 节点类型 */
export type TenantRoleType = 'department' | 'position' | 'role';

/** 创建角色请求 */
export interface TenantRoleCreateRequest {
  code?: string; // 后端生成
  name: string;
  description?: null | string;
  is_active?: boolean;
  sort_order?: number;
  permission_ids?: number[];
  parent_id?: null | number;
  /** 节点类型: department/position/role，默认 role */
  type?: TenantRoleType;
  /** 是否允许添加成员，默认 true */
  allow_members?: boolean;
}

/** 更新角色请求 */
export interface TenantRoleUpdateRequest {
  name?: null | string;
  description?: null | string;
  is_active?: boolean | null;
  sort_order?: null | number;
  permission_ids?: null | number[];
  parent_id?: null | number;
  /** 节点类型: department/position/role */
  type?: null | TenantRoleType;
  /** 是否允许添加成员 */
  allow_members?: boolean | null;
  /** 负责人 ID */
  leader_id?: null | number;
}

/** 分配权限请求 */
export interface TenantRolePermissionsRequest {
  permission_ids: number[];
}

/** 权限基本信息 */
export interface TenantPermissionBasicInfo {
  id: number;
  code: string;
  name: string;
  type: string;
}

/** 负责人基本信息 */
export interface TenantLeaderBasicInfo {
  id: number;
  username: string;
  real_name?: string;
  avatar?: string;
}

/** 角色信息（后端原始格式 snake_case） */
export interface TenantRoleInfoRaw {
  id: number;
  code: string;
  name: string;
  description?: string;
  is_active: boolean;
  sort_order: number;
  parent_id?: null | number;
  permissions?: TenantPermissionBasicInfo[];
  permission_ids?: number[]; // 角色详情返回的权限 ID 列表
  permissions_count?: number;
  children?: TenantRoleInfoRaw[];
  created_at: string;
  updated_at?: string;
  // 组织架构扩展字段
  type?: TenantRoleType;
  level?: number;
  has_children?: boolean;
  allow_members?: boolean;
  member_count?: number;
  leader_id?: null | number;
  leader?: null | TenantLeaderBasicInfo;
}

/** 角色信息（前端格式 camelCase） */
export interface TenantRoleInfo {
  id: number;
  code: string;
  name: string;
  description?: string;
  isActive: boolean;
  sortOrder: number;
  parentId?: null | number;
  permissions?: TenantPermissionBasicInfo[];
  permissionIds?: number[];
  permissionsCount?: number;
  children?: TenantRoleInfo[];
  createdAt: string;
  updatedAt?: string;
  // 组织架构扩展字段
  type?: TenantRoleType;
  level?: number;
  hasChildren?: boolean;
  allowMembers?: boolean;
  memberCount?: number;
  leaderId?: null | number;
  leader?: null | TenantLeaderBasicInfo;
}

/** 移动角色请求 */
export interface TenantRoleMoveRequest {
  new_parent_id: null | number;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
function transformRoleInfo(raw: TenantRoleInfoRaw): TenantRoleInfo {
  return {
    id: raw.id,
    code: raw.code,
    name: raw.name,
    description: raw.description,
    isActive: raw.is_active,
    sortOrder: raw.sort_order,
    parentId: raw.parent_id,
    permissions: raw.permissions,
    permissionIds: raw.permission_ids,
    permissionsCount:
      raw.permissions_count ??
      raw.permission_ids?.length ??
      (raw.permissions ? raw.permissions.length : 0),
    children: raw.children?.map((item) => transformRoleInfo(item)),
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    // 组织架构扩展字段
    type: raw.type,
    level: raw.level,
    hasChildren: raw.has_children,
    allowMembers: raw.allow_members,
    memberCount: raw.member_count,
    leaderId: raw.leader_id,
    leader: raw.leader,
  };
}

// ============================================================
// API 接口
// ============================================================

const API_PREFIX = '/tenant/roles';

/**
 * 获取角色列表
 * GET /tenant/roles
 * 注意: 角色列表不分页，返回全部
 */
export async function getTenantRoleListApi(
  options?: ApiRequestOptions,
): Promise<TenantRoleInfo[]> {
  const response = await requestClient.get<TenantRoleInfoRaw[]>(
    API_PREFIX,
    options,
  );
  return response.map((item) => transformRoleInfo(item));
}

/**
 * 获取角色详情
 * GET /tenant/roles/{role_id}
 */
export async function getTenantRoleDetailApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<TenantRoleInfo> {
  const raw = await requestClient.get<TenantRoleInfoRaw>(
    `${API_PREFIX}/${roleId}`,
    options,
  );
  return transformRoleInfo(raw);
}

/**
 * 创建角色
 * POST /tenant/roles
 */
export async function createTenantRoleApi(
  data: TenantRoleCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantRoleInfo> {
  const raw = await requestClient.post<TenantRoleInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformRoleInfo(raw);
}

/**
 * 更新角色
 * PUT /tenant/roles/{role_id}
 */
export async function updateTenantRoleApi(
  roleId: number,
  data: TenantRoleUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantRoleInfo> {
  const raw = await requestClient.put<TenantRoleInfoRaw>(
    `${API_PREFIX}/${roleId}`,
    data,
    options,
  );
  return transformRoleInfo(raw);
}

/**
 * 删除角色
 * DELETE /tenant/roles/{role_id}
 */
export async function deleteTenantRoleApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${roleId}`, options);
}

/**
 * 分配角色权限
 * PUT /tenant/roles/{role_id}/permissions
 */
export async function assignTenantRolePermissionsApi(
  roleId: number,
  data: TenantRolePermissionsRequest,
  options?: ApiRequestOptions,
): Promise<TenantRoleInfo> {
  const raw = await requestClient.put<TenantRoleInfoRaw>(
    `${API_PREFIX}/${roleId}/permissions`,
    data,
    options,
  );
  return transformRoleInfo(raw);
}

/**
 * 获取角色树
 * GET /tenant/roles/tree
 * 返回树形结构，包含层级关系
 */
export async function getTenantRoleTreeApi(
  options?: ApiRequestOptions,
): Promise<TenantRoleInfo[]> {
  const response = await requestClient.get<TenantRoleInfoRaw[]>(
    `${API_PREFIX}/tree`,
    options,
  );
  return response.map((item) => transformRoleInfo(item));
}

/**
 * 获取子角色
 * GET /tenant/roles/{role_id}/children
 */
export async function getTenantRoleChildrenApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<TenantRoleInfo[]> {
  const response = await requestClient.get<TenantRoleInfoRaw[]>(
    `${API_PREFIX}/${roleId}/children`,
    options,
  );
  return response.map((item) => transformRoleInfo(item));
}

/**
 * 移动角色
 * PUT /tenant/roles/{role_id}/move
 */
export async function moveTenantRoleApi(
  roleId: number,
  data: TenantRoleMoveRequest,
  options?: ApiRequestOptions,
): Promise<TenantRoleInfo> {
  const raw = await requestClient.put<TenantRoleInfoRaw>(
    `${API_PREFIX}/${roleId}/move`,
    data,
    options,
  );
  return transformRoleInfo(raw);
}
