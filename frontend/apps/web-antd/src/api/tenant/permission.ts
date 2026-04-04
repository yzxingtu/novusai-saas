/**
 * Tenant permission management API / 企业权限管理 API
 * Backend: /tenant/permissions/* / 对接后端 /tenant/permissions/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Permission type / 权限类型 */
export type TenantPermissionType = 'api' | 'button' | 'menu' | 'operation';

/** Permission node (tree structure, backend raw format) / 权限节点（后端原始格式） */
export interface TenantPermissionNodeRaw {
  id: number;
  code: string;
  name: string;
  type: TenantPermissionType;
  parent_id: null | number;
  sort_order: number;
  /** Icon (Iconify format, e.g. lucide:gauge) / 图标 */
  icon?: null | string;
  children?: TenantPermissionNodeRaw[];
}

/** Permission node (tree structure, frontend format) / 权限节点（前端格式） */
export interface TenantPermissionNode {
  id: number;
  code: string;
  name: string;
  type: TenantPermissionType;
  parentId: null | number;
  sortOrder: number;
  /** Icon (Iconify format, e.g. lucide:gauge) / 图标 */
  icon?: null | string;
  children?: TenantPermissionNode[];
}

/** Permission item (flat list, backend raw format) / 权限项（后端原始格式） */
export interface TenantPermissionItemRaw {
  id: number;
  code: string;
  name: string;
  type: TenantPermissionType;
  parent_id: null | number;
}

/** Permission item (flat list, frontend format) / 权限项（前端格式） */
export interface TenantPermissionItem {
  id: number;
  code: string;
  name: string;
  type: TenantPermissionType;
  parentId: null | number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Recursively transform permission tree node / 递归转换权限树节点 */
function transformPermissionNode(
  raw: TenantPermissionNodeRaw,
): TenantPermissionNode {
  return {
    id: raw.id,
    code: raw.code,
    name: raw.name,
    type: raw.type,
    parentId: raw.parent_id,
    sortOrder: raw.sort_order,
    icon: raw.icon,
    children: raw.children?.map((item) => transformPermissionNode(item)),
  };
}

/** Transform permission item / 转换权限项 */
function transformPermissionItem(
  raw: TenantPermissionItemRaw,
): TenantPermissionItem {
  return {
    id: raw.id,
    code: raw.code,
    name: raw.name,
    type: raw.type,
    parentId: raw.parent_id,
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/tenant/permissions';

/**
 * Get permission tree / 获取权限树
 * GET /tenant/permissions
 * Returns tree structure for role permission configuration / 返回树形结构，用于角色权限配置
 */
export async function getTenantPermissionTreeApi(
  options?: ApiRequestOptions,
): Promise<TenantPermissionNode[]> {
  const response = await requestClient.get<TenantPermissionNodeRaw[]>(
    API_PREFIX,
    options,
  );
  return response.map((item) => transformPermissionNode(item));
}

/**
 * Get permission list / 获取权限列表
 * GET /tenant/permissions/list
 */
export async function getTenantPermissionListApi(
  options?: ApiRequestOptions,
): Promise<TenantPermissionItem[]> {
  const response = await requestClient.get<TenantPermissionItemRaw[]>(
    `${API_PREFIX}/list`,
    options,
  );
  return response.map((item) => transformPermissionItem(item));
}
