import type {
  ComponentRecordType,
  GenerateMenuAndRoutesOptions,
  RouteRecordStringComponent,
} from '@vben/types';

import type { ApiEndpoint } from '#/api';
import type { BackendMenuItemRaw } from '#/api/shared/menu-transformer';

import { generateAccessible } from '@vben/access';
import { i18n } from '@vben/locales';
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
import { transformMenuData } from '#/api/shared/menu-transformer';
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

      // 加载插件前端菜单并合并
      const pluginMenus = await loadPluginMenus(currentEndpoint);

      return [...menus, ...pluginMenus];
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

/**
 * 加载已启用插件的前端菜单
 * 从后端获取插件前端配置，将 menus 转换为路由记录并过滤端类型
 */
async function loadPluginMenus(
  endpoint: ApiEndpoint,
): Promise<RouteRecordStringComponent[]> {
  try {
    const configs = await adminApi.getPluginFrontendConfigApi();
    const allMenus: BackendMenuItemRaw[] = [];

    for (const config of configs) {
      // 合并插件 i18n 资源（不区分 endpoint，所有语言都合并）
      mergePluginLocales(config.locales);

      if (config.endpoint !== endpoint) continue;

      for (const menu of config.menus) {
        // 将插件菜单的 component 路径重写为 plugins/{name}/ 前缀
        allMenus.push(
          rewritePluginMenuComponent(menu, config.plugin_name),
        );
      }
    }

    if (allMenus.length === 0) return [];
    return transformMenuData(allMenus, endpoint);
  } catch {
    // 插件菜单加载失败不阻塞核心菜单
    return [];
  }
}

/**
 * 合并插件 i18n 翻译资源到全局 i18n 实例
 * @param locales 插件 locale 数据 {"zh-CN": {...}, "en-US": {...}}
 */
function mergePluginLocales(
  locales: Record<string, Record<string, unknown>> | undefined,
): void {
  if (!locales) return;
  for (const [lang, messages] of Object.entries(locales)) {
    if (messages && typeof messages === 'object') {
      i18n.global.mergeLocaleMessage(lang, messages);
    }
  }
}

/**
 * 重写插件菜单项的 component 路径
 * 将相对路径（如 "index.vue"）转为 "/plugins/{name}/index" 格式
 */
function rewritePluginMenuComponent(
  menu: BackendMenuItemRaw,
  pluginName: string,
): BackendMenuItemRaw {
  const result = { ...menu };
  if (result.component) {
    // 去掉 .vue 后缀，加上 /plugins/{name}/ 前缀
    const comp = result.component.replace(/\.vue$/, '');
    result.component = `/plugins/${pluginName}/${comp}`;
  }
  if (result.children) {
    result.children = result.children.map((child) =>
      rewritePluginMenuComponent(child, pluginName),
    );
  }
  return result;
}

export { generateAccess, getCurrentEndpoint, getMenuWithPermissionsApi };
