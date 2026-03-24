import type { RouteRecordRaw } from 'vue-router';

import { usePublicConfigStore } from '#/store';

const rootGatewayRoute: RouteRecordRaw = {
  path: '/',
  name: 'PlatformPublicHome',
  component: () => import('#/views/public/platform-home/index.vue'),
  meta: {
    hideInBreadcrumb: true,
    hideInMenu: true,
    hideInTab: true,
    title: 'public.platformHome.title',
  },
  beforeEnter: async (to) => {
    const publicConfigStore = usePublicConfigStore();

    await publicConfigStore.detectDomainType().catch(() => {});

    if (publicConfigStore.isDomainTenantDomain) {
      return {
        name: 'UserHome',
        query: to.query,
        hash: to.hash,
        replace: true,
      };
    }

    return true;
  },
};

export const rootRoutes: RouteRecordRaw[] = [rootGatewayRoute];
export const rootCoreRouteNames = ['PlatformPublicHome'];
