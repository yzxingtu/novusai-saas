/**
 * Platform organization management API / 平台组织架构管理 API
 * Backend: /admin/roles/* (organization related)
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Node type enum / 节点类型枚举 */
export type OrgNodeType = 'department' | 'position' | 'role';

/** Leader basic info / 负责人基本信息 */
export interface LeaderInfo {
  id: number;
  username: string;
  nickname?: string;
  avatar?: string;
}

/** Org node info (backend raw snake_case) / 组织架构节点信息（后端原始） */
export interface OrgNodeInfoRaw {
  id: number;
  code: string;
  name: string;
  description?: string;
  type: OrgNodeType;
  is_active: boolean;
  sort_order: number;
  parent_id?: null | number;
  level: number;
  has_children: boolean;
  allow_members: boolean;
  member_count: number;
  leader_id?: null | number;
  leader?: LeaderInfo | null;
  permissions_count?: number;
  created_at: string;
  updated_at?: string;
}

/** Org node info (frontend camelCase) / 组织架构节点信息（前端） */
export interface OrgNodeInfo {
  id: number;
  code: string;
  name: string;
  description?: string;
  type: OrgNodeType;
  isActive: boolean;
  sortOrder: number;
  parentId?: null | number;
  level: number;
  hasChildren: boolean;
  allowMembers: boolean;
  memberCount: number;
  leaderId?: null | number;
  leader?: LeaderInfo | null;
  permissionsCount?: number;
  createdAt: string;
  updatedAt?: string;
  /** Frontend tree control: children (dynamically populated on lazy load) / 前端树形控件子节点 */
  children?: OrgNodeInfo[];
  /** Frontend tree control: loading children / 前端树形控件加载中 */
  loading?: boolean;
}

/** Node member info (backend raw) / 节点成员信息（后端原始） */
export interface OrgMemberRaw {
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

/** Node member info (frontend) / 节点成员信息（前端） */
export interface OrgMember {
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
export interface MemberListParams {
  /** Search keyword (username/nickname/email) / 搜索关键词 */
  search?: string;
  /** Page number / 页码 */
  page?: number;
  /** Page size / 每页数量 */
  pageSize?: number;
  /** Include descendant members (recursive), default true / 是否包含子节点成员 */
  includeDescendants?: boolean;
}

/** Member list paginated response (backend raw) / 成员列表分页响应（后端原始） */
export interface MemberListResponseRaw {
  items: OrgMemberRaw[];
  total: number;
  page: number;
  page_size: number;
}

/** Member list paginated response (frontend) / 成员列表分页响应（前端） */
export interface MemberListResponse {
  items: OrgMember[];
  total: number;
  page: number;
  pageSize: number;
}

/** Add member request (associate existing member) / 添加成员请求（关联现有） */
export interface AddMemberRequest {
  admin_id: number;
}

/** Create member request (create new member) / 创建成员请求（直接创建） */
export interface CreateMemberRequest {
  username: string;
  email: string;
  password: string;
  phone?: null | string;
  nickname?: null | string;
  is_active?: boolean;
  is_super?: boolean;
}

/** Update member request / 更新成员请求 */
export interface UpdateMemberRequest {
  email?: null | string;
  phone?: null | string;
  nickname?: null | string;
  avatar?: null | string;
  is_active?: boolean | null;
  is_super?: boolean | null;
  /** New role ID (change role group) / 新角色 ID */
  role_id?: null | number;
}

/** Reset member password request / 重置成员密码请求 */
export interface ResetMemberPasswordRequest {
  new_password: string;
}

/** Toggle member status request / 切换成员状态请求 */
export interface MemberStatusRequest {
  is_active: boolean;
}

/** Set leader request / 设置负责人请求 */
export interface SetLeaderRequest {
  leader_id: null | number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Convert backend node data to frontend format / 将后端节点数据转换为前端格式 */
function transformOrgNode(raw: OrgNodeInfoRaw): OrgNodeInfo {
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

/** Convert backend member data to frontend format / 将后端成员数据转换为前端格式 */
function transformOrgMember(raw: OrgMemberRaw): OrgMember {
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

const API_PREFIX = '/admin/roles';

/**
 * Get organization root nodes / 获取组织架构根节点
 * GET /admin/roles/organization
 * Returns level=1 root nodes with has_children flag
 */
export async function getOrganizationRootNodesApi(
  options?: ApiRequestOptions,
): Promise<OrgNodeInfo[]> {
  const response = await requestClient.get<OrgNodeInfoRaw[]>(
    `${API_PREFIX}/organization`,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

/**
 * Get child nodes (lazy load) / 获取子节点（按需加载）
 * GET /admin/roles/{role_id}/children
 */
export async function getNodeChildrenApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<OrgNodeInfo[]> {
  const response = await requestClient.get<OrgNodeInfoRaw[]>(
    `${API_PREFIX}/${roleId}/children`,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

/**
 * Get node member list (paginated + search) / 获取节点成员列表
 * GET /admin/roles/{role_id}/members
 * @param roleId - Node ID / 节点 ID
 * @param params - Query params (search, pagination) / 查询参数
 * @param options - Request options / 请求选项
 */
export async function getNodeMembersApi(
  roleId: number,
  params?: MemberListParams,
  options?: ApiRequestOptions,
): Promise<MemberListResponse> {
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
  // Recursively query descendant members, default true / 递归查询子节点成员
  if (params?.includeDescendants !== undefined) {
    queryParams.include_descendants = params.includeDescendants;
  }

  const response = await requestClient.get<MemberListResponseRaw>(
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
 * Add member to node (associate existing user) / 添加成员到节点
 * POST /admin/roles/{role_id}/members
 */
export async function addMemberToNodeApi(
  roleId: number,
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `${API_PREFIX}/${roleId}/members`,
    { admin_id: adminId } as AddMemberRequest,
    options,
  );
}

/**
 * Create new member under node / 在节点下创建新成员
 * POST /admin/roles/{role_id}/members/create
 */
export async function createMemberApi(
  roleId: number,
  data: CreateMemberRequest,
  options?: ApiRequestOptions,
): Promise<OrgMember> {
  const raw = await requestClient.post<OrgMemberRaw>(
    `${API_PREFIX}/${roleId}/members/create`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

/**
 * Update node member info / 更新节点成员信息
 * PUT /admin/roles/{role_id}/members/{admin_id}
 */
export async function updateMemberApi(
  roleId: number,
  adminId: number,
  data: UpdateMemberRequest,
  options?: ApiRequestOptions,
): Promise<OrgMember> {
  const raw = await requestClient.put<OrgMemberRaw>(
    `${API_PREFIX}/${roleId}/members/${adminId}`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

/**
 * Reset member password / 重置成员密码
 * PUT /admin/roles/{role_id}/members/{admin_id}/reset-password
 */
export async function resetMemberPasswordApi(
  roleId: number,
  adminId: number,
  data: ResetMemberPasswordRequest,
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
 * PUT /admin/roles/{role_id}/members/{admin_id}/status
 */
export async function toggleMemberStatusApi(
  roleId: number,
  adminId: number,
  data: MemberStatusRequest,
  options?: ApiRequestOptions,
): Promise<OrgMember> {
  const raw = await requestClient.put<OrgMemberRaw>(
    `${API_PREFIX}/${roleId}/members/${adminId}/status`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

/**
 * Remove member from node / 从节点移除成员
 * DELETE /admin/roles/{role_id}/members/{admin_id}
 */
export async function removeMemberFromNodeApi(
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
 * PUT /admin/roles/{role_id}/leader
 * @param roleId - Node ID / 节点 ID
 * @param leaderId - Leader ID, pass null to unset / 负责人 ID，传 null 取消
 * @param options - Request options / 请求选项
 */
export async function setNodeLeaderApi(
  roleId: number,
  leaderId: null | number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${roleId}/leader`,
    { leader_id: leaderId } as SetLeaderRequest,
    options,
  );
}
