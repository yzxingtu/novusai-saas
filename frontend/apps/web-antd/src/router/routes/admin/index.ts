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
    // Dashboard：固定标签页，必须静态注册
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
    // 技能包详情页：带 :id 动态参数 + activePath，后端不注册此路由
    {
      name: 'AdminAISkillPackageDetail',
      path: 'ai/skill-packages/:id',
      component: () =>
        import('#/views/admin/ai/skill-packages/detail.vue'),
      meta: {
        hideInMenu: true,
        title: $t('admin.ai.skillPackage.detail.title'),
        activePath: '/admin/ai/skill-packages',
      },
    },
    // 插件市场页：后端不注册此路由
    {
      name: 'AdminPluginMarketplace',
      path: 'plugins/marketplace',
      component: () => import('#/views/admin/plugins/marketplace/index.vue'),
      meta: {
        hideInMenu: true,
        title: $t('admin.plugin.marketplace.title'),
        activePath: '/admin/plugins',
      },
    },
    // 插件详情改为抽屉形式，不再需要独立路由
    // 个人中心：不在后端菜单中，必须静态注册
    {
      name: 'Profile',
      path: '/admin/profile',
      component: () => import('#/views/admin/profile/index.vue'),
      meta: {
        hideInMenu: true,
        title: $t('page.auth.profile'),
      },
    },
  ],
};

/** 平台管理端路由 */
export const adminRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

/** 平台管理端路由名称列表（不需要权限拦截） */
export const adminCoreRouteNames = ['AdminAuthentication', 'AdminLogin'];
