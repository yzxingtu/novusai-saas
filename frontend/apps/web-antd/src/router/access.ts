import type {
  ComponentRecordType,
  GenerateMenuAndRoutesOptions,
} from '@vben/types';

import type { ApiEndpoint } from '#/api';

import { generateAccessible } from '@vben/access';
import { preferences } from '@vben/preferences';
import { useAccessStore } from '@vben/stores';

import { message } from 'ant-design-vue';

import {
  adminApi,
  getApiEndpoint,
  setExistingComponents,
  tenantApi,
  userApi,
} from '#/api';
import { BasicLayout, IFrameView } from '#/layouts';
import { $t } from '#/locales';

const forbiddenComponent = () => import('#/views/_core/fallback/forbidden.vue');

/**
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
      // user 端暂时使用旧 API，返回空权限码
      return async () => {
        const menus = await userApi.getUserMenusApi();
        return { menus, permissions: [] as string[] };
      };
    }
  }
}

/**
 * 生成路由和菜单
 * @param options 选项
 * @param endpoint 端类型（可选，不传则根据当前路由自动判断）
 */
async function generateAccess(
  options: GenerateMenuAndRoutesOptions,
  endpoint?: ApiEndpoint,
) {
  const pageMap: ComponentRecordType = import.meta.glob('../views/**/*.vue');
  const accessStore = useAccessStore();

  // 设置已存在的组件映射，用于检测缺失的菜单组件
  setExistingComponents(pageMap);

  const layoutMap: ComponentRecordType = {
    BasicLayout,
    IFrameView,
  };

  // 如果未指定端类型，尝试从当前路由获取
  const currentEndpoint = endpoint || getCurrentEndpoint();
  const menuApi = getMenuWithPermissionsApi(currentEndpoint);

  return await generateAccessible(preferences.app.accessMode, {
    ...options,
    fetchMenuListAsync: async () => {
      message.loading({
        content: `${$t('common.loadingMenu')}...`,
        duration: 1.5,
      });
      // 获取菜单和权限码
      const { menus, permissions } = await menuApi();
      // 设置权限码到 accessStore
      accessStore.setAccessCodes(permissions);
      return menus;
    },
    // 可以指定没有权限跳转403页面
    forbiddenComponent,
    // 如果 route.meta.menuVisibleWithForbidden = true
    layoutMap,
    pageMap,
  });
}

/**
 * 获取当前端类型
 * 从 window.location 获取，因为此时可能还没有路由实例
 */
function getCurrentEndpoint(): ApiEndpoint {
  const path = window.location.pathname;
  return getApiEndpoint(path);
}

export { generateAccess, getCurrentEndpoint, getMenuWithPermissionsApi };
