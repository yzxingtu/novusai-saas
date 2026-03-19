/**
 * Admin (platform management) route module
 * 平台管理端路由模块
 */
import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const AuthPageLayout = () => import('#/layouts/admin-auth.vue');
const BasicLayout = () => import('#/layouts/basic.vue');

/** Admin authentication routes / 平台管理端认证路由 */
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

/** Admin main layout routes / 平台管理端主布局路由 */
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
        ai: { mode: 'context_only' as const },
      },
    },
    // Analytics：数据分析页面
    {
      name: 'AdminAnalytics',
      path: 'analytics',
      component: () => import('#/views/admin/analytics/index.vue'),
      meta: {
        icon: 'lucide:bar-chart-3',
        title: $t('admin.analytics.title'),
        ai: { mode: 'context_only' as const },
      },
    },
    // 技能包详情页：带 :id 动态参数 + activePath，后端不注册此路由
    {
      name: 'AdminAISkillPackageDetail',
      path: 'ai/skill-packages/:id',
      component: () => import('#/views/admin/ai/skill-packages/detail.vue'),
      meta: {
        hideInMenu: true,
        title: $t('admin.ai.skillPackage.detail.title'),
        activePath: '/admin/ai/skill-packages',
        ai: { pageContextKey: 'admin.ai.skill-packages.detail' },
      },
    },
    // 智能体详情页
    {
      name: 'AdminAIAgentDetail',
      path: 'ai/agents/:id',
      component: () => import('#/views/admin/ai/agents/detail.vue'),
      meta: {
        hideInMenu: true,
        title: $t('admin.ai.agent.detail.title'),
        activePath: '/admin/ai/agents',
        ai: { pageContextKey: 'admin.ai.agents.detail' },
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
    // 代码生成器：DEBUG 模式，静态注册 / Codegen: DEBUG only, static routes
    {
      name: 'AdminSystemCodegen',
      path: 'system/codegen',
      component: () => import('#/views/admin/system/codegen/index.vue'),
      meta: {
        hideInProduction: true,
        title: $t('admin.system.codegen.name'),
        activePath: '/admin/system/codegen',
        accessCodes: ['action.codegen.list'],
      },
    },
    {
      name: 'AdminSystemCodegenNew',
      path: 'system/codegen/new',
      component: () => import('#/views/admin/system/codegen/builder.vue'),
      meta: {
        hideInMenu: true,
        hideInProduction: true,
        title: $t('admin.system.codegen.builderNew'),
        activePath: '/admin/system/codegen',
        accessCodes: ['action.codegen.create', 'action.codegen.options'],
        accessCodesMode: 'all',
      },
    },
    {
      name: 'AdminSystemCodegenEdit',
      path: 'system/codegen/:id/edit',
      component: () => import('#/views/admin/system/codegen/builder.vue'),
      meta: {
        hideInMenu: true,
        hideInProduction: true,
        title: $t('admin.system.codegen.builderEdit'),
        activePath: '/admin/system/codegen',
        accessCodes: [
          'action.codegen.detail',
          'action.codegen.options',
          'action.codegen.update',
        ],
        accessCodesMode: 'all',
      },
    },
    // 个人中心：不在后端菜单中，必须静态注册 / Profile: not in backend menu
    {
      name: 'AdminProfile',
      path: '/admin/profile',
      component: () => import('#/views/admin/profile/index.vue'),
      meta: {
        hideInMenu: true,
        title: $t('page.auth.profile'),
      },
    },
    // 全局偏好设置由后端动态菜单注册，无需静态路由
    // Global preferences registered via backend dynamic menu
  ],
};

/** Admin routes / 平台管理端路由 */
export const adminRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

/** Admin core route names (bypass permission checks) / 平台管理端路由名称列表（不需要权限拦截） */
export const adminCoreRouteNames = ['AdminAuthentication', 'AdminLogin'];
