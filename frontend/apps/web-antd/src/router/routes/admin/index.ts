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
    // Fallback 静态注册：附件管理（后端菜单动态路由优先生效）
    {
      name: 'AdminSystemAttachments',
      path: 'system/attachments',
      component: () => import('#/views/admin/system/attachments/index.vue'),
      meta: {
        hideInMenu: true,
        icon: 'lucide:paperclip',
        title: $t('admin.system.attachment.title'),
      },
    },
    // Fallback 静态注册：任务日志（后端菜单动态路由优先生效）
    {
      name: 'AdminSystemTaskLogs',
      path: 'system/task-logs',
      component: () => import('#/views/admin/system/task-logs/index.vue'),
      meta: {
        hideInMenu: true,
        icon: 'lucide:list-checks',
        title: $t('admin.system.taskLog.title'),
      },
    },
    // Fallback 静态注册：定时任务（后端菜单动态路由优先生效）
    {
      name: 'AdminSystemPeriodicTasks',
      path: 'system/periodic-tasks',
      component: () =>
        import('#/views/admin/system/periodic-tasks/index.vue'),
      meta: {
        hideInMenu: true,
        icon: 'lucide:timer',
        title: $t('admin.system.periodicTask.title'),
      },
    },
    // Fallback 静态注册：AI 网关管理（后端菜单动态路由优先生效）
    {
      name: 'AdminAIGateway',
      path: 'ai',
      meta: {
        icon: 'lucide:bot',
        title: $t('admin.ai.title'),
      },
      children: [
        {
          name: 'AdminAIProviders',
          path: 'providers',
          component: () => import('#/views/admin/ai/providers/index.vue'),
          meta: {
            icon: 'lucide:cpu',
            title: $t('admin.ai.provider.title'),
          },
        },
        {
          name: 'AdminAIModels',
          path: 'models',
          component: () => import('#/views/admin/ai/models/index.vue'),
          meta: {
            icon: 'lucide:brain',
            title: $t('admin.ai.model.title'),
          },
        },
        {
          name: 'AdminAIApiKeys',
          path: 'api-keys',
          component: () => import('#/views/admin/ai/api-keys/index.vue'),
          meta: {
            icon: 'lucide:key',
            title: $t('admin.ai.apiKey.title'),
          },
        },
        {
          name: 'AdminAIQuotas',
          path: 'quotas',
          component: () => import('#/views/admin/ai/quotas/index.vue'),
          meta: {
            icon: 'lucide:gauge',
            title: $t('admin.ai.quota.title'),
          },
        },
        // 监控与分析（子目录）
        {
          name: 'AdminAIMonitor',
          path: 'monitor',
          meta: {
            icon: 'lucide:activity',
            title: $t('admin.ai.monitor.title'),
          },
          children: [
            {
              name: 'AdminAICallLogs',
              path: 'call-logs',
              component: () => import('#/views/admin/ai/call-logs/index.vue'),
              meta: {
                icon: 'lucide:scroll-text',
                title: $t('admin.ai.callLog.title'),
              },
            },
            {
              name: 'AdminAIUsage',
              path: 'usage',
              component: () => import('#/views/admin/ai/usage/index.vue'),
              meta: {
                icon: 'lucide:bar-chart-3',
                title: $t('admin.ai.usage.title'),
              },
            },
            {
              name: 'AdminAIHealth',
              path: 'health',
              component: () => import('#/views/admin/ai/health/index.vue'),
              meta: {
                icon: 'lucide:heart-pulse',
                title: $t('admin.ai.health.title'),
              },
            },
          ],
        },
        {
          name: 'AdminAIKnowledgeBases',
          path: 'knowledge-bases',
          component: () =>
            import('#/views/admin/ai/knowledge-bases/index.vue'),
          meta: {
            icon: 'lucide:book-open',
            title: $t('admin.knowledgeBase.title'),
          },
        },
        {
          name: 'AdminAISkillPackages',
          path: 'skill-packages',
          component: () =>
            import('#/views/admin/ai/skill-packages/index.vue'),
          meta: {
            icon: 'lucide:package',
            title: $t('admin.ai.skillPackage.title'),
          },
        },
        // AdminAISkillPackageDetail + AdminAISkills routes removed — Master-Detail layout in index.vue
        {
          name: 'AdminAIAgents',
          path: 'agents',
          component: () => import('#/views/admin/ai/agents/index.vue'),
          meta: {
            icon: 'lucide:bot',
            title: $t('admin.ai.agent.title'),
          },
        },
        {
          name: 'AdminAIChat',
          path: 'chat',
          component: () => import('#/views/admin/ai/chat/index.vue'),
          meta: {
            icon: 'lucide:message-square',
            title: $t('admin.ai.chat.title'),
          },
        },
        {
          name: 'AdminAIConversations',
          path: 'conversations',
          component: () =>
            import('#/views/admin/ai/conversations/index.vue'),
          meta: {
            icon: 'lucide:messages-square',
            title: $t('admin.ai.conversation.title'),
          },
        },
        {
          name: 'AdminAIActionLogs',
          path: 'action-logs',
          component: () =>
            import('#/views/admin/ai/action-logs/index.vue'),
          meta: {
            icon: 'lucide:file-text',
            title: $t('admin.ai.actionLog.title'),
          },
        },
        {
          name: 'AdminAITablePolicies',
          path: 'table-policies',
          component: () =>
            import('#/views/admin/ai/table-policies/index.vue'),
          meta: {
            icon: 'lucide:shield',
            title: $t('admin.ai.tablePolicy.title'),
          },
        },
      ],
    },
    // Fallback 静态注册：开发工具（后端菜单动态路由优先生效）
    {
      name: 'AdminDevTools',
      path: 'dev',
      meta: {
        hideInMenu: true,
        icon: 'lucide:code-2',
        title: $t('admin.dev.title'),
      },
      children: [
        {
          name: 'AdminDevCrudGenerator',
          path: 'crud-generator',
          component: () =>
            import('#/views/admin/dev/crud-generator/index.vue'),
          meta: {
            icon: 'lucide:wand-2',
            title: $t('admin.dev.crudGenerator.title'),
          },
        },
      ],
    },
  ],
};

/** 平台管理端路由 */
export const adminRoutes: RouteRecordRaw[] = [authRoutes, mainRoutes];

/** 平台管理端路由名称列表（不需要权限拦截） */
export const adminCoreRouteNames = ['AdminAuthentication', 'AdminLogin'];
