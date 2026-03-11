/**
 * Tenant user menu API / 租户用户端菜单 API
 * Backend: /api/user/permissions/menus / 对接后端 /api/user/permissions/menus 接口
 */
import type { RouteRecordStringComponent } from '@vben/types';

import type { BackendMenuItemRaw } from '../shared/menu-transformer';

import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

import {
  extractPermissionsFromMenus,
  needsTransform,
  transformMenuData,
} from '../shared/menu-transformer';

/** Menus with permissions result / 菜单和权限码的返回结果 */
export interface MenusWithPermissions {
  menus: RouteRecordStringComponent[];
  permissions: string[];
}

/**
 * Get current user menus with permissions / 获取当前用户菜单列表（含权限码）
 * Filtered by role permissions, used for dynamic menu rendering / 根据角色权限过滤，用于前端动态渲染菜单
 * Auto-converts backend snake_case to frontend camelCase / 自动处理后端 snake_case 到前端 camelCase 的转换
 * @returns Menus and permission codes / 菜单列表和权限码
 */
export async function getUserMenusWithPermissionsApi(
  options?: ApiRequestOptions,
): Promise<MenusWithPermissions> {
  const rawMenus = await requestClient.get<BackendMenuItemRaw[]>(
    '/api/user/permissions/menus',
    options,
  );

  // Extract permission codes / 提取权限码
  const permissions = extractPermissionsFromMenus(rawMenus);

  // Transform menu format / 转换菜单格式
  const menus = needsTransform(rawMenus)
    ? transformMenuData(rawMenus, 'user')
    : (rawMenus as unknown as RouteRecordStringComponent[]);

  return { menus, permissions };
}

/**
 * Get current user menus / 获取当前用户菜单列表
 * @deprecated Use getUserMenusWithPermissionsApi to get permissions too / 请使用 getUserMenusWithPermissionsApi 以同时获取权限码
 */
export async function getUserMenusApi(
  options?: ApiRequestOptions,
): Promise<RouteRecordStringComponent[]> {
  const { menus } = await getUserMenusWithPermissionsApi(options);
  return menus;
}
