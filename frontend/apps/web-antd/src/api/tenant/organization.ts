/**
 * Tenant organization management API / 企业组织架构管理 API
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export type TenantOrgNodeType = 'department' | 'position';

export type TenantLeaderScopeType =
  | 'all'
  | 'custom'
  | 'dept_children'
  | 'dept_only'
  | 'self';

export interface TenantLeaderInfo {
  id: number;
  username: string;
  nickname?: string;
  real_name?: string;
  avatar?: string;
}

export interface TenantOrgScopeTargetRaw {
  id: number;
  name: string;
  type?: string;
}

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
  permission_ids?: number[];
  permission_codes?: string[];
  can_assign_permissions?: boolean;
  data_scope?: null | TenantLeaderScopeType;
  custom_dept_ids?: null | number[];
  scope_target_count?: number;
  scope_targets?: TenantOrgScopeTargetRaw[];
  created_at: string;
  updated_at?: string;
  children?: TenantOrgNodeInfoRaw[];
}

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
  permissionIds?: number[];
  permissionCodes?: string[];
  canAssignPermissions?: boolean;
  dataScope?: null | TenantLeaderScopeType;
  customDeptIds?: null | number[];
  scopeTargetCount?: number;
  scopeTargets?: TenantOrgScopeTargetRaw[];
  createdAt: string;
  updatedAt?: string;
  children?: TenantOrgNodeInfo[];
  loading?: boolean;
}

export interface TenantOrgMemberRaw {
  id: number;
  username: string;
  nickname?: string;
  email?: string;
  avatar?: string;
  ai_enabled?: boolean;
  is_active: boolean;
  is_leader: boolean;
  joined_at: string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  permission_role_id?: null | number;
  permission_role_name?: null | string;
  role_id?: null | number;
  role_name?: null | string;
  created_at?: string;
  updated_at?: string;
}

export interface TenantOrgMember {
  id: number;
  username: string;
  nickname?: string;
  email?: string;
  avatar?: string;
  aiEnabled: boolean;
  isActive: boolean;
  isLeader: boolean;
  joinedAt: string;
  orgNodeId?: null | number;
  orgNodeName?: null | string;
  roleId?: null | number;
  roleName?: null | string;
  createdAt?: string;
  updatedAt?: string;
}

export interface TenantMemberListParams {
  search?: string;
  page?: number;
  pageSize?: number;
  includeDescendants?: boolean;
}

export interface TenantMemberListResponseRaw {
  items: TenantOrgMemberRaw[];
  total: number;
  page: number;
  page_size: number;
}

export interface TenantMemberListResponse {
  items: TenantOrgMember[];
  total: number;
  page: number;
  pageSize: number;
}

export interface TenantAddMemberRequest {
  admin_id: number;
}

export interface TenantCreateMemberRequest {
  username: string;
  email: string;
  password: string;
  phone?: null | string;
  nickname?: null | string;
  is_active?: boolean;
  ai_enabled?: boolean;
  is_super?: boolean;
  org_node_id?: null | number;
  role_id?: null | number;
}

export interface TenantUpdateMemberRequest {
  email?: null | string;
  phone?: null | string;
  nickname?: null | string;
  avatar?: null | string;
  is_active?: boolean | null;
  ai_enabled?: boolean | null;
  is_super?: boolean | null;
  org_node_id?: null | number;
  role_id?: null | number;
}

export interface TenantResetMemberPasswordRequest {
  new_password: string;
}

export interface TenantMemberStatusRequest {
  is_active: boolean;
}

export interface TenantSetLeaderRequest {
  leader_id: null | number;
}

export interface CreateTenantOrganizationNodeRequest {
  name: string;
  description?: null | string;
  type?: TenantOrgNodeType;
  parent_id?: null | number;
  allow_members?: boolean;
  is_active?: boolean;
  sort_order?: number;
  permission_ids?: null | number[];
  data_scope?: null | TenantLeaderScopeType;
  custom_dept_ids?: null | number[];
}

export interface UpdateTenantOrganizationNodeRequest {
  name?: null | string;
  description?: null | string;
  type?: null | TenantOrgNodeType;
  allow_members?: boolean | null;
  is_active?: boolean | null;
  sort_order?: null | number;
  leader_id?: null | number;
  permission_ids?: null | number[];
  data_scope?: null | TenantLeaderScopeType;
  custom_dept_ids?: null | number[];
}

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
    permissionIds: raw.permission_ids,
    permissionCodes: raw.permission_codes,
    canAssignPermissions: raw.can_assign_permissions,
    dataScope: raw.data_scope,
    customDeptIds: raw.custom_dept_ids,
    scopeTargetCount:
      raw.scope_target_count ?? raw.custom_dept_ids?.length ?? 0,
    scopeTargets: raw.scope_targets,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    children: raw.children?.map((child) =>
      transformOrgNode(child as TenantOrgNodeInfoRaw),
    ),
  };
}

function transformOrgMember(raw: TenantOrgMemberRaw): TenantOrgMember {
  return {
    id: raw.id,
    username: raw.username,
    nickname: raw.nickname,
    email: raw.email,
    avatar: raw.avatar,
    aiEnabled: raw.ai_enabled ?? true,
    isActive: raw.is_active,
    isLeader: raw.is_leader,
    joinedAt: raw.joined_at,
    orgNodeId: raw.org_node_id ?? null,
    orgNodeName: raw.org_node_name ?? null,
    roleId: raw.permission_role_id ?? raw.role_id ?? null,
    roleName: raw.permission_role_name ?? raw.role_name ?? null,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

const API_PREFIX = '/tenant/organization';

export async function getTenantOrganizationRootNodesApi(
  options?: ApiRequestOptions,
): Promise<TenantOrgNodeInfo[]> {
  const response = await requestClient.get<TenantOrgNodeInfoRaw[]>(
    API_PREFIX,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

export async function getTenantOrganizationTreeApi(
  options?: ApiRequestOptions,
): Promise<TenantOrgNodeInfo[]> {
  const response = await requestClient.get<TenantOrgNodeInfoRaw[]>(
    `${API_PREFIX}/tree`,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

export async function getTenantOrganizationNodeDetailApi(
  nodeId: number,
  options?: ApiRequestOptions,
): Promise<TenantOrgNodeInfo> {
  const response = await requestClient.get<TenantOrgNodeInfoRaw>(
    `${API_PREFIX}/${nodeId}`,
    options,
  );
  return transformOrgNode(response);
}

export async function getTenantNodeChildrenApi(
  orgNodeId: number,
  options?: ApiRequestOptions,
): Promise<TenantOrgNodeInfo[]> {
  const response = await requestClient.get<TenantOrgNodeInfoRaw[]>(
    `${API_PREFIX}/${orgNodeId}/children`,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

export async function createTenantOrganizationNodeApi(
  data: CreateTenantOrganizationNodeRequest,
  options?: ApiRequestOptions,
): Promise<TenantOrgNodeInfo> {
  const response = await requestClient.post<TenantOrgNodeInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformOrgNode(response);
}

export async function updateTenantOrganizationNodeApi(
  nodeId: number,
  data: UpdateTenantOrganizationNodeRequest,
  options?: ApiRequestOptions,
): Promise<TenantOrgNodeInfo> {
  const response = await requestClient.put<TenantOrgNodeInfoRaw>(
    `${API_PREFIX}/${nodeId}`,
    data,
    options,
  );
  return transformOrgNode(response);
}

export async function deleteTenantOrganizationNodeApi(
  nodeId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${nodeId}`, options);
}

export async function getTenantNodeMembersApi(
  orgNodeId: number,
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
  if (params?.includeDescendants !== undefined) {
    queryParams.include_descendants = params.includeDescendants;
  }

  const response = await requestClient.get<TenantMemberListResponseRaw>(
    `${API_PREFIX}/${orgNodeId}/members`,
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

export async function addTenantMemberToNodeApi(
  orgNodeId: number,
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `${API_PREFIX}/${orgNodeId}/members`,
    { admin_id: adminId } as TenantAddMemberRequest,
    options,
  );
}

export async function createTenantMemberApi(
  orgNodeId: number,
  data: TenantCreateMemberRequest,
  options?: ApiRequestOptions,
): Promise<TenantOrgMember> {
  const raw = await requestClient.post<TenantOrgMemberRaw>(
    `${API_PREFIX}/${orgNodeId}/members/create`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

export async function updateTenantMemberApi(
  orgNodeId: number,
  adminId: number,
  data: TenantUpdateMemberRequest,
  options?: ApiRequestOptions,
): Promise<TenantOrgMember> {
  const raw = await requestClient.put<TenantOrgMemberRaw>(
    `${API_PREFIX}/${orgNodeId}/members/${adminId}`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

export async function resetTenantMemberPasswordApi(
  orgNodeId: number,
  adminId: number,
  data: TenantResetMemberPasswordRequest,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${orgNodeId}/members/${adminId}/reset-password`,
    data,
    options,
  );
}

export async function toggleTenantMemberStatusApi(
  orgNodeId: number,
  adminId: number,
  data: TenantMemberStatusRequest,
  options?: ApiRequestOptions,
): Promise<TenantOrgMember> {
  const raw = await requestClient.put<TenantOrgMemberRaw>(
    `${API_PREFIX}/${orgNodeId}/members/${adminId}/status`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

export async function removeTenantMemberFromNodeApi(
  orgNodeId: number,
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${API_PREFIX}/${orgNodeId}/members/${adminId}`,
    options,
  );
}

export async function setTenantNodeLeaderApi(
  orgNodeId: number,
  leaderId: null | number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${orgNodeId}/leader`,
    { leader_id: leaderId } as TenantSetLeaderRequest,
    options,
  );
}
