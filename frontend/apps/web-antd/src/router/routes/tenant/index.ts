/**
 * Tenant management route module
 * 企业管理端路由模块
 */
import type { RouteRecordRaw } from 'vue-router';

const AuthPageLayout = () => import('#/layouts/tenant-auth.vue');
const BasicLayout = () => import('#/layouts/basic.vue');

/** Tenant authentication routes / 企业管理端认证路由 */
const authRoutes: RouteRecordRaw = {
  component: AuthPageLayout,
  meta: {
    hideInTab: true,
    title: 'page.tenant.authentication',
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
        title: 'page.auth.login',
      },
    },
    {
      name: 'TenantImpersonate',
      path: '/tenant/impersonate',
      component: () => import('#/views/tenant/authentication/impersonate.vue'),
      meta: {
        title: 'page.auth.impersonate',
      },
    },
  ],
};

/** Tenant main layout routes / 企业管理端主布局路由 */
const mainRoutes: RouteRecordRaw = {
  component: BasicLayout,
  meta: {
    hideInBreadcrumb: true,
    title: 'page.tenant.root',
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
        title: 'page.dashboard.title',
      },
    },
    // Analytics：数据分析页面
    {
      name: 'TenantAnalytics',
      path: 'analytics',
      component: () => import('#/views/tenant/analytics/index.vue'),
      meta: {
        icon: 'lucide:bar-chart-3',
        title: 'tenant.analytics.title',
      },
    },
    // 智能体详情页 / Agent detail page
    {
      name: 'TenantAIAgentDetail',
      path: 'ai/agents/:id',
      component: () => import('#/views/tenant/ai/agents/detail.vue'),
      meta: {
        accessCodes: ['agent:detail'],
        hideInMenu: true,
        title: 'tenant.ai.agent.detail.title',
        activePath: '/tenant/ai/agents',
      },
    },
    // 个人中心：不在后端菜单中，必须静态注册 / Profile: not in backend menu
    {
      name: 'TenantProfile',
      path: '/tenant/profile',
      component: () => import('#/views/tenant/profile/index.vue'),
      meta: {
        hideInMenu: true,
        title: 'page.auth.profile',
      },
    },
    // 全局偏好设置由后端动态菜单注册，无需静态路由
    // Global preferences registered via backend dynamic menu
  ],
};

/** Tenant routes / 企业管理端路由 */
export const tenantRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

export { tenantCoreRouteNames } from './names';
