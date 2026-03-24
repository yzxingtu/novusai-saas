/**
 * User-facing route module
 * 用户端路由模块
 */
import type { RouteRecordRaw } from 'vue-router';

const UserLayout = () => import('#/layouts/user.vue');

/** User main layout routes / 用户端主布局路由 */
const mainRoutes: RouteRecordRaw = {
  component: UserLayout,
  meta: {
    hideInBreadcrumb: true,
    title: 'User Root',
  },
  name: 'UserRoot',
  path: '/',
  children: [
    {
      name: 'UserHome',
      path: '',
      alias: ['/home'],
      component: () => import('#/views/user/home/index.vue'),
      meta: {
        affixTab: true,
        icon: 'lucide:home',
        ignoreAccess: true,
        title: 'user.home.title',
      },
    },
    {
      name: 'UserAgents',
      path: 'agents',
      component: () => import('#/views/user/agents/index.vue'),
      meta: {
        icon: 'lucide:sparkles',
        title: 'user.agents.title',
      },
    },
    {
      name: 'UserAIChat',
      path: 'ai-chat',
      component: () => import('#/views/user/ai-chat/index.vue'),
      meta: {
        icon: 'lucide:bot',
        title: 'user.aiChat.title',
      },
    },
    {
      name: 'UserHelp',
      path: 'help',
      component: () => import('#/views/user/help/index.vue'),
      meta: {
        icon: 'lucide:life-buoy',
        title: 'user.helpCenter.title',
      },
    },
    {
      name: 'UserSettings',
      path: 'settings',
      component: () => import('#/views/user/settings/index.vue'),
      redirect: '/settings/profile',
      meta: {
        icon: 'lucide:settings',
        title: 'user.settings.title',
      },
      children: [
        {
          name: 'UserProfile',
          path: 'profile',
          component: () => import('#/views/user/profile/index.vue'),
          meta: {
            icon: 'lucide:user',
            title: 'user.profile.title',
          },
        },
        {
          name: 'UserChangePassword',
          path: 'password',
          component: () =>
            import('#/views/user/profile/change-password.vue'),
          meta: {
            hideInMenu: true,
            title: 'user.profile.changePassword',
          },
        },
        // UserPreferences route removed — personal preferences handled via Vben gear sidebar
        // 用户端偏好页面已移除，个人偏好通过 Vben 齿轮侧边栏管理
      ],
    },
  ],
};

/** User routes / 用户端路由 */
export const userRoutes: RouteRecordRaw[] = [mainRoutes];

/** User core route names (bypass permission checks) / 用户端路由名称列表（不需要权限拦截） */
export const userCoreRouteNames: string[] = [];
