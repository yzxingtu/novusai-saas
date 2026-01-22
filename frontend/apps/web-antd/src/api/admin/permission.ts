/**
 * 平台权限管理 API
 * 对接后端 /admin/permissions/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 权限类型 */
export type PermissionType = 'api' | 'button' | 'menu';

/** 权限节点（树形结构，后端原始格式） */
export interface PermissionNodeRaw {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parent_id: null | number;
  sort_order: number;
  /** 图标（Iconify 格式，如 lucide:gauge） */
  icon?: null | string;
  children?: PermissionNodeRaw[];
}

/** 权限节点（树形结构，前端格式） */
export interface PermissionNode {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parentId: null | number;
  sortOrder: number;
  /** 图标（Iconify 格式，如 lucide:gauge） */
  icon?: null | string;
  children?: PermissionNode[];
}

/** 权限项（平铺列表，后端原始格式） */
export interface PermissionItemRaw {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parent_id: null | number;
}

/** 权限项（平铺列表，前端格式） */
export interface PermissionItem {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parentId: null | number;
}

// ============================================================
// 转换函数
// ============================================================

/** 递归转换权限树节点 */
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

/** 转换权限项 */
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
// API 接口
// ============================================================

const API_PREFIX = '/admin/permissions';

/**
 * 获取权限树
 * GET /admin/permissions
 * 返回树形结构，用于角色权限配置页面
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
 * 获取权限列表（平铺）
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
