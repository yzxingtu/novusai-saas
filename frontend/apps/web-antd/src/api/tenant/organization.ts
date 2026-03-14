/**
 * Tenant organization structure management API / 企业组织架构管理 API
 * Backend: /tenant/roles/* organization-related endpoints / 对接后端 /tenant/roles/* 组织架构相关接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions (reuse platform definitions with Tenant prefix) / 类型定义
// ============================================================

/** Node type enum / 节点类型枚举 */
export type TenantOrgNodeType = 'department' | 'position' | 'role';

/** Leader basic info / 负责人基本信息 */
export interface TenantLeaderInfo {
  id: number;
  username: string;
  nickname?: string;
  avatar?: string;
}

/** Org node info (backend raw format snake_case) / 组织架构节点信息（后端原始格式） */
export interface TenantOrgNodeInfoRaw {
  id: number;
  code: string;
  name: string;
  description?: string;
  type: TenantOrgNodeType;
  is_active: boolean;
  sort_order: number;
  parent_id?: null | number;
  level: number;
  has_children: boolean;
  allow_members: boolean;
  member_count: number;
  leader_id?: null | number;
  leader?: null | TenantLeaderInfo;
  permissions_count?: number;
  created_at: string;
  updated_at?: string;
}

/** Org node info (frontend format camelCase) / 组织架构节点信息（前端格式） */
export interface TenantOrgNodeInfo {
  id: number;
  code: string;
  name: string;
  description?: string;
  type: TenantOrgNodeType;
  isActive: boolean;
  sortOrder: number;
  parentId?: null | number;
  level: number;
  hasChildren: boolean;
  allowMembers: boolean;
  memberCount: number;
  leaderId?: null | number;
  leader?: null | TenantLeaderInfo;
  permissionsCount?: number;
  createdAt: string;
  updatedAt?: string;
  /** For frontend tree component: child nodes (dynamically filled on lazy load) / 前端树形控件使用 */
  children?: TenantOrgNodeInfo[];
  /** For frontend tree component: whether loading child nodes / 是否正在加载子节点 */
  loading?: boolean;
}

/** Node member info (backend raw format) / 节点成员信息（后端原始格式） */
export interface TenantOrgMemberRaw {
  id: number;
  username: string;
  nickname?: string;
  email?: string;
  avatar?: string;
  is_active: boolean;
  is_leader: boolean;
  joined_at: string;
  /** Role ID / 所属角色 ID */
  role_id?: number;
  /** Role name / 所属角色名称 */
  role_name?: string;
  /** Created at / 创建时间 */
  created_at?: string;
  /** Updated at / 更新时间 */
  updated_at?: string;
}

/** Node member info (frontend format) / 节点成员信息（前端格式） */
export interface TenantOrgMember {
  id: number;
  username: string;
  nickname?: string;
  email?: string;
  avatar?: string;
  isActive: boolean;
  isLeader: boolean;
  joinedAt: string;
  /** Role ID / 所属角色 ID */
  roleId?: number;
  /** Role name / 所属角色名称 */
  roleName?: string;
  /** Created at / 创建时间 */
  createdAt?: string;
  /** Updated at / 更新时间 */
  updatedAt?: string;
}

/** Member list query params / 成员列表查询参数 */
export interface TenantMemberListParams {
  /** Search keyword (username/nickname/email) / 搜索关键词 */
  search?: string;
  /** Page number / 页码 */
  page?: number;
  /** Page size / 每页数量 */
  pageSize?: number;
  /** Whether to include descendant members (recursive), default true / 是否包含子节点成员 */
  includeDescendants?: boolean;
}

/** Member list paginated response (backend raw format) / 成员列表分页响应（后端原始格式） */
export interface TenantMemberListResponseRaw {
  items: TenantOrgMemberRaw[];
  total: number;
  page: number;
  page_size: number;
}

/** Member list paginated response (frontend format) / 成员列表分页响应（前端格式） */
export interface TenantMemberListResponse {
  items: TenantOrgMember[];
  total: number;
  page: number;
  pageSize: number;
}

/** Add member request / 添加成员请求 */
export interface TenantAddMemberRequest {
  admin_id: number;
}

/** Create member request (create new member directly) / 创建成员请求 */
export interface TenantCreateMemberRequest {
  username: string;
  email: string;
  password: string;
  phone?: null | string;
  nickname?: null | string;
  is_active?: boolean;
  is_super?: boolean;
}

/** Update member request / 更新成员请求 */
export interface TenantUpdateMemberRequest {
  email?: null | string;
  phone?: null | string;
  nickname?: null | string;
  avatar?: null | string;
  is_active?: boolean | null;
  is_super?: boolean | null;
  /** New role ID (reassign to a different role group) / 新角色 ID */
  role_id?: null | number;
}

/** Reset member password request / 重置成员密码请求 */
export interface TenantResetMemberPasswordRequest {
  new_password: string;
}

/** Toggle member status request / 切换成员状态请求 */
export interface TenantMemberStatusRequest {
  is_active: boolean;
}

/** Set leader request / 设置负责人请求 */
export interface TenantSetLeaderRequest {
  leader_id: null | number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Convert backend node data to frontend format / 后端节点转前端格式 */
function transformOrgNode(raw: TenantOrgNodeInfoRaw): TenantOrgNodeInfo {
  return {
    id: raw.id,
    code: raw.code,
    name: raw.name,
    description: raw.description,
    type: raw.type,
    isActive: raw.is_active,
    sortOrder: raw.sort_order,
    parentId: raw.parent_id,
    level: raw.level,
    hasChildren: raw.has_children,
    allowMembers: raw.allow_members,
    memberCount: raw.member_count,
    leaderId: raw.leader_id,
    leader: raw.leader,
    permissionsCount: raw.permissions_count,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/** Convert backend member data to frontend format / 后端成员转前端格式 */
function transformOrgMember(raw: TenantOrgMemberRaw): TenantOrgMember {
  return {
    id: raw.id,
    username: raw.username,
    nickname: raw.nickname,
    email: raw.email,
    avatar: raw.avatar,
    isActive: raw.is_active,
    isLeader: raw.is_leader,
    joinedAt: raw.joined_at,
    roleId: raw.role_id,
    roleName: raw.role_name,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/tenant/roles';

/**
 * Get organization root nodes / 获取组织架构根节点
 * GET /tenant/roles/organization
 * Returns level=1 root node list with has_children flag / 返回根节点列表
 */
export async function getTenantOrganizationRootNodesApi(
  options?: ApiRequestOptions,
): Promise<TenantOrgNodeInfo[]> {
  const response = await requestClient.get<TenantOrgNodeInfoRaw[]>(
    `${API_PREFIX}/organization`,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

/**
 * Get child nodes (lazy load) / 获取子节点（按需加载）
 * GET /tenant/roles/{role_id}/children
 */
export async function getTenantNodeChildrenApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<TenantOrgNodeInfo[]> {
  const response = await requestClient.get<TenantOrgNodeInfoRaw[]>(
    `${API_PREFIX}/${roleId}/children`,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

/**
 * Get node member list / 获取节点成员列表
 * GET /tenant/roles/{role_id}/members
 * @param roleId - Node ID / 节点 ID
 * @param params - Query params (search, pagination) / 查询参数
 * @param options - Request options / 请求选项
 */
export async function getTenantNodeMembersApi(
  roleId: number,
  params?: TenantMemberListParams,
  options?: ApiRequestOptions,
): Promise<TenantMemberListResponse> {
  const queryParams: Record<string, boolean | number | string> = {};
  if (params?.search) {
    queryParams.search = params.search;
  }
  if (params?.page) {
    queryParams['page[number]'] = params.page;
  }
  if (params?.pageSize) {
    queryParams['page[size]'] = params.pageSize;
  }
  // Recursive query for descendant members, default true / 递归查询子节点成员
  if (params?.includeDescendants !== undefined) {
    queryParams.include_descendants = params.includeDescendants;
  }

  const response = await requestClient.get<TenantMemberListResponseRaw>(
    `${API_PREFIX}/${roleId}/members`,
    {
      ...options,
      params: queryParams,
    },
  );
  return {
    items: response.items.map((item) => transformOrgMember(item)),
    total: response.total,
    page: response.page,
    pageSize: response.page_size,
  };
}

/**
 * Add member to node / 添加成员到节点
 * POST /tenant/roles/{role_id}/members
 */
export async function addTenantMemberToNodeApi(
  roleId: number,
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `${API_PREFIX}/${roleId}/members`,
    { admin_id: adminId } as TenantAddMemberRequest,
    options,
  );
}

/**
 * Create new member under node / 在节点下创建新成员
 * POST /tenant/roles/{role_id}/members/create
 */
export async function createTenantMemberApi(
  roleId: number,
  data: TenantCreateMemberRequest,
  options?: ApiRequestOptions,
): Promise<TenantOrgMember> {
  const raw = await requestClient.post<TenantOrgMemberRaw>(
    `${API_PREFIX}/${roleId}/members/create`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

/**
 * Update node member info / 更新节点成员信息
 * PUT /tenant/roles/{role_id}/members/{admin_id}
 */
export async function updateTenantMemberApi(
  roleId: number,
  adminId: number,
  data: TenantUpdateMemberRequest,
  options?: ApiRequestOptions,
): Promise<TenantOrgMember> {
  const raw = await requestClient.put<TenantOrgMemberRaw>(
    `${API_PREFIX}/${roleId}/members/${adminId}`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

/**
 * Reset member password / 重置成员密码
 * PUT /tenant/roles/{role_id}/members/{admin_id}/reset-password
 */
export async function resetTenantMemberPasswordApi(
  roleId: number,
  adminId: number,
  data: TenantResetMemberPasswordRequest,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${roleId}/members/${adminId}/reset-password`,
    data,
    options,
  );
}

/**
 * Toggle member status / 切换成员状态
 * PUT /tenant/roles/{role_id}/members/{admin_id}/status
 */
export async function toggleTenantMemberStatusApi(
  roleId: number,
  adminId: number,
  data: TenantMemberStatusRequest,
  options?: ApiRequestOptions,
): Promise<TenantOrgMember> {
  const raw = await requestClient.put<TenantOrgMemberRaw>(
    `${API_PREFIX}/${roleId}/members/${adminId}/status`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

/**
 * Remove member from node / 从节点移除成员
 * DELETE /tenant/roles/{role_id}/members/{admin_id}
 */
export async function removeTenantMemberFromNodeApi(
  roleId: number,
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${API_PREFIX}/${roleId}/members/${adminId}`,
    options,
  );
}

/**
 * Set node leader / 设置节点负责人
 * PUT /tenant/roles/{role_id}/leader
 * @param roleId - Node ID / 节点 ID
 * @param leaderId - Leader ID, pass null to unset / 负责人 ID，传 null 取消
 * @param options - Request options / 请求选项
 */
export async function setTenantNodeLeaderApi(
  roleId: number,
  leaderId: null | number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${roleId}/leader`,
    { leader_id: leaderId } as TenantSetLeaderRequest,
    options,
  );
}
