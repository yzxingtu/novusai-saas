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
  redirect: '/home',
  children: [
    {
      name: 'UserHome',
      path: 'home',
      component: () => import('#/views/user/home/index.vue'),
      meta: {
        affixTab: true,
        icon: 'lucide:home',
        ignoreAccess: true,
        title: $t('user.home.title'),
      },
    },
    {
      name: 'UserSettings',
      path: 'settings',
      component: () => import('#/views/user/settings/index.vue'),
      redirect: '/settings/profile',
      meta: {
        icon: 'lucide:settings',
        ignoreAccess: true,
        title: $t('menu.user.settings'),
      },
      children: [
        {
          name: 'UserProfile',
          path: 'profile',
          component: () => import('#/views/user/profile/index.vue'),
          meta: {
            icon: 'lucide:user',
            ignoreAccess: true,
            title: $t('user.profile.title'),
          },
        },
        {
          name: 'UserChangePassword',
          path: 'password',
          component: () =>
            import('#/views/user/profile/change-password.vue'),
          meta: {
            hideInMenu: true,
            ignoreAccess: true,
            title: $t('user.profile.changePassword'),
          },
        },
      ],
    },
  ],
};

/** 用户端路由 */
export const userRoutes: RouteRecordRaw[] = [mainRoutes];

/** 用户端路由名称列表（不需要权限拦截） */
export const userCoreRouteNames: string[] = [];
