/**
 * 用户端路由模块
 */
import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const UserLayout = () => import('#/layouts/user.vue');

/** 用户端主布局路由 */
const mainRoutes: RouteRecordRaw = {
  component: UserLayout,
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
    {
      name: 'UserProfile',
      path: 'profile',
      component: () => import('#/views/user/profile/index.vue'),
      meta: {
        icon: 'lucide:user',
        title: $t('user.profile.title'),
      },
    },
    {
      name: 'UserChangePassword',
      path: 'profile/change-password',
      component: () => import('#/views/user/profile/change-password.vue'),
      meta: {
        hideInMenu: true,
        title: $t('user.profile.changePassword'),
      },
    },
  ],
};

/** 用户端路由 */
export const userRoutes: RouteRecordRaw[] = [mainRoutes];

/** 用户端路由名称列表（不需要权限拦截） */
export const userCoreRouteNames: string[] = [];
