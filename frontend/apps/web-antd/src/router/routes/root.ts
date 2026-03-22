import type { RouteRecordRaw } from 'vue-router';

import { RouterView } from 'vue-router';

import {
  HOME_PATHS,
  LOGIN_PATHS,
  resolveRootEndpoint,
} from '#/constants/endpoints';
import { usePublicConfigStore } from '#/store';
import { TokenStorage } from '#/store/shared/token-storage';

const rootGatewayRoute: RouteRecordRaw = {
  path: '/',
  name: 'RootGateway',
  component: RouterView,
  meta: {
    hideInBreadcrumb: true,
    hideInMenu: true,
    hideInTab: true,
    title: 'Root Gateway',
  },
  beforeEnter: async (to) => {
    const publicConfigStore = usePublicConfigStore();

    await publicConfigStore.detectDomainType().catch(() => {});

    const rootEndpoint =
      publicConfigStore.isDomainDetected
        ? publicConfigStore.isDomainTenantDomain
          ? 'user'
          : 'admin'
        : resolveRootEndpoint();

    if (rootEndpoint === 'admin') {
      if (TokenStorage.hasToken('admin')) {
        return { path: HOME_PATHS.admin, replace: true };
      }
      return { path: LOGIN_PATHS.admin, replace: true };
    }
    return {
      name: 'UserHome',
      query: to.query,
      hash: to.hash,
      replace: true,
    };
  },
};

export const rootRoutes: RouteRecordRaw[] = [rootGatewayRoute];
export const rootCoreRouteNames = ['RootGateway'];
