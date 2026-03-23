/**
 * Platform permission role management API / 平台权限角色管理 API
 * Backend: /admin/permission-roles/*
 */
import type { SelectOption, SelectResponse } from '#/types';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export interface PermissionRoleInfoRaw {
  id: number;
  code: string;
  name: string;
  description?: null | string;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  permissions_count: number;
  created_at: string;
  updated_at?: null | string;
}

export interface PermissionRoleDetailRaw extends PermissionRoleInfoRaw {
  permission_ids: number[];
  permission_codes: string[];
}

export interface PermissionRoleInfo {
  id: number;
  code: string;
  name: string;
  description?: null | string;
  isSystem: boolean;
  isActive: boolean;
  sortOrder: number;
  permissionsCount: number;
  createdAt: string;
  updatedAt?: null | string;
}

export interface PermissionRoleSummary {
  code: string;
  id: number;
  name: string;
  type: string;
}

export interface PermissionRoleDetail extends PermissionRoleInfo {
  permissionIds: number[];
  permissionCodes: string[];
  permissions: PermissionRoleSummary[];
}

export interface RoleCreateRequest {
  name: string;
  code?: null | string;
  description?: null | string;
  is_active?: boolean;
  sort_order?: number;
  permission_ids?: number[];
}

export interface RoleUpdateRequest {
  name?: null | string;
  code?: null | string;
  description?: null | string;
  is_active?: boolean | null;
  sort_order?: null | number;
  permission_ids?: null | number[];
}

export interface RolePermissionsRequest {
  permission_ids: number[];
}

export interface PermissionRoleListResponse {
  items: PermissionRoleInfo[];
  total: number;
  page: number;
  pageSize: number;
}

const API_PREFIX = '/admin/permission-roles';

function transformPermissionRoleInfo(
  raw: PermissionRoleInfoRaw,
): PermissionRoleInfo {
  return {
    id: raw.id,
    code: raw.code,
    name: raw.name,
    description: raw.description,
    isSystem: raw.is_system,
    isActive: raw.is_active,
    sortOrder: raw.sort_order,
    permissionsCount: raw.permissions_count,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function transformPermissionRoleDetail(
  raw: PermissionRoleDetailRaw,
): PermissionRoleDetail {
  return {
    ...transformPermissionRoleInfo(raw),
    permissionIds: raw.permission_ids,
    permissionCodes: raw.permission_codes,
    permissions: raw.permission_ids.map((id, index) => ({
      id,
      code: raw.permission_codes[index] ?? String(id),
      name: raw.permission_codes[index] ?? String(id),
      type: 'operation',
    })),
  };
}

export async function getPermissionRoleListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PermissionRoleListResponse> {
  const response = await requestClient.get<{
    items: PermissionRoleInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map(transformPermissionRoleInfo),
    total: response.total,
    page: response.page,
    pageSize: response.page_size,
  };
}

export async function getRoleListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PermissionRoleListResponse> {
  return getPermissionRoleListApi(params, options);
}

export async function getPermissionRoleDetailApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<PermissionRoleDetail> {
  const response = await requestClient.get<PermissionRoleDetailRaw>(
    `${API_PREFIX}/${roleId}`,
    options,
  );
  return transformPermissionRoleDetail(response);
}

export async function getRoleDetailApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<PermissionRoleDetail> {
  return getPermissionRoleDetailApi(roleId, options);
}

export async function createRoleApi(
  data: RoleCreateRequest,
  options?: ApiRequestOptions,
): Promise<PermissionRoleDetail> {
  const response = await requestClient.post<PermissionRoleDetailRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformPermissionRoleDetail(response);
}

export async function updateRoleApi(
  roleId: number,
  data: RoleUpdateRequest,
  options?: ApiRequestOptions,
): Promise<PermissionRoleDetail> {
  const response = await requestClient.put<PermissionRoleDetailRaw>(
    `${API_PREFIX}/${roleId}`,
    data,
    options,
  );
  return transformPermissionRoleDetail(response);
}

export async function assignRolePermissionsApi(
  roleId: number,
  data: RolePermissionsRequest,
  options?: ApiRequestOptions,
): Promise<PermissionRoleDetail> {
  const response = await requestClient.put<PermissionRoleDetailRaw>(
    `${API_PREFIX}/${roleId}/permissions`,
    data,
    options,
  );
  return transformPermissionRoleDetail(response);
}

export async function deleteRoleApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${roleId}`, options);
}

export async function getAllPermissionRoleListApi(
  options?: ApiRequestOptions,
): Promise<PermissionRoleInfo[]> {
  const pageSize = 100;
  let page = 1;
  const items: PermissionRoleInfo[] = [];

  while (true) {
    const response = await getPermissionRoleListApi(
      {
        'page[number]': page,
        'page[size]': pageSize,
      },
      options,
    );
    items.push(...response.items);

    if (items.length >= response.total || response.items.length < pageSize) {
      break;
    }

    page += 1;
  }

  return items;
}

export async function getRoleSelectApi(
  _params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SelectResponse> {
  const roles = await getAllPermissionRoleListApi(options);
  const items: SelectOption[] = roles.map((role) => ({
    label: role.name,
    value: role.id,
  }));
  return { items };
}
