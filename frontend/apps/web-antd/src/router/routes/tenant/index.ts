/**
 * Tenant management route module
 * 企业管理端路由模块
 */
import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const AuthPageLayout = () => import('#/layouts/tenant-auth.vue');
const BasicLayout = () => import('#/layouts/basic.vue');

/** Tenant authentication routes / 企业管理端认证路由 */
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

/** Tenant main layout routes / 企业管理端主布局路由 */
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
    // Dashboard：固定标签页，必须静态注册
    {
      name: 'TenantDashboard',
      path: 'dashboard',
      component: () => import('#/views/tenant/dashboard/index.vue'),
      meta: {
        affixTab: true,
        icon: 'lucide:layout-dashboard',
        title: $t('page.dashboard.title'),
        ai: { mode: 'context_only' as const },
      },
    },
    // Analytics：数据分析页面
    {
      name: 'TenantAnalytics',
      path: 'analytics',
      component: () => import('#/views/tenant/analytics/index.vue'),
      meta: {
        icon: 'lucide:bar-chart-3',
        title: $t('tenant.analytics.title'),
        ai: { mode: 'context_only' as const },
      },
    },
    // 智能体详情页
    {
      name: 'TenantAIAgentDetail',
      path: 'ai/agents/:id',
      component: () => import('#/views/tenant/ai/agents/detail.vue'),
      meta: {
        hideInMenu: true,
        title: $t('tenant.ai.agent.detail.title'),
        activePath: '/tenant/ai/agents',
        ai: { pageContextKey: 'tenant.ai.agents.detail' },
      },
    },
    {
      name: 'TenantAISkillPackageDetail',
      path: 'ai/skill-packages/:id',
      component: () => import('#/views/tenant/ai/skill-packages/detail.vue'),
      meta: {
        hideInMenu: true,
        title: $t('tenant.ai.skillPackage.detail.title'),
        activePath: '/tenant/ai/skill-packages',
        ai: { pageContextKey: 'tenant.ai.skill-packages.detail' },
      },
    },
    // 个人中心：不在后端菜单中，必须静态注册 / Profile: not in backend menu
    {
      name: 'TenantProfile',
      path: '/tenant/profile',
      component: () => import('#/views/tenant/profile/index.vue'),
      meta: {
        hideInMenu: true,
        title: $t('page.auth.profile'),
      },
    },
    // 全局偏好设置由后端动态菜单注册，无需静态路由
    // Global preferences registered via backend dynamic menu
  ],
};

/** Tenant routes / 企业管理端路由 */
export const tenantRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

export { tenantCoreRouteNames } from './names';
