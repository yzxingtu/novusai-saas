/**
 * Tenant backend menu API / 租户后台菜单 API
 * Backend: /tenant/permissions/menus / 对接后端 /tenant/permissions/menus 接口
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

/** Menus with permission codes response / 菜单和权限码的返回结果 */
export interface MenusWithPermissions {
  menus: RouteRecordStringComponent[];
  permissions: string[];
}

/**
 * Get current tenant admin menu list (with permission codes) / 获取当前租户管理员菜单列表（含权限码）
 * Filtered by role permissions, used for frontend dynamic menu rendering / 根据角色权限过滤，用于前端动态渲染菜单
 * Auto-converts backend snake_case to frontend camelCase / 自动处理格式转换
 * @returns Menu list and permission codes / 菜单列表和权限码
 */
export async function getTenantMenusWithPermissionsApi(
  options?: ApiRequestOptions,
): Promise<MenusWithPermissions> {
  const rawMenus = await requestClient.get<BackendMenuItemRaw[]>(
    '/tenant/permissions/menus',
    options,
  );

  // Extract permission codes / 提取权限码
  const permissions = extractPermissionsFromMenus(rawMenus);

  // Transform menu format / 转换菜单格式
  const menus = needsTransform(rawMenus)
    ? transformMenuData(rawMenus, 'tenant')
    : (rawMenus as unknown as RouteRecordStringComponent[]);

  return { menus, permissions };
}

/**
 * Get current tenant admin menu list / 获取当前租户管理员菜单列表
 * @deprecated Use getTenantMenusWithPermissionsApi to get permission codes as well / 请使用 getTenantMenusWithPermissionsApi
 */
export async function getTenantMenusApi(
  options?: ApiRequestOptions,
): Promise<RouteRecordStringComponent[]> {
  const { menus } = await getTenantMenusWithPermissionsApi(options);
  return menus;
}
