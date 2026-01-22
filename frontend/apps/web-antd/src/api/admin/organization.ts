/**
 * 平台组织架构管理 API
 * 对接后端 /admin/roles/* 组织架构相关接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 节点类型枚举 */
export type OrgNodeType = 'department' | 'position' | 'role';

/** 负责人基本信息 */
export interface LeaderInfo {
  id: number;
  username: string;
  realName?: string;
  avatar?: string;
}

/** 组织架构节点信息（后端原始格式 snake_case） */
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

/** 组织架构节点信息（前端格式 camelCase） */
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
  /** 前端树形控件使用：子节点（按需加载时动态填充） */
  children?: OrgNodeInfo[];
  /** 前端树形控件使用：是否正在加载子节点 */
  loading?: boolean;
}

/** 节点成员信息（后端原始格式） */
export interface OrgMemberRaw {
  id: number;
  username: string;
  real_name?: string;
  email?: string;
  avatar?: string;
  is_active: boolean;
  is_leader: boolean;
  joined_at: string;
  /** 所属角色 ID */
  role_id?: number;
  /** 所属角色名称 */
  role_name?: string;
  /** 创建时间 */
  created_at?: string;
  /** 更新时间 */
  updated_at?: string;
}

/** 节点成员信息（前端格式） */
export interface OrgMember {
  id: number;
  username: string;
  realName?: string;
  email?: string;
  avatar?: string;
  isActive: boolean;
  isLeader: boolean;
  joinedAt: string;
  /** 所属角色 ID */
  roleId?: number;
  /** 所属角色名称 */
  roleName?: string;
  /** 创建时间 */
  createdAt?: string;
  /** 更新时间 */
  updatedAt?: string;
}

/** 成员列表查询参数 */
export interface MemberListParams {
  /** 搜索关键词（用户名/昵称/邮箱） */
  search?: string;
  /** 页码 */
  page?: number;
  /** 每页数量 */
  pageSize?: number;
  /** 是否包含子节点成员（递归查询），默认 true */
  includeDescendants?: boolean;
}

/** 成员列表分页响应（后端原始格式） */
export interface MemberListResponseRaw {
  items: OrgMemberRaw[];
  total: number;
  page: number;
  page_size: number;
}

/** 成员列表分页响应（前端格式） */
export interface MemberListResponse {
  items: OrgMember[];
  total: number;
  page: number;
  pageSize: number;
}

/** 添加成员请求 */
export interface AddMemberRequest {
  admin_id: number;
}

/** 设置负责人请求 */
export interface SetLeaderRequest {
  leader_id: null | number;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端节点数据转换为前端格式 */
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

/** 将后端成员数据转换为前端格式 */
function transformOrgMember(raw: OrgMemberRaw): OrgMember {
  return {
    id: raw.id,
    username: raw.username,
    realName: raw.real_name,
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
// API 接口
// ============================================================

const API_PREFIX = '/admin/roles';

/**
 * 获取组织架构根节点
 * GET /admin/roles/organization
 * 返回 level=1 的根节点列表，包含 has_children 标记
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
 * 获取子节点（按需加载）
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
 * 获取节点成员列表（分页 + 搜索）
 * GET /admin/roles/{role_id}/members
 * @param roleId - 节点 ID
 * @param params - 查询参数（搜索、分页）
 * @param options - 请求选项
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
  // 递归查询子节点成员，默认 true
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
 * 添加成员到节点
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
 * 从节点移除成员
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
 * 设置节点负责人
 * PUT /admin/roles/{role_id}/leader
 * @param roleId - 节点 ID
 * @param leaderId - 负责人 ID，传 null 表示取消负责人
 * @param options - 请求选项
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
