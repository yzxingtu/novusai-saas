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
    // Fallback 静态注册：AI 管理（后端菜单动态路由优先生效）
    {
      name: 'TenantAI',
      path: 'ai',
      meta: {
        icon: 'lucide:bot',
        title: $t('tenant.ai.title'),
      },
      children: [
        {
          name: 'TenantAIModels',
          path: 'config',
          component: () => import('#/views/tenant/ai/models/index.vue'),
          meta: {
            icon: 'lucide:brain',
            title: $t('tenant.ai.model.title'),
          },
        },
        {
          name: 'TenantAIApiKeys',
          path: 'api-keys',
          component: () => import('#/views/tenant/ai/api-keys/index.vue'),
          meta: {
            icon: 'lucide:key',
            title: $t('tenant.ai.apiKey.title'),
          },
        },
        {
          name: 'TenantAIUsage',
          path: 'usage',
          component: () => import('#/views/tenant/ai/usage/index.vue'),
          meta: {
            icon: 'lucide:bar-chart-3',
            title: $t('tenant.ai.usage.title'),
          },
        },
        {
          name: 'TenantAICallLogs',
          path: 'call-logs',
          component: () => import('#/views/tenant/ai/call-logs/index.vue'),
          meta: {
            icon: 'lucide:scroll-text',
            title: $t('tenant.ai.callLog.title'),
          },
        },
        {
          name: 'TenantAIKnowledgeBases',
          path: 'knowledge-bases',
          component: () =>
            import('#/views/tenant/ai/knowledge-bases/index.vue'),
          meta: {
            icon: 'lucide:book-open',
            title: $t('tenant.knowledgeBase.title'),
          },
        },
        {
          name: 'TenantAISkillPackages',
          path: 'skill-packages',
          component: () =>
            import('#/views/tenant/ai/skill-packages/index.vue'),
          meta: {
            icon: 'lucide:package',
            title: $t('tenant.ai.skillPackage.title'),
          },
        },
        {
          name: 'TenantAISkillPackageDetail',
          path: 'skill-packages/:id',
          component: () =>
            import('#/views/tenant/ai/skill-packages/detail.vue'),
          meta: {
            hideInMenu: true,
            title: $t('tenant.ai.skillPackage.detail.title'),
            activePath: '/tenant/ai/skill-packages',
          },
        },
        {
          name: 'TenantAIAgents',
          path: 'agents',
          component: () => import('#/views/tenant/ai/agents/index.vue'),
          meta: {
            icon: 'lucide:bot',
            title: $t('tenant.ai.agent.title'),
          },
        },
        {
          name: 'TenantAIChat',
          path: 'chat',
          component: () => import('#/views/tenant/ai/chat/index.vue'),
          meta: {
            icon: 'lucide:message-square',
            title: $t('tenant.ai.chat.title'),
          },
        },
        {
          name: 'TenantAIConversations',
          path: 'conversations',
          component: () =>
            import('#/views/tenant/ai/conversations/index.vue'),
          meta: {
            icon: 'lucide:messages-square',
            title: $t('tenant.ai.conversation.title'),
          },
        },
        {
          name: 'TenantAIActionLogs',
          path: 'action-logs',
          component: () =>
            import('#/views/tenant/ai/action-logs/index.vue'),
          meta: {
            icon: 'lucide:file-text',
            title: $t('tenant.ai.actionLog.title'),
          },
        },
        {
          name: 'TenantAIQuotas',
          path: 'quotas',
          component: () => import('#/views/tenant/ai/quotas/index.vue'),
          meta: {
            icon: 'lucide:gauge',
            title: $t('tenant.ai.quota.title'),
          },
        },
        {
          name: 'TenantAITablePolicies',
          path: 'table-policies',
          component: () =>
            import('#/views/tenant/ai/table-policies/index.vue'),
          meta: {
            icon: 'lucide:shield',
            title: $t('tenant.ai.tablePolicy.title'),
          },
        },
      ],
    },
    // 个人中心
    {
      name: 'TenantProfile',
      path: '/tenant/profile',
      component: () => import('#/views/_core/profile/index.vue'),
      meta: {
        hideInMenu: true,
        title: $t('page.auth.profile'),
      },
    },
  ],
};

/** 租户管理端路由 */
export const tenantRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

export { tenantCoreRouteNames } from './names';
