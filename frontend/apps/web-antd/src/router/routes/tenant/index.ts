/**
 * 租户管理端路由模块
 */
import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const AuthPageLayout = () => import('#/layouts/auth.vue');
const BasicLayout = () => import('#/layouts/basic.vue');

/** 租户管理端认证路由 */
const authRoutes: RouteRecordRaw = {
  component: AuthPageLayout,
  meta: {
    hideInTab: true,
    title: $t('page.tenant.authentication'),
  },
  name: 'TenantAuthentication',
  path: '/tenant/auth',
  redirect: '/tenant/login',
  children: [
    {
      name: 'TenantLogin',
      path: '/tenant/login',
      component: () => import('#/views/tenant/authentication/login.vue'),
      meta: {
        title: $t('page.auth.login'),
      },
    },
    {
      name: 'TenantImpersonate',
      path: '/tenant/impersonate',
      component: () => import('#/views/tenant/authentication/impersonate.vue'),
      meta: {
        title: $t('page.auth.impersonate'),
      },
    },
  ],
};

/** 租户管理端主布局路由 */
const mainRoutes: RouteRecordRaw = {
  component: BasicLayout,
  meta: {
    hideInBreadcrumb: true,
    title: $t('page.tenant.root'),
  },
  name: 'TenantRoot',
  path: '/tenant',
  redirect: '/tenant/dashboard',
  children: [
    {
      name: 'TenantDashboard',
      path: 'dashboard',
      component: () => import('#/views/tenant/dashboard/index.vue'),
      meta: {
        affixTab: true,
        icon: 'lucide:layout-dashboard',
        title: $t('page.dashboard.title'),
      },
    },
    // Fallback 静态注册：系统配置（后端菜单动态路由优先生效）
    {
      name: 'TenantSystemConfigs',
      path: 'system/configs',
      component: () => import('#/views/tenant/system/configs/list.vue'),
      meta: {
        hideInMenu: true,
        icon: 'lucide:settings',
        title: $t('tenant.system.configs.title'),
      },
    },
    // Fallback 静态注册：附件管理（后端菜单动态路由优先生效）
    {
      name: 'TenantSystemAttachments',
      path: 'system/attachments',
      component: () => import('#/views/tenant/system/attachments/index.vue'),
      meta: {
        hideInMenu: true,
        icon: 'lucide:paperclip',
        title: $t('tenant.system.attachment.title'),
      },
    },
    // Fallback 静态注册：任务日志
    {
      name: 'TenantSystemTaskLogs',
      path: 'system/task-logs',
      component: () => import('#/views/tenant/system/task-logs/index.vue'),
      meta: {
        hideInMenu: true,
        icon: 'lucide:scroll-text',
        title: $t('tenant.system.taskLog.title'),
      },
    },
    // Fallback 静态注册：定时任务
    {
      name: 'TenantSystemPeriodicTasks',
      path: 'system/periodic-tasks',
      component: () =>
        import('#/views/tenant/system/periodic-tasks/index.vue'),
      meta: {
        hideInMenu: true,
        icon: 'lucide:timer',
        title: $t('tenant.system.periodicTask.title'),
      },
    },
  ],
};

/** 租户管理端路由 */
export const tenantRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

export { tenantCoreRouteNames } from './names';
