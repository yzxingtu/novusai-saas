/**
 * Plugin frontend initialization composable
 * 插件前端初始化 Composable
 *
 * Injection-based loading: fetches visible plugin slots via API, then dynamically loads UMD plugin components.
 * 注入式加载：通过 API 获取可见插件插槽，再按需 UMD 动态加载插件组件
 *
 * Scope filter rules / Scope 过滤规则:
 *   - admin_only         → load frontend only on admin side / 仅 admin 端加载
 *   - all_tenants        → load frontend only on tenant side / 仅 tenant 端加载
 *   - assigned_tenants   → load only on assigned tenant side / 仅被分配的 tenant 端加载
 *   - admin_and_all      → admin + all tenants / admin + 所有 tenant 端
 *   - admin_and_assigned → admin + assigned tenants / admin + 被分配的 tenant 端
 */

import type { Component } from 'vue';
import type { Router } from 'vue-router';

import { onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { usePluginExtensionsStore } from '#/stores/plugin-extensions';
import { usePluginSlotsStore } from '#/stores/plugin-slots';

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

// Flag whether plugin routes are registered (prevent duplicate registration) / 标记插件路由是否已注册
let _pluginRoutesReady = false;
let _pluginRoutesReadySide: EndpointSide | null = null;

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
  if (_pluginRoutesReady && _pluginRoutesReadySide === side) return;

  const slotsStore = usePluginSlotsStore();
  const extensionsStore = usePluginExtensionsStore();

  try {
    // Fetch first, only clear after success to avoid losing existing routes on failure / 先拉取，成功后再清空，避免失败时丢失现有路由
    // / 先 fetch，成功后再清理，避免失败时丢失现有路由
    await slotsStore.fetchSlots(side);

    removeAllPluginPageRoutes(router);
    extensionsStore.clearAll();

    _registerStandalonePageRoutes(router, slotsStore);

    _pluginRoutesReady = true;
    _pluginRoutesReadySide = side;
  } catch (error: unknown) {
    console.error('[ensurePluginRoutes] Failed:', error);
  }
}

/** Reset plugin routes ready flag (called on endpoint switch) / 重置插件路由就绪标志（端切换时调用） */
export function resetPluginRoutesReady(router?: Router) {
  _pluginRoutesReady = false;
  _pluginRoutesReadySide = null;

  if (router) {
    removeAllPluginPageRoutes(router);
  }

  const slotsStore = usePluginSlotsStore();
  const extensionsStore = usePluginExtensionsStore();
  slotsStore.clearAll();
  extensionsStore.clearAll();
}

/**
 * Independently refresh plugin frontend slots (call after enable/disable/uninstall, no F5 needed)
 * 独立刷新插件前端插槽（可在启用/禁用/卸载后调用，无需 F5）
 *
 * M51-T9: Uses store.fetchSlots() to call backend /plugins/slots API,
 * then registers Vue Router dynamic routes based on standalonePages.
 */
export async function refreshPluginSlots(
  endpoint: string = '/admin',
  router?: Router,
) {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  const slotsStore = usePluginSlotsStore();
  const extensionsStore = usePluginExtensionsStore();

  if (router) {
    removeAllPluginPageRoutes(router);
  }

  extensionsStore.clearAll();
  // fetchSlots internally calls clearAll / fetchSlots 内部已调用 clearAll
  await slotsStore.fetchSlots(side);

  if (router) {
    _registerStandalonePageRoutes(router, slotsStore);
  }
  _pluginRoutesReady = true;
  _pluginRoutesReadySide = side;
}

/**
 * M51-T9: Register plugin pages from standalonePages as Vue Router dynamic routes
 * 将 standalonePages 中的插件页面注册为 Vue Router 动态路由
 * (Does not add sidebar menus, menus are managed by RBAC permission system)
 * （不添加侧边栏菜单，菜单由 RBAC 权限系统管理）
 */
function _registerStandalonePageRoutes(
  router: Router,
  slotsStore: ReturnType<typeof usePluginSlotsStore>,
) {
  for (const item of slotsStore.standalonePages) {
    if (!item.path || !item.component) continue;
    if (!isValidPluginRoutePath(item.path)) continue;

    const isTenant = item.path.startsWith('/tenant/plugins/');
    const parentName = isTenant ? 'TenantRoot' : 'AdminRoot';
    const prefix = isTenant ? '/tenant/' : '/admin/';
    const childPath = item.path.startsWith(prefix)
      ? item.path.slice(prefix.length)
      : item.path.replace(/^\//, '');
    const routeName = `plugin-${item.pluginName}-${item.name}`;

    if (registeredPluginRouteNames.has(routeName) || router.hasRoute(routeName))
      continue;

    const routeMeta: Record<string, unknown> = {
      title: item.title ?? item.name,
      icon: item.icon,
      hideInMenu: true,
    };
    if (item.ai) {
      routeMeta.ai = {
        mode: item.ai.mode,
        ...(item.ai.page_context_key
          ? { pageContextKey: item.ai.page_context_key }
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
  const slotsStore = usePluginSlotsStore();
  const router = useRouter();

  async function initPluginSlots() {
    // Phase 1: Fetch slot data via unified /plugins/slots API (M51-T9)
    // Backend already filters by scope + tenant assignment, no frontend filtering needed / 后端已按 scope 与分配过滤，前端无需再过滤
    await slotsStore.fetchSlots(side);

    // Phase 2: Register standalone_pages dynamic routes / 注册 standalone_pages 动态路由
    _registerStandalonePageRoutes(router, slotsStore);
  }

  onMounted(async () => {
    await initPluginSlots();
  });

  return { initPluginSlots };
}
