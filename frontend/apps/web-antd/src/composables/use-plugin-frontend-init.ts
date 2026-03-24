/**
 * Plugin frontend initialization composable
 * 插件前端初始化 Composable
 *
 * Injection-based loading: fetches visible plugin slots via API, then dynamically loads UMD plugin components.
 * 注入式加载：通过 API 获取可见插件插槽，再按需 UMD 动态加载插件组件
 *
 * 插件端点 scope（PermissionScope，与资源 ResourceScopeEnum 不同）过滤规则:
 *   - admin   → 仅管理端加载
 *   - tenant  → 仅企业端加载
 *   Current plugin frontend model does not support user-side endpoints.
 *   / 当前插件前端模型不支持 user 端。
 */

import type { Component } from 'vue';
import type { Router, RouteRecordRaw } from 'vue-router';

import { onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { usePluginExtensionsStore } from '#/stores/plugin-extensions';
import { usePluginSlotsStore } from '#/stores/plugin-slots';
import { unloadPlugin } from '#/utils/plugin-loader';

type EndpointSide = 'admin' | 'tenant';

const PLUGIN_ROUTE_PREFIXES = ['/admin/plugins/', '/tenant/plugins/'] as const;

function isValidPluginRoutePath(path: string): boolean {
  return PLUGIN_ROUTE_PREFIXES.some((prefix) => path.startsWith(prefix));
}

/**
 * Registered plugin route names (for uninstall cleanup)
 * 已注册的插件路由名称（用于卸载清理）
 */
const registeredPluginRouteNames: Set<string> = new Set();

/**
 * Remove all dynamically registered plugin routes
 * 移除所有插件注册的动态路由
 */
function removeAllPluginPageRoutes(router: Router) {
  for (const name of registeredPluginRouteNames) {
    if (router.hasRoute(name)) {
      router.removeRoute(name);
    }
  }
  registeredPluginRouteNames.clear();
}

function getLoadedPluginNames(
  slotsStore: ReturnType<typeof usePluginSlotsStore>,
): string[] {
  const pluginNames = new Set<string>();
  for (const list of [
    slotsStore.headerWidgets,
    slotsStore.floatingPanels,
    slotsStore.dashboardWidgets,
    slotsStore.settingsTabs,
    slotsStore.notificationUI,
    slotsStore.pages,
  ]) {
    for (const item of list) {
      if (
        typeof item.pluginName === 'string' &&
        item.pluginName.trim().length > 0
      ) {
        pluginNames.add(item.pluginName);
      }
    }
  }
  return [...pluginNames];
}

// Flag whether plugin routes are registered (prevent duplicate registration) / 标记插件路由是否已注册
let _pluginRoutesReady = false;
let _pluginRoutesReadySide: EndpointSide | null = null;
let pluginFrontendGeneration = 0;
const pluginFrontendInFlight: Map<EndpointSide, Promise<void>> = new Map();
const queuedPluginFrontendRefreshSides: Set<EndpointSide> = new Set();

export interface RefreshPluginSlotsOptions {
  reloadAssets?: boolean;
}

function getPluginPageRouteName(item: {
  name: string;
  pluginName: string;
}): string {
  return `plugin-${item.pluginName}-${item.name}`;
}

function hasMissingPluginRoutes(
  router: Router,
  slotsStore: ReturnType<typeof usePluginSlotsStore>,
): boolean {
  for (const item of slotsStore.pages) {
    if (!item.path || !item.component) continue;
    if (!isValidPluginRoutePath(item.path)) continue;
    if (!router.hasRoute(getPluginPageRouteName(item))) {
      return true;
    }
  }
  return false;
}

function inferLoadedPluginSide(
  slotsStore: ReturnType<typeof usePluginSlotsStore>,
): EndpointSide | null {
  for (const list of [
    slotsStore.pages,
    slotsStore.headerWidgets,
    slotsStore.dashboardWidgets,
    slotsStore.settingsTabs,
    slotsStore.floatingPanels,
    slotsStore.notificationUI,
  ]) {
    for (const item of list) {
      if (typeof item.path === 'string') {
        if (item.path.startsWith('/tenant/plugins/')) {
          return 'tenant';
        }
        if (item.path.startsWith('/admin/plugins/')) {
          return 'admin';
        }
      }
      if (item.scope === 'tenant') {
        return 'tenant';
      }
      if (item.scope === 'admin') {
        return 'admin';
      }
    }
  }
  return null;
}

async function syncPluginFrontendState(
  side: EndpointSide,
  router?: Router,
  options: {
    forceRefresh?: boolean;
    reloadAssets?: boolean;
  } = {},
) {
  const forceRefresh = options.forceRefresh ?? false;
  const reloadAssets = options.reloadAssets ?? false;
  const slotsStore = usePluginSlotsStore();
  const extensionsStore = usePluginExtensionsStore();

  while (true) {
    if (
      router &&
      !forceRefresh &&
      _pluginRoutesReady &&
      _pluginRoutesReadySide === side
    ) {
      if (!hasMissingPluginRoutes(router, slotsStore)) {
        return;
      }
      removeAllPluginPageRoutes(router);
      _registerStandalonePageRoutes(router, slotsStore);
      return;
    }

    const existing = pluginFrontendInFlight.get(side);
    if (existing) {
      if (forceRefresh) {
        queuedPluginFrontendRefreshSides.add(side);
      }
      try {
        await existing;
      } catch {
        // Let the caller retry with a fresh pass after the in-flight sync settles. / 同步结束后由调用方重试
      }

      if (!forceRefresh) {
        continue;
      }
      if (queuedPluginFrontendRefreshSides.delete(side)) {
        continue;
      }
      return;
    }

    const previousPluginNames = getLoadedPluginNames(slotsStore);
    const generationAtStart = pluginFrontendGeneration;
    const task = (async () => {
      const extensionsSnapshot = reloadAssets
        ? extensionsStore.captureSnapshot()
        : null;

      if (reloadAssets) {
        extensionsStore.clearAll();
      }

      try {
        await slotsStore.fetchSlots(side, {
          forceReload: reloadAssets,
        });
      } catch (error) {
        if (extensionsSnapshot) {
          extensionsStore.restoreSnapshot(extensionsSnapshot);
        }
        throw error;
      }

      if (generationAtStart !== pluginFrontendGeneration) {
        return;
      }

      if (router) {
        removeAllPluginPageRoutes(router);
      }

      const nextPluginNames = getLoadedPluginNames(slotsStore);
      const nextPluginSet = new Set(nextPluginNames);
      for (const pluginName of previousPluginNames) {
        if (nextPluginSet.has(pluginName)) {
          continue;
        }
        extensionsStore.unregisterPlugin(pluginName);
        unloadPlugin(pluginName, { endpoint: side });
      }

      if (router) {
        _registerStandalonePageRoutes(router, slotsStore);
      }

      _pluginRoutesReady = true;
      _pluginRoutesReadySide = side;
    })();

    pluginFrontendInFlight.set(side, task);

    try {
      await task;
    } finally {
      if (pluginFrontendInFlight.get(side) === task) {
        pluginFrontendInFlight.delete(side);
      }
    }

    if (forceRefresh && queuedPluginFrontendRefreshSides.delete(side)) {
      continue;
    }
    return;
  }
}

/**
 * Ensure plugin routes are registered (can be called in guard for seamless refresh)
 * 确保插件路由已注册（可在 guard 中调用，实现刷新无感）
 * Idempotent: multiple calls execute only once.
 * 幂等：多次调用只执行一次。
 *
 * M51-T9: Consistent with usePluginFrontendInit, uses store.fetchSlots() unified entry.
 */
export async function ensurePluginRoutes(
  router: Router,
  endpoint: string = '/admin',
) {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  try {
    await syncPluginFrontendState(side, router);
  } catch (error: unknown) {
    console.error('[ensurePluginRoutes] Failed:', error);
  }
}

/** Reset plugin routes ready flag (called on endpoint switch) / 重置插件路由就绪标志（端切换时调用） */
export function resetPluginRoutesReady(router?: Router) {
  const slotsStore = usePluginSlotsStore();
  const loadedSide =
    _pluginRoutesReadySide ?? inferLoadedPluginSide(slotsStore);
  pluginFrontendGeneration += 1;
  _pluginRoutesReady = false;
  _pluginRoutesReadySide = null;
  queuedPluginFrontendRefreshSides.clear();

  if (router) {
    removeAllPluginPageRoutes(router);
  }

  const extensionsStore = usePluginExtensionsStore();
  const pluginNames = getLoadedPluginNames(slotsStore);
  for (const pluginName of pluginNames) {
    if (loadedSide) {
      unloadPlugin(pluginName, { endpoint: loadedSide });
    }
  }
  slotsStore.clearAll();
  extensionsStore.clearAll();
}

/**
 * Independently refresh plugin frontend slots (call after enable/disable/uninstall, no F5 needed)
 * 独立刷新插件前端插槽（可在启用/禁用/卸载后调用，无需 F5）
 *
 * M51-T9: Uses store.fetchSlots() to call backend /plugins/slots API,
 * then registers Vue Router dynamic routes based on pages.
 */
export async function refreshPluginSlots(
  endpoint: string = '/admin',
  router?: Router,
  options: RefreshPluginSlotsOptions = {},
) {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  await syncPluginFrontendState(side, router, {
    forceRefresh: true,
    reloadAssets: options.reloadAssets ?? false,
  });
}

/**
 * M51-T9: Register plugin pages from pages as Vue Router dynamic routes
 * 将 pages 中的插件页面注册为 Vue Router 动态路由
 * (Does not add sidebar menus, menus are managed by RBAC permission system)
 * （不添加侧边栏菜单，菜单由 RBAC 权限系统管理）
 */
function _registerStandalonePageRoutes(
  router: Router,
  slotsStore: ReturnType<typeof usePluginSlotsStore>,
) {
  for (const item of slotsStore.pages) {
    if (!item.path || !item.component) continue;
    if (!isValidPluginRoutePath(item.path)) continue;

    const isTenant = item.path.startsWith('/tenant/plugins/');
    const parentName = isTenant ? 'TenantRoot' : 'AdminRoot';
    const prefix = isTenant ? '/tenant/' : '/admin/';
    const childPath = item.path.startsWith(prefix)
      ? item.path.slice(prefix.length)
      : item.path.replace(/^\//, '');
    const routeName = getPluginPageRouteName(item);

    if (registeredPluginRouteNames.has(routeName) || router.hasRoute(routeName))
      continue;

    const samePathRoutes = router
      .getRoutes()
      .filter((route) => route.path === item.path && route.name !== routeName);
    for (const route of samePathRoutes) {
      if (route.name) {
        router.removeRoute(route.name);
      }
    }

    const routeMeta: NonNullable<RouteRecordRaw['meta']> = {
      title: item.title ?? item.name,
      ...(item.titleLocaleMap ? { titleLocaleMap: item.titleLocaleMap } : {}),
      icon: item.icon,
      hideInMenu: true,
    };
    if (Array.isArray(item.accessCodes) && item.accessCodes.length > 0) {
      routeMeta.accessCodes = item.accessCodes;
    }
    if (item.ai) {
      routeMeta.ai = {
        ...(item.ai.mode ? { mode: item.ai.mode } : {}),
        ...(item.ai.page_context_key
          ? { pageContextKey: item.ai.page_context_key }
          : {}),
        ...(item.ai.disabled_capabilities?.length
          ? { disabledCapabilities: item.ai.disabled_capabilities }
          : {}),
        ...(item.ai.disabled_operations?.length
          ? { disabledOperations: item.ai.disabled_operations }
          : {}),
      };
    }

    router.addRoute(parentName, {
      name: routeName,
      path: childPath,
      component: item.component as Component,
      props: (route) => ({
        shared: (window as unknown as Record<string, unknown>)
          .NovusPluginShared,
        ...route.params,
      }),
      meta: routeMeta,
    });
    registeredPluginRouteNames.add(routeName);
  }
}

export function usePluginFrontendInit(endpoint: string = '/admin') {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  const router = useRouter();

  async function initPluginSlots() {
    await syncPluginFrontendState(side, router);
  }

  onMounted(async () => {
    try {
      await initPluginSlots();
    } catch (error: unknown) {
      console.warn('[usePluginFrontendInit] initPluginSlots failed:', error);
    }
  });

  return { initPluginSlots };
}
