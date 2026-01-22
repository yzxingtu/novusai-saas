/**
 * 租户权限管理 API
 * 对接后端 /tenant/permissions/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 权限类型 */
export type TenantPermissionType = 'api' | 'button' | 'menu';

/** 权限节点（树形结构，后端原始格式） */
export interface TenantPermissionNodeRaw {
  id: number;
  code: string;
  name: string;
  type: TenantPermissionType;
  parent_id: null | number;
  sort_order: number;
  /** 图标（Iconify 格式，如 lucide:gauge） */
  icon?: null | string;
  children?: TenantPermissionNodeRaw[];
}

/** 权限节点（树形结构，前端格式） */
export interface TenantPermissionNode {
  id: number;
  code: string;
  name: string;
  type: TenantPermissionType;
  parentId: null | number;
  sortOrder: number;
  /** 图标（Iconify 格式，如 lucide:gauge） */
  icon?: null | string;
  children?: TenantPermissionNode[];
}

/** 权限项（平铺列表，后端原始格式） */
export interface TenantPermissionItemRaw {
  id: number;
  code: string;
  name: string;
  type: TenantPermissionType;
  parent_id: null | number;
}

/** 权限项（平铺列表，前端格式） */
export interface TenantPermissionItem {
  id: number;
  code: string;
  name: string;
  type: TenantPermissionType;
  parentId: null | number;
}

// ============================================================
// 转换函数
// ============================================================

/** 递归转换权限树节点 */
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

/** 转换权限项 */
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
// API 接口
// ============================================================

const API_PREFIX = '/tenant/permissions';

/**
 * 获取权限树
 * GET /tenant/permissions
 * 返回树形结构，用于角色权限配置页面
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
 * 获取权限列表
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
