import type {
  ComponentRecordType,
  GenerateMenuAndRoutesOptions,
} from '@vben/types';

import type { RouteRecordRaw, Router } from 'vue-router';

import type { ApiEndpoint } from '#/api';

import { generateAccessible } from '@vben/access';
import { preferences } from '@vben/preferences';
import { useAccessStore } from '@vben/stores';

import { message } from 'ant-design-vue';

import {
  adminApi,
  setExistingComponents,
  tenantApi,
  userApi,
} from '#/api';
import { BasicLayout, IFrameView, UserLayout } from '#/layouts';
import { $t } from '#/locales';
import { adminRoutes } from '#/router/routes/admin';
import { getEndpointFromPath } from '#/utils';

const forbiddenComponent = () => import('#/views/_core/fallback/forbidden.vue');

const ADMIN_ROOT_PATH = '/admin';

/**
 * Normalize admin child route to absolute path for dedupe / 将管理端子路由规范为绝对路径以便去重
 */
function adminChildAbsolutePath(childPath: string): string {
  const p = (childPath || '').replace(/\/+/g, '/');
  if (p.startsWith('/')) {
    return p;
  }
  return `${ADMIN_ROOT_PATH}/${p}`.replace(/\/+/g, '/');
}

/**
 * After backend menu rebuilds AdminRoot, static-only children (e.g. codegen/new, :id/edit) are missing.
 * Re-add any child from the initial admin route definition whose absolute path is not already registered.
 * 后端菜单重建 AdminRoot 后，仅静态注册的子路由（如 codegen/new、:id/edit）会丢失；按绝对路径去重后补回。
 */
function mergeAdminStaticRoutesMissingFromBackend(router: Router) {
  const adminRootDef = adminRoutes.find((r) => r.name === 'AdminRoot');
  const staticChildren = adminRootDef?.children as RouteRecordRaw[] | undefined;
  if (!staticChildren?.length) {
    return;
  }

  const mounted = router.getRoutes().find((r) => r.name === 'AdminRoot');
  if (!mounted?.children?.length) {
    return;
  }

  const existingAbs = new Set(
    mounted.children.map((c) =>
      adminChildAbsolutePath((c.path as string) || ''),
    ),
  );

  for (const child of staticChildren) {
    const abs = adminChildAbsolutePath((child.path as string) || '');
    if (!existingAbs.has(abs)) {
      router.addRoute('AdminRoot', child);
      existingAbs.add(abs);
    }
  }
}

/**
 * Get menu API with permissions by endpoint type
 * 根据端类型获取对应的菜单 API（含权限码）
 */
function getMenuWithPermissionsApi(endpoint: ApiEndpoint) {
  switch (endpoint) {
    case 'admin': {
      return adminApi.getAdminMenusWithPermissionsApi;
    }
    case 'tenant': {
      return tenantApi.getTenantMenusWithPermissionsApi;
    }
    default: {
      return userApi.getUserMenusWithPermissionsApi;
    }
  }
}

/**
 * Generate routes and menus
 * 生成路由和菜单
 * @param options - Options / 选项
 * @param endpoint - Endpoint type (optional, auto-detected from current route if omitted) / 端类型（可选，不传则根据当前路由自动判断）
 */
async function generateAccess(
  options: GenerateMenuAndRoutesOptions,
  endpoint?: ApiEndpoint,
) {
  const pageMap: ComponentRecordType = import.meta.glob('../views/**/*.vue');
  const accessStore = useAccessStore();

  // 设置已存在的组件映射，用于检测缺失的菜单组件 / record existing view modules
  setExistingComponents(pageMap);

  const layoutMap: ComponentRecordType = {
    BasicLayout,
    IFrameView,
    UserLayout,
  };

  // 如果未指定端类型，尝试从当前路由获取 / infer endpoint from route
  const currentEndpoint = endpoint || getCurrentEndpoint();
  const menuApi = getMenuWithPermissionsApi(currentEndpoint);

  const result = await generateAccessible(preferences.app.accessMode, {
    ...options,
    fetchMenuListAsync: async () => {
      message.loading({
        content: `${$t('common.loadingMenu')}...`,
        duration: 1.5,
      });
      // 获取菜单和权限码
      const { menus, permissions } = await menuApi();
      // Merge with codes already set by fetchUserInfo (e.g. super admin `*`) / 与 fetchUserInfo 已写入的权限合并（如超管 `*`），避免被菜单提取列表覆盖丢失
      const prev = accessStore.accessCodes;
      const merged =
        prev.length > 0
          ? [...new Set([...prev, ...permissions])]
          : permissions;
      accessStore.setAccessCodes(merged);
      return menus;
    },
    // 可以指定没有权限跳转403页面 / forbidden route component
    forbiddenComponent,
    // 如果 route.meta.menuVisibleWithForbidden = true / keep menu visible when forbidden
    layoutMap,
    pageMap,
  });

  if (currentEndpoint === 'admin') {
    mergeAdminStaticRoutesMissingFromBackend(options.router);
  }

  return result;
}

/**
 * Get current endpoint type
 * Retrieved from window.location since router instance may not exist yet
 * 获取当前端类型
 * 从 window.location 获取，因为此时可能还没有路由实例
 */
function getCurrentEndpoint(): ApiEndpoint {
  const path = window.location.pathname;
  return getEndpointFromPath(path) as ApiEndpoint;
}

export { generateAccess, getCurrentEndpoint, getMenuWithPermissionsApi };
