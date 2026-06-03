/**
 * Platform organization management API / 平台组织架构管理 API
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export type OrgNodeType = 'department' | 'position';

export type OrgLeaderScopeType =
  | 'all'
  | 'custom'
  | 'dept_children'
  | 'dept_only'
  | 'self';

export interface LeaderInfo {
  id: number;
  username: string;
  nickname?: string;
  real_name?: string;
  avatar?: string;
}

export interface OrgScopeTargetRaw {
  id: number;
  name: string;
  type?: string;
}

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
  permission_ids?: number[];
  permission_codes?: string[];
  can_manage_member_ai?: boolean;
  data_scope?: null | OrgLeaderScopeType;
  custom_dept_ids?: null | number[];
  scope_target_count?: number;
  scope_targets?: OrgScopeTargetRaw[];
  created_at: string;
  updated_at?: string;
  children?: OrgNodeInfoRaw[];
}

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
  permissionIds?: number[];
  permissionCodes?: string[];
  canManageMemberAi?: boolean;
  dataScope?: null | OrgLeaderScopeType;
  customDeptIds?: null | number[];
  scopeTargetCount?: number;
  scopeTargets?: OrgScopeTargetRaw[];
  createdAt: string;
  updatedAt?: string;
  children?: OrgNodeInfo[];
  loading?: boolean;
}

export interface OrgMemberRaw {
  id: number;
  username: string;
  nickname?: string;
  email?: string;
  avatar?: string;
  ai_enabled?: boolean;
  effective_ai_enabled?: boolean;
  ai_unavailable_reason?: null | string;
  can_manage_ai?: boolean;
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

export interface OrgMember {
  id: number;
  username: string;
  nickname?: string;
  email?: string;
  avatar?: string;
  aiEnabled: boolean;
  effectiveAiEnabled: boolean;
  aiUnavailableReason?: null | string;
  canManageAi?: boolean;
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

export interface MemberListParams {
  search?: string;
  page?: number;
  pageSize?: number;
  includeDescendants?: boolean;
}

export interface MemberListResponseRaw {
  items: OrgMemberRaw[];
  total: number;
  page: number;
  page_size: number;
}

export interface MemberListResponse {
  items: OrgMember[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AddMemberRequest {
  admin_id: number;
}

export interface CreateMemberRequest {
  username: string;
  email: string;
  password: string;
  phone?: null | string;
  nickname?: null | string;
  is_active?: boolean;
  ai_enabled?: boolean;
  is_super?: boolean;
  org_node_id?: null | number;
}

export interface UpdateMemberRequest {
  email?: null | string;
  phone?: null | string;
  nickname?: null | string;
  avatar?: null | string;
  is_active?: boolean | null;
  ai_enabled?: boolean | null;
  is_super?: boolean | null;
  org_node_id?: null | number;
}

export interface ResetMemberPasswordRequest {
  new_password: string;
}

export interface MemberStatusRequest {
  is_active: boolean;
}

export interface SetLeaderRequest {
  leader_id: null | number;
}

export interface CreateOrganizationNodeRequest {
  name: string;
  description?: null | string;
  type?: OrgNodeType;
  parent_id?: null | number;
  allow_members?: boolean;
  is_active?: boolean;
  sort_order?: number;
  permission_ids?: null | number[];
  data_scope?: null | OrgLeaderScopeType;
  custom_dept_ids?: null | number[];
}

export interface UpdateOrganizationNodeRequest {
  name?: null | string;
  description?: null | string;
  type?: null | OrgNodeType;
  allow_members?: boolean | null;
  is_active?: boolean | null;
  sort_order?: null | number;
  leader_id?: null | number;
  permission_ids?: null | number[];
  data_scope?: null | OrgLeaderScopeType;
  custom_dept_ids?: null | number[];
}

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
    permissionIds: raw.permission_ids,
    permissionCodes: raw.permission_codes,
    canManageMemberAi: raw.can_manage_member_ai,
    dataScope: raw.data_scope,
    customDeptIds: raw.custom_dept_ids,
    scopeTargetCount:
      raw.scope_target_count ?? raw.custom_dept_ids?.length ?? 0,
    scopeTargets: raw.scope_targets,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    children: raw.children?.map((child) =>
      transformOrgNode(child as OrgNodeInfoRaw),
    ),
  };
}

function transformOrgMember(raw: OrgMemberRaw): OrgMember {
  return {
    id: raw.id,
    username: raw.username,
    nickname: raw.nickname,
    email: raw.email,
    avatar: raw.avatar,
    aiEnabled: raw.ai_enabled ?? true,
    effectiveAiEnabled: raw.effective_ai_enabled ?? raw.ai_enabled ?? true,
    aiUnavailableReason: raw.ai_unavailable_reason ?? null,
    canManageAi: raw.can_manage_ai ?? false,
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

const API_PREFIX = '/admin/organization';

export async function getOrganizationRootNodesApi(
  options?: ApiRequestOptions,
): Promise<OrgNodeInfo[]> {
  const response = await requestClient.get<OrgNodeInfoRaw[]>(
    API_PREFIX,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

export async function getOrganizationTreeApi(
  options?: ApiRequestOptions,
): Promise<OrgNodeInfo[]> {
  const response = await requestClient.get<OrgNodeInfoRaw[]>(
    `${API_PREFIX}/tree`,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

export async function getOrganizationNodeDetailApi(
  nodeId: number,
  options?: ApiRequestOptions,
): Promise<OrgNodeInfo> {
  const response = await requestClient.get<OrgNodeInfoRaw>(
    `${API_PREFIX}/${nodeId}`,
    options,
  );
  return transformOrgNode(response);
}

export async function getNodeChildrenApi(
  orgNodeId: number,
  options?: ApiRequestOptions,
): Promise<OrgNodeInfo[]> {
  const response = await requestClient.get<OrgNodeInfoRaw[]>(
    `${API_PREFIX}/${orgNodeId}/children`,
    options,
  );
  return response.map((item) => transformOrgNode(item));
}

export async function createOrganizationNodeApi(
  data: CreateOrganizationNodeRequest,
  options?: ApiRequestOptions,
): Promise<OrgNodeInfo> {
  const response = await requestClient.post<OrgNodeInfoRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformOrgNode(response);
}

export async function updateOrganizationNodeApi(
  nodeId: number,
  data: UpdateOrganizationNodeRequest,
  options?: ApiRequestOptions,
): Promise<OrgNodeInfo> {
  const response = await requestClient.put<OrgNodeInfoRaw>(
    `${API_PREFIX}/${nodeId}`,
    data,
    options,
  );
  return transformOrgNode(response);
}

export async function deleteOrganizationNodeApi(
  nodeId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${nodeId}`, options);
}

export async function getNodeMembersApi(
  orgNodeId: number,
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
  if (params?.includeDescendants !== undefined) {
    queryParams.include_descendants = params.includeDescendants;
  }

  const response = await requestClient.get<MemberListResponseRaw>(
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

export async function addMemberToNodeApi(
  orgNodeId: number,
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `${API_PREFIX}/${orgNodeId}/members`,
    { admin_id: adminId } as AddMemberRequest,
    options,
  );
}

export async function createMemberApi(
  orgNodeId: number,
  data: CreateMemberRequest,
  options?: ApiRequestOptions,
): Promise<OrgMember> {
  const raw = await requestClient.post<OrgMemberRaw>(
    `${API_PREFIX}/${orgNodeId}/members/create`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

export async function updateMemberApi(
  orgNodeId: number,
  adminId: number,
  data: UpdateMemberRequest,
  options?: ApiRequestOptions,
): Promise<OrgMember> {
  const raw = await requestClient.put<OrgMemberRaw>(
    `${API_PREFIX}/${orgNodeId}/members/${adminId}`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

export async function resetMemberPasswordApi(
  orgNodeId: number,
  adminId: number,
  data: ResetMemberPasswordRequest,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${orgNodeId}/members/${adminId}/reset-password`,
    data,
    options,
  );
}

export async function toggleMemberStatusApi(
  orgNodeId: number,
  adminId: number,
  data: MemberStatusRequest,
  options?: ApiRequestOptions,
): Promise<OrgMember> {
  const raw = await requestClient.put<OrgMemberRaw>(
    `${API_PREFIX}/${orgNodeId}/members/${adminId}/status`,
    data,
    options,
  );
  return transformOrgMember(raw);
}

export async function removeMemberFromNodeApi(
  orgNodeId: number,
  adminId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${API_PREFIX}/${orgNodeId}/members/${adminId}`,
    options,
  );
}

export async function setNodeLeaderApi(
  orgNodeId: number,
  leaderId: null | number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `${API_PREFIX}/${orgNodeId}/leader`,
    { leader_id: leaderId } as SetLeaderRequest,
    options,
  );
}
