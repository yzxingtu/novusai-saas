/**
 * 插件前端初始化 Composable
 *
 * 注入式加载：
 *   通过 API 获取可见插件插槽，再按需 UMD 动态加载插件组件
 *
 * Scope 过滤规则：
 *   - admin_only         → 仅 admin 端加载前端
 *   - all_tenants        → 仅 tenant 端加载前端
 *   - assigned_tenants   → 仅被分配的 tenant 端加载前端
 *   - admin_and_all      → admin + 所有 tenant 端加载前端
 *   - admin_and_assigned → admin + 被分配的 tenant 端加载前端
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
 * 已注册的插件路由名称（用于卸载清理）
 */
const registeredPluginRouteNames: Set<string> = new Set();

/**
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

// 标记插件路由是否已注册（防止重复注册）
let _pluginRoutesReady = false;
let _pluginRoutesReadySide: EndpointSide | null = null;

/**
 * 确保插件路由已注册（可在 guard 中调用，实现刷新无感）
 * 幂等：多次调用只执行一次。
 *
 * M51-T9: 与 usePluginFrontendInit 保持一致，使用 store.fetchSlots() 统一入口。
 */
export async function ensurePluginRoutes(
  router: Router,
  endpoint: string = '/admin',
) {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  if (_pluginRoutesReady && _pluginRoutesReadySide === side) return;

  const slotsStore = usePluginSlotsStore();
  const extensionsStore = usePluginExtensionsStore();

  removeAllPluginPageRoutes(router);
  slotsStore.clearAll();
  extensionsStore.clearAll();

  try {
    // 统一通过 /plugins/slots API 获取插槽数据（与 usePluginFrontendInit 同路径）
    await slotsStore.fetchSlots(side);

    // 注册 standalonePages 动态路由
    _registerStandalonePageRoutes(router, slotsStore);

    _pluginRoutesReady = true;
    _pluginRoutesReadySide = side;
  } catch (error: unknown) {
    console.error('[ensurePluginRoutes] Failed:', error);
  }
}

/** 重置插件路由就绪标志（端切换时调用） */
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
 * 独立刷新插件前端插槽（可在启用/禁用/卸载后调用，无需 F5）
 *
 * M51-T9: 统一使用 store.fetchSlots() 调用后端 /plugins/slots API，
 *         再根据 standalonePages 注册 Vue Router 动态路由。
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
  // fetchSlots 内部已调用 clearAll
  await slotsStore.fetchSlots(side);

  if (router) {
    _registerStandalonePageRoutes(router, slotsStore);
  }
  _pluginRoutesReady = true;
  _pluginRoutesReadySide = side;
}

/**
 * M51-T9: 将 standalonePages 中的插件页面注册为 Vue Router 动态路由
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

    router.addRoute(parentName, {
      name: routeName,
      path: childPath,
      component: item.component as Component,
      props: (route) => ({
        shared: (window as unknown as Record<string, unknown>)
          .NovusPluginShared,
        ...route.params,
      }),
      meta: {
        title: item.title ?? item.name,
        icon: item.icon,
        hideInMenu: true,
      },
    });
    registeredPluginRouteNames.add(routeName);
  }
}

export function usePluginFrontendInit(endpoint: string = '/admin') {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  const slotsStore = usePluginSlotsStore();
  const router = useRouter();

  async function initPluginSlots() {
    // Phase 1: 通过统一 /plugins/slots API 获取插槽数据（M51-T9）
    // 后端已按 scope + tenant 分配过滤，前端无需再过滤
    await slotsStore.fetchSlots(side);

    // Phase 2: 注册 standalone_pages 动态路由
    _registerStandalonePageRoutes(router, slotsStore);
  }

  onMounted(async () => {
    await initPluginSlots();
  });

  return { initPluginSlots };
}
