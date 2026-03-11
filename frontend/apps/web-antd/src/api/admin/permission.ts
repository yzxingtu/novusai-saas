/**
 * Platform permission management API / 平台权限管理 API
 * Backend: /admin/permissions/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Permission type / 权限类型 */
export type PermissionType = 'api' | 'button' | 'menu';

/** Permission node (tree, backend raw) / 权限节点（树形，后端原始） */
export interface PermissionNodeRaw {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parent_id: null | number;
  sort_order: number;
  /** Icon (Iconify format, e.g. lucide:gauge) / 图标 */
  icon?: null | string;
  children?: PermissionNodeRaw[];
}

/** Permission node (tree, frontend) / 权限节点（树形，前端） */
export interface PermissionNode {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parentId: null | number;
  sortOrder: number;
  /** Icon (Iconify format, e.g. lucide:gauge) / 图标 */
  icon?: null | string;
  children?: PermissionNode[];
}

/** Permission item (flat list, backend raw) / 权限项（平铺，后端原始） */
export interface PermissionItemRaw {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parent_id: null | number;
}

/** Permission item (flat list, frontend) / 权限项（平铺，前端） */
export interface PermissionItem {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parentId: null | number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Recursively transform permission tree node / 递归转换权限树节点 */
function transformPermissionNode(raw: PermissionNodeRaw): PermissionNode {
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
function transformPermissionItem(raw: PermissionItemRaw): PermissionItem {
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

const API_PREFIX = '/admin/permissions';

/**
 * Get permission tree / 获取权限树
 * GET /admin/permissions
 * Returns tree structure for role permission config page
 */
export async function getPermissionTreeApi(
  options?: ApiRequestOptions,
): Promise<PermissionNode[]> {
  const response = await requestClient.get<PermissionNodeRaw[]>(
    API_PREFIX,
    options,
  );
  return response.map((item) => transformPermissionNode(item));
}

/**
 * Get permission list (flat) / 获取权限列表（平铺）
 * GET /admin/permissions/list
 */
export async function getPermissionListApi(
  options?: ApiRequestOptions,
): Promise<PermissionItem[]> {
  const response = await requestClient.get<PermissionItemRaw[]>(
    `${API_PREFIX}/list`,
    options,
  );
  return response.map((item) => transformPermissionItem(item));
}
