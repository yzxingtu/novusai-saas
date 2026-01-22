/**
 * 平台角色管理 API
 * 对接后端 /admin/roles/* 接口
 */
import type { SelectOption, SelectResponse } from '#/types';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 节点类型 */
export type RoleType = 'department' | 'position' | 'role';

/** 创建角色请求 */
export interface RoleCreateRequest {
  code?: string; // 后端生成，无需前端填写
  name: string;
  description?: null | string;
  is_active?: boolean;
  sort_order?: number;
  parent_id?: null | number;
  permission_ids?: number[];
  /** 节点类型: department/position/role，默认 role */
  type?: RoleType;
  /** 是否允许添加成员，默认 true */
  allow_members?: boolean;
}

/** 更新角色请求 */
export interface RoleUpdateRequest {
  name?: null | string;
  description?: null | string;
  is_active?: boolean | null;
  sort_order?: null | number;
  permission_ids?: null | number[];
  /** 节点类型: department/position/role */
  type?: null | RoleType;
  /** 是否允许添加成员 */
  allow_members?: boolean | null;
  /** 负责人 ID */
  leader_id?: null | number;
}

/** 分配权限请求 */
export interface RolePermissionsRequest {
  permission_ids: number[];
}

/** 权限基本信息 */
export interface PermissionBasicInfo {
  id: number;
  code: string;
  name: string;
  type: string;
}

/** 负责人基本信息 */
export interface LeaderBasicInfo {
  id: number;
  username: string;
  real_name?: string;
  avatar?: string;
}

/** 角色信息（后端原始格式 snake_case） */
export interface RoleInfoRaw {
  id: number;
  code: string;
  name: string;
  description?: string;
  is_active: boolean;
  sort_order: number;
  permissions?: PermissionBasicInfo[];
  permission_ids?: number[]; // 角色详情返回的权限 ID 列表
  permissions_count?: number;
  created_at: string;
  updated_at?: string;
  // 组织架构扩展字段
  type?: RoleType;
  level?: number;
  has_children?: boolean;
  allow_members?: boolean;
  member_count?: number;
  leader_id?: null | number;
  leader?: LeaderBasicInfo | null;
}

/** 角色信息（前端格式 camelCase） */
export interface RoleInfo {
  id: number;
  code: string;
  name: string;
  description?: string;
  isActive: boolean;
  sortOrder: number;
  parentId?: null | number;
  permissions?: PermissionBasicInfo[];
  permissionIds?: number[]; // 角色详情返回的权限 ID 列表
  permissionsCount?: number;
  children?: RoleInfo[];
  createdAt: string;
  updatedAt?: string;
  // 组织架构扩展字段
  type?: RoleType;
  level?: number;
  hasChildren?: boolean;
  allowMembers?: boolean;
  memberCount?: number;
  leaderId?: null | number;
  leader?: LeaderBasicInfo | null;
}

/** 移动角色请求 */
export interface RoleMoveRequest {
  new_parent_id: null | number;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
function transformRoleInfo(raw: RoleInfoRaw): RoleInfo {
  return {
    id: raw.id,
    code: raw.code,
    name: raw.name,
    description: raw.description,
    isActive: raw.is_active,
    sortOrder: raw.sort_order,
    parentId: (raw as any).parent_id,
    permissions: raw.permissions,
    permissionIds: raw.permission_ids,
    permissionsCount:
      (raw as any).permissions_count ??
      raw.permission_ids?.length ??
      (raw.permissions ? raw.permissions.length : 0),
    children: (raw as any).children?.map((item: RoleInfoRaw) =>
      transformRoleInfo(item),
    ),
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

const API_PREFIX = '/admin/roles';

/**
 * 获取角色列表
 * GET /admin/roles
 * 注意: 角色列表不分页，返回全部
 */
export async function getRoleListApi(
  options?: ApiRequestOptions,
): Promise<RoleInfo[]> {
  const response = await requestClient.get<RoleInfoRaw[]>(API_PREFIX, options);
  return response.map((item) => transformRoleInfo(item));
}

/**
 * 获取角色详情
 * GET /admin/roles/{role_id}
 */
export async function getRoleDetailApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<RoleInfo> {
  const raw = await requestClient.get<RoleInfoRaw>(
    `${API_PREFIX}/${roleId}`,
    options,
  );
  return transformRoleInfo(raw);
}

/**
 * 创建角色
 * POST /admin/roles
 */
export async function createRoleApi(
  data: RoleCreateRequest,
  options?: ApiRequestOptions,
): Promise<RoleInfo> {
  const raw = await requestClient.post<RoleInfoRaw>(API_PREFIX, data, options);
  return transformRoleInfo(raw);
}

/**
 * 更新角色
 * PUT /admin/roles/{role_id}
 */
export async function updateRoleApi(
  roleId: number,
  data: RoleUpdateRequest,
  options?: ApiRequestOptions,
): Promise<RoleInfo> {
  const raw = await requestClient.put<RoleInfoRaw>(
    `${API_PREFIX}/${roleId}`,
    data,
    options,
  );
  return transformRoleInfo(raw);
}

/**
 * 删除角色
 * DELETE /admin/roles/{role_id}
 */
export async function deleteRoleApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${roleId}`, options);
}

/**
 * 分配角色权限
 * PUT /admin/roles/{role_id}/permissions
 */
export async function assignRolePermissionsApi(
  roleId: number,
  data: RolePermissionsRequest,
  options?: ApiRequestOptions,
): Promise<RoleInfo> {
  const raw = await requestClient.put<RoleInfoRaw>(
    `${API_PREFIX}/${roleId}/permissions`,
    data,
    options,
  );
  return transformRoleInfo(raw);
}

/**
 * 获取角色树
 * GET /admin/roles/tree
 * 返回树形结构，包含层级关系
 */
export async function getRoleTreeApi(
  options?: ApiRequestOptions,
): Promise<RoleInfo[]> {
  const response = await requestClient.get<RoleInfoRaw[]>(
    `${API_PREFIX}/tree`,
    options,
  );
  return response.map((item) => transformRoleInfo(item));
}

/**
 * 获取子角色
 * GET /admin/roles/{role_id}/children
 */
export async function getRoleChildrenApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<RoleInfo[]> {
  const response = await requestClient.get<RoleInfoRaw[]>(
    `${API_PREFIX}/${roleId}/children`,
    options,
  );
  return response.map((item) => transformRoleInfo(item));
}

/**
 * 移动角色
 * PUT /admin/roles/{role_id}/move
 */
export async function moveRoleApi(
  roleId: number,
  data: RoleMoveRequest,
  options?: ApiRequestOptions,
): Promise<RoleInfo> {
  const raw = await requestClient.put<RoleInfoRaw>(
    `${API_PREFIX}/${roleId}/move`,
    data,
    options,
  );
  return transformRoleInfo(raw);
}

/**
 * 获取角色下拉选项
 * GET /admin/roles/select
 * 用于下拉选择器，返回简化的选项列表
 */
export async function getRoleSelectApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SelectResponse> {
  const response = await requestClient.get<SelectOption[]>(
    `${API_PREFIX}/select`,
    { params, ...options },
  );
  return { items: response };
}
