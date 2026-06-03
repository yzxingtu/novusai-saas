/**
 * Platform admin menu API / 平台管理端菜单 API
 * Backend: /admin/permissions/menus
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

/** Menus and permission codes result / 菜单和权限码的返回结果 */
export interface MenusWithPermissions {
  menus: RouteRecordStringComponent[];
  permissions: string[];
}

/**
 * Get current admin menus (with permission codes)
 * 获取当前管理员菜单列表（含权限码）
 *
 * Filtered by role permissions, used for frontend dynamic menu rendering.
 * Auto-converts backend snake_case to frontend camelCase.
 * @returns Menus and permission codes / 菜单列表和权限码
 */
export async function getAdminMenusWithPermissionsApi(
  options?: ApiRequestOptions,
): Promise<MenusWithPermissions> {
  const rawMenus = await requestClient.get<BackendMenuItemRaw[]>(
    '/admin/permissions/menus',
    options,
  );

  // Extract permission codes / 提取权限码
  const permissions = extractPermissionsFromMenus(rawMenus);

  // Transform menu format / 转换菜单格式
  const menus = needsTransform(rawMenus)
    ? transformMenuData(rawMenus, 'admin')
    : (rawMenus as unknown as RouteRecordStringComponent[]);

  return { menus, permissions };
}
