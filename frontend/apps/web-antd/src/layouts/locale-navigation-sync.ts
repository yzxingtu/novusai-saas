import type { Router, RouteRecordRaw } from 'vue-router';

import type { GenerateMenuAndRoutesOptions } from '@vben/types';

import type { ApiEndpoint } from '#/api';
import type { RefreshPluginSlotsOptions } from '#/composables/use-plugin-frontend-init';

import { resolveRouteMetaTitle } from '@vben/utils';

type AccessibleResult = {
  accessibleMenus: unknown[];
  accessibleRoutes: unknown[];
};

type AccessStoreLike = {
  setAccessMenus(menus: unknown[]): void;
  setAccessRoutes(routes: unknown[]): void;
};

type HasLocaleKeyFn = (key: string) => boolean;

type RouterLike = Pick<Router, 'currentRoute' | 'getRoutes' | 'replace'>;

type TabLike = {
  meta?: Record<string, unknown>;
  path: string;
};

type TabbarStoreLike = {
  getTabs: TabLike[];
  setUpdateTime: () => void;
  touchTabs?: () => void;
};

type TranslateFn = (key: string, ...args: unknown[]) => string;

export interface SyncLocaleNavigationOptions {
  accessStore: AccessStoreLike;
  endpoint: ApiEndpoint;
  generateAccess: (
    options: GenerateMenuAndRoutesOptions,
    endpoint?: ApiEndpoint,
  ) => Promise<AccessibleResult>;
  hasLocaleKey: HasLocaleKeyFn;
  locale: string;
  refreshPluginSlots: (
    endpoint: string,
    router?: Router,
    options?: RefreshPluginSlotsOptions,
  ) => Promise<void>;
  router: RouterLike;
  routes: RouteRecordRaw[];
  tabbarStore: TabbarStoreLike;
  translate: TranslateFn;
  userRoles: string[];
}

export function buildCurrentRouteReloadTarget(
  currentRoute: RouterLike['currentRoute']['value'],
) {
  if (currentRoute.name) {
    return {
      hash: currentRoute.hash,
      name: currentRoute.name,
      params: currentRoute.params,
      query: currentRoute.query,
    };
  }

  return {
    hash: currentRoute.hash,
    path: currentRoute.path,
    query: currentRoute.query,
  };
}

export function syncOpenTabTitles(options: {
  hasLocaleKey: HasLocaleKeyFn;
  locale: string;
  router: RouterLike;
  tabbarStore: TabbarStoreLike;
  translate: TranslateFn;
}) {
  const routeMetaMap = new Map<string, Record<string, unknown>>();
  for (const route of options.router.getRoutes()) {
    if (route.meta) {
      routeMetaMap.set(route.path, route.meta as Record<string, unknown>);
    }
  }

  for (const tab of options.tabbarStore.getTabs) {
    const routeMeta = routeMetaMap.get(tab.path);
    const newTitle = resolveRouteMetaTitle(routeMeta, {
      hasLocaleKey: options.hasLocaleKey,
      locale: options.locale,
      translate: options.translate,
    });
    if (!newTitle || !tab.meta) {
      continue;
    }

    tab.meta.title = newTitle;
    tab.meta.titleLocaleMap = routeMeta?.titleLocaleMap as
      | Record<string, string>
      | undefined;
  }

  options.tabbarStore.touchTabs?.();
  options.tabbarStore.setUpdateTime();
}

export async function syncLocaleNavigation(
  options: SyncLocaleNavigationOptions,
) {
  const { accessibleMenus, accessibleRoutes } = await options.generateAccess(
    {
      roles: options.userRoles,
      router: options.router as Router,
      routes: options.routes,
    },
    options.endpoint,
  );

  options.accessStore.setAccessMenus(accessibleMenus);
  options.accessStore.setAccessRoutes(accessibleRoutes);
  await options.refreshPluginSlots(options.endpoint, options.router as Router, {
    reloadAssets: false,
  });

  syncOpenTabTitles({
    hasLocaleKey: options.hasLocaleKey,
    locale: options.locale,
    router: options.router,
    tabbarStore: options.tabbarStore,
    translate: options.translate,
  });

  await options.router.replace({
    ...buildCurrentRouteReloadTarget(options.router.currentRoute.value),
    force: true,
  });
}
