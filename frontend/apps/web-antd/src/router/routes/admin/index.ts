/**
 * 平台管理端路由模块
 */
import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const AuthPageLayout = () => import('#/layouts/auth.vue');
const BasicLayout = () => import('#/layouts/basic.vue');

/** 平台管理端认证路由 */
const authRoutes: RouteRecordRaw = {
  component: AuthPageLayout,
  meta: {
    hideInTab: true,
    title: 'Admin Authentication',
  },
  name: 'AdminAuthentication',
  path: '/admin/auth',
  redirect: '/admin/login',
  children: [
    {
      name: 'AdminLogin',
      path: '/admin/login',
      component: () => import('#/views/admin/authentication/login.vue'),
      meta: {
        title: $t('page.auth.login'),
      },
    },
  ],
};

/** 平台管理端主布局路由 */
const mainRoutes: RouteRecordRaw = {
  component: BasicLayout,
  meta: {
    hideInBreadcrumb: true,
    title: 'Admin Root',
  },
  name: 'AdminRoot',
  path: '/admin',
  redirect: '/admin/dashboard',
  children: [
    {
      name: 'AdminDashboard',
      path: 'dashboard',
      component: () => import('#/views/admin/dashboard/index.vue'),
      meta: {
        affixTab: true,
        icon: 'lucide:layout-dashboard',
        title: $t('page.dashboard.title'),
      },
    },
    // Fallback 静态注册：系统配置（后端菜单动态路由优先生效）
    {
      name: 'AdminSystemConfigs',
      path: 'system/configs',
      component: () => import('#/views/admin/system/configs/list.vue'),
      meta: {
        hideInMenu: true,
        icon: 'lucide:settings',
        title: $t('admin.system.configs.title'),
      },
    },
  ],
};

/** 平台管理端路由 */
export const adminRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

/** 平台管理端路由名称列表（不需要权限拦截） */
export const adminCoreRouteNames = ['AdminAuthentication', 'AdminLogin'];
