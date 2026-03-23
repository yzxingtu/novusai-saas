/**
 * Tenant permission role management API / 企业权限角色管理 API
 * Backend: /tenant/permission-roles/*
 */
import type { SelectOption, SelectResponse } from '#/types';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export interface TenantPermissionRoleInfoRaw {
  id: number;
  tenant_id: number;
  name: string;
  code: string;
  description?: null | string;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  permissions_count: number;
  member_count: number;
  created_at: string;
  updated_at?: null | string;
}

export interface TenantPermissionRoleDetailRaw
  extends TenantPermissionRoleInfoRaw {
  permission_ids: number[];
  permission_codes: string[];
}

export interface TenantPermissionRoleInfo {
  id: number;
  tenantId: number;
  name: string;
  code: string;
  description?: null | string;
  isSystem: boolean;
  isActive: boolean;
  sortOrder: number;
  permissionsCount: number;
  memberCount: number;
  createdAt: string;
  updatedAt?: null | string;
}

export interface TenantPermissionRoleSummary {
  code: string;
  id: number;
  name: string;
  type: string;
}

export interface TenantPermissionRoleDetail extends TenantPermissionRoleInfo {
  permissionIds: number[];
  permissionCodes: string[];
  permissions: TenantPermissionRoleSummary[];
}

export interface TenantRoleCreateRequest {
  name: string;
  code?: null | string;
  description?: null | string;
  is_active?: boolean;
  sort_order?: number;
  permission_ids?: number[];
}

export interface TenantRoleUpdateRequest {
  name?: null | string;
  code?: null | string;
  description?: null | string;
  is_active?: boolean | null;
  sort_order?: null | number;
  permission_ids?: null | number[];
}

export interface TenantRolePermissionsRequest {
  permission_ids: number[];
}

export interface TenantPermissionRoleListResponse {
  items: TenantPermissionRoleInfo[];
  total: number;
  page: number;
  pageSize: number;
}

const API_PREFIX = '/tenant/permission-roles';

function transformTenantPermissionRoleInfo(
  raw: TenantPermissionRoleInfoRaw,
): TenantPermissionRoleInfo {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    name: raw.name,
    code: raw.code,
    description: raw.description,
    isSystem: raw.is_system,
    isActive: raw.is_active,
    sortOrder: raw.sort_order,
    permissionsCount: raw.permissions_count,
    memberCount: raw.member_count,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function transformTenantPermissionRoleDetail(
  raw: TenantPermissionRoleDetailRaw,
): TenantPermissionRoleDetail {
  return {
    ...transformTenantPermissionRoleInfo(raw),
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

export async function getTenantPermissionRoleListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantPermissionRoleListResponse> {
  const response = await requestClient.get<{
    items: TenantPermissionRoleInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map(transformTenantPermissionRoleInfo),
    total: response.total,
    page: response.page,
    pageSize: response.page_size,
  };
}

export async function getTenantRoleListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<TenantPermissionRoleListResponse> {
  return getTenantPermissionRoleListApi(params, options);
}

export async function getTenantPermissionRoleDetailApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<TenantPermissionRoleDetail> {
  const response = await requestClient.get<TenantPermissionRoleDetailRaw>(
    `${API_PREFIX}/${roleId}`,
    options,
  );
  return transformTenantPermissionRoleDetail(response);
}

export async function getTenantRoleDetailApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<TenantPermissionRoleDetail> {
  return getTenantPermissionRoleDetailApi(roleId, options);
}

export async function createTenantRoleApi(
  data: TenantRoleCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantPermissionRoleDetail> {
  const response = await requestClient.post<TenantPermissionRoleDetailRaw>(
    API_PREFIX,
    data,
    options,
  );
  return transformTenantPermissionRoleDetail(response);
}

export async function updateTenantRoleApi(
  roleId: number,
  data: TenantRoleUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantPermissionRoleDetail> {
  const response = await requestClient.put<TenantPermissionRoleDetailRaw>(
    `${API_PREFIX}/${roleId}`,
    data,
    options,
  );
  return transformTenantPermissionRoleDetail(response);
}

export async function assignTenantRolePermissionsApi(
  roleId: number,
  data: TenantRolePermissionsRequest,
  options?: ApiRequestOptions,
): Promise<TenantPermissionRoleDetail> {
  const response = await requestClient.put<TenantPermissionRoleDetailRaw>(
    `${API_PREFIX}/${roleId}/permissions`,
    data,
    options,
  );
  return transformTenantPermissionRoleDetail(response);
}

export async function deleteTenantRoleApi(
  roleId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${API_PREFIX}/${roleId}`, options);
}

export async function getAllTenantPermissionRoleListApi(
  options?: ApiRequestOptions,
): Promise<TenantPermissionRoleInfo[]> {
  const pageSize = 100;
  let page = 1;
  const items: TenantPermissionRoleInfo[] = [];

  while (true) {
    const response = await getTenantPermissionRoleListApi(
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

export async function getTenantRoleSelectApi(
  _params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<SelectResponse> {
  const roles = await getAllTenantPermissionRoleListApi(options);
  const items: SelectOption[] = roles.map((role) => ({
    label: role.name,
    value: role.id,
  }));
  return { items };
}
