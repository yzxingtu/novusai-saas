import type { RouteRecordRaw } from 'vue-router';

import { traverseTreeValues } from '@vben/utils';

// 各端路由模块
import { adminCoreRouteNames, adminRoutes } from './admin';
import { coreRoutes, fallbackNotFoundRoute } from './core';
import { tenantRoutes } from './tenant';
import { tenantCoreRouteNames } from './tenant/names';
import { userCoreRouteNames, userRoutes } from './user';

/** 路由列表，由基本路由、各端路由和 404 兖底路由组成 */
const routes: RouteRecordRaw[] = [
  ...coreRoutes,
  ...adminRoutes,
  ...tenantRoutes,
  ...userRoutes,
  fallbackNotFoundRoute,
];

/** 基本路由列表，这些路由不需要进入权限拦截 */
const coreRouteNames = [
  ...traverseTreeValues(coreRoutes, (route) => route.name),
  ...adminCoreRouteNames,
  ...tenantCoreRouteNames,
  ...userCoreRouteNames,
];

/** 有权限校验的路由列表（由后端菜单动态生成） */
const accessRoutes: RouteRecordRaw[] = [];
export { accessRoutes, coreRouteNames, routes };
