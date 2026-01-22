/**
 * 用户端路由模块
 */
import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const AuthPageLayout = () => import('#/layouts/auth.vue');
const BasicLayout = () => import('#/layouts/basic.vue');

/** 用户端认证路由 */
const authRoutes: RouteRecordRaw = {
  component: AuthPageLayout,
  meta: {
    hideInTab: true,
    title: 'User Authentication',
  },
  name: 'UserAuthentication',
  path: '/auth',
  redirect: '/login',
  children: [
    {
      name: 'UserLogin',
      path: '/login',
      component: () => import('#/views/_core/authentication/login.vue'),
      meta: {
        title: $t('page.auth.login'),
      },
    },
    {
      name: 'UserRegister',
      path: '/register',
      component: () => import('#/views/_core/authentication/register.vue'),
      meta: {
        title: $t('page.auth.register'),
      },
    },
  ],
};

/** 用户端主布局路由 */
const mainRoutes: RouteRecordRaw = {
  component: BasicLayout,
  meta: {
    hideInBreadcrumb: true,
    title: 'User Root',
  },
  name: 'UserRoot',
  path: '/',
  redirect: '/dashboard',
  children: [
    {
      name: 'UserDashboard',
      path: 'dashboard',
      component: () => import('#/views/user/dashboard/index.vue'),
      meta: {
        affixTab: true,
        icon: 'lucide:layout-dashboard',
        title: $t('page.dashboard.title'),
      },
    },
  ],
};

/** 用户端路由 */
export const userRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

/** 用户端路由名称列表（不需要权限拦截） */
export const userCoreRouteNames = [
  'UserAuthentication',
  'UserLogin',
  'UserRegister',
];
