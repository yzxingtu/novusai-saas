/**
 * 插件前端初始化 Composable
 *
 * 双模式加载：
 *   1. 内置插件（dev/build 时 Vite 编译）→ 从 BUILTIN_PLUGINS 直接加载，无需 API
 *   2. 运行时插件（生产环境安装）→ 通过 API 获取列表 + UMD 动态加载
 *
 * Scope 过滤规则：
 *   - admin_only         → 仅 admin 端加载前端
 *   - all_tenants        → 仅 tenant 端加载前端
 *   - assigned_tenants   → 仅被分配的 tenant 端加载前端
 *   - admin_and_all      → admin + 所有 tenant 端加载前端
 *   - admin_and_assigned → admin + 被分配的 tenant 端加载前端
 */

import type { MenuRecordRaw } from '@vben/types';
import type { Component } from 'vue';
import type { Router } from 'vue-router';

import { onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { useAccessStore } from '@vben/stores';

import { usePluginSlotsStore } from '#/stores/plugin-slots';
import { usePluginExtensionsStore } from '#/stores/plugin-extensions';
import { loadPluginComponents, getBuiltinPluginNames } from '#/utils/plugin-loader';

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
 * 缓存插件生成的 MenuRecordRaw 条目，供 locale 切换后重新追加
 */
let cachedPluginMenuEntries: MenuRecordRaw[] = [];


/**
 * 将插件菜单条目去重合并到 accessStore.accessMenus
 */
function _mergePluginMenusIntoAccessStore(entries: MenuRecordRaw[]) {
  if (entries.length === 0) return;
  const accessStore = useAccessStore();
  const currentMenus = accessStore.accessMenus;
  const existingPaths = new Set(currentMenus.map((m) => m.path));
  const newMenus = entries.filter((m) => !existingPaths.has(m.path));
  if (newMenus.length > 0) {
    accessStore.setAccessMenus([...currentMenus, ...newMenus]);
  }
}

/**
 * 将缓存的插件菜单重新追加到 accessStore（在 locale 切换 / 菜单重新生成后调用）
 */
export function appendPluginMenusToAccessStore() {
  if (cachedPluginMenuEntries.length > 0) {
    _mergePluginMenusIntoAccessStore(cachedPluginMenuEntries);
  }
}

/**
 * 移除所有插件注册的动态路由，并从 accessStore 清除插件菜单
 */
function removeAllPluginPageRoutes(router: Router) {
  for (const name of registeredPluginRouteNames) {
    if (router.hasRoute(name)) {
      router.removeRoute(name);
    }
  }
  registeredPluginRouteNames.clear();

  // Remove cached plugin menus from accessStore
  if (cachedPluginMenuEntries.length > 0) {
    const accessStore = useAccessStore();
    const pluginPaths = new Set(cachedPluginMenuEntries.map((m) => m.path));
    const filtered = accessStore.accessMenus.filter(
      (m) => !pluginPaths.has(m.path),
    );
    accessStore.setAccessMenus(filtered);
    cachedPluginMenuEntries = [];
  }
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
export async function ensurePluginRoutes(router: Router, endpoint: string = '/admin') {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  if (_pluginRoutesReady && _pluginRoutesReadySide === side) return;

  const slotsStore = usePluginSlotsStore();
  const extensionsStore = usePluginExtensionsStore();

  removeAllPluginPageRoutes(router);
  slotsStore.clearAll();
  extensionsStore.clearAll();

  try {
    // 预加载内置插件模块（dev 模式让 setup() 注册 i18n）
    const builtinNames = getBuiltinPluginNames();
    for (const name of builtinNames) {
      try { await loadPluginComponents(name); } catch { /* skip */ }
    }

    // 统一通过 /plugins/slots API 获取插槽数据（与 usePluginFrontendInit 同路径）
    await slotsStore.fetchSlots(side);

    // 注册 standalonePages 动态路由
    _registerStandalonePageRoutes(router, slotsStore);

    _pluginRoutesReady = true;
    _pluginRoutesReadySide = side;
  } catch (err: unknown) {
    console.error('[ensurePluginRoutes] Failed:', err);
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
export async function refreshPluginSlots(endpoint: string = '/admin', router?: Router) {
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

    if (registeredPluginRouteNames.has(routeName) || router.hasRoute(routeName)) continue;

    router.addRoute(parentName, {
      name: routeName,
      path: childPath,
      component: item.component as Component,
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
    // Phase 1: 预加载内置插件模块（dev 模式：让 setup() 注册 i18n）
    const builtinNames = getBuiltinPluginNames();
    for (const name of builtinNames) {
      try { await loadPluginComponents(name); } catch { /* skip */ }
    }

    // Phase 2: 通过统一 /plugins/slots API 获取插槽数据（M51-T9）
    // 后端已按 scope + tenant 分配过滤，前端无需再过滤
    await slotsStore.fetchSlots(side);

    // Phase 3: 注册 standalone_pages 动态路由
    _registerStandalonePageRoutes(router, slotsStore);
  }

  onMounted(async () => {
    await initPluginSlots();
  });

  return { initPluginSlots };
}
