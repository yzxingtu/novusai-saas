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

import { markRaw, onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { preferences } from '@vben/preferences';
import { useAccessStore } from '@vben/stores';

import { requestClient } from '#/utils/request';
import { usePluginSlotsStore } from '#/stores/plugin-slots';
import { usePluginExtensionsStore } from '#/stores/plugin-extensions';
import { loadPluginComponents, getBuiltinPluginNames } from '#/utils/plugin-loader';

interface PluginSlotDeclaration {
  name: string;
  component: string;
  sort_order?: number;
  icon?: string;
  title?: string | Record<string, string>;
  position?: string;
  scope?: string;
  grid?: Record<string, number>;
  path?: string;
  event?: string;
  [key: string]: unknown;
}

interface PluginManifestFrontend {
  header_widgets?: PluginSlotDeclaration[];
  floating_panels?: PluginSlotDeclaration[];
  dashboard_widgets?: PluginSlotDeclaration[];
  settings_tabs?: PluginSlotDeclaration[];
  standalone_pages?: PluginSlotDeclaration[];
  notification_ui?: PluginSlotDeclaration[];
  menus?: PluginSlotDeclaration[];
}

interface PluginListItem {
  name: string;
  status: string;
  scope?: string;
  manifest?: {
    scope?: string;
    extensions?: {
      frontend?: PluginManifestFrontend;
    };
  };
}

type EndpointSide = 'admin' | 'tenant';

const ADMIN_SCOPES = new Set(['admin_only', 'admin_and_all', 'admin_and_assigned']);
const TENANT_SCOPES = new Set(['all_tenants', 'assigned_tenants', 'admin_and_all', 'admin_and_assigned']);
const PLUGIN_ROUTE_PREFIXES = ['/admin/plugins/', '/tenant/plugins/'] as const;

function isValidPluginRoutePath(path: string): boolean {
  return PLUGIN_ROUTE_PREFIXES.some((prefix) => path.startsWith(prefix));
}

function shouldLoadForSide(scope: string | undefined, side: EndpointSide): boolean {
  if (!scope) return true;
  return side === 'admin' ? ADMIN_SCOPES.has(scope) : TENANT_SCOPES.has(scope);
}

function getPluginScope(plugin: PluginListItem): string | undefined {
  return plugin.scope || plugin.manifest?.scope;
}


/**
 * 将插件模块注册到插槽 Store
 */
/**
 * manifest key → store slot type 映射
 */
const SLOT_TYPE_MAP: Record<string, string> = {
  header_widgets: 'headerWidgets',
  floating_panels: 'floatingPanels',
  dashboard_widgets: 'dashboardWidgets',
  settings_tabs: 'settingsTabs',
  menus: 'sidebarMenus',
};

function registerPluginSlots(
  pluginName: string,
  frontend: PluginManifestFrontend,
  pluginMod: Record<string, unknown>,
  slotsStore: ReturnType<typeof usePluginSlotsStore>,
) {
  for (const [manifestKey, storeSlotType] of Object.entries(SLOT_TYPE_MAP)) {
    const items = frontend[manifestKey as keyof PluginManifestFrontend] as PluginSlotDeclaration[] | undefined;
    if (!items) continue;

    for (const item of items) {
      const comp = pluginMod[item.component] as Component | undefined;
      if (!comp) {
        console.error(
          `[PluginFrontendInit] Component '${item.component}' not exported by plugin '${pluginName}' (slot: ${storeSlotType})`,
        );
        continue;
      }

      slotsStore.registerSlot(storeSlotType, {
        pluginName,
        name: item.name,
        component: markRaw(comp),
        icon: item.icon,
        title: typeof item.title === 'string'
          ? item.title
          : item.title?.[preferences.app.locale] ?? item.title?.['zh-CN'] ?? item.title?.['en'],
        sortOrder: item.sort_order ?? 100,
        scope: item.scope,
        position: item.position,
        grid: item.grid,
        path: item.path,
        hidden: item.hidden === true,
      });
    }
  }
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
 * 将 sidebarMenus 中的插件页面注册为 VueRouter 动态路由，
 * 并将可见菜单追加到 accessStore.accessMenus 使其出现在侧边栏。
 *
 * 路由挂载为 TenantRoot / AdminRoot 的子路由（根据 path 前缀判断）。
 */
function registerPluginPageRoutes(
  router: Router,
  slotsStore: ReturnType<typeof usePluginSlotsStore>,
  side: EndpointSide = 'admin',
) {
  const menus = slotsStore.sidebarMenus;
  if (!menus || menus.length === 0) return;

  const menuEntries: MenuRecordRaw[] = [];

  for (const item of menus) {
    if (!item.path || !item.component) continue;

    if (!isValidPluginRoutePath(item.path)) {
      console.warn(
        `[PluginFrontendInit] Ignored invalid plugin route path '${item.path}', ` +
          `must start with '/admin/plugins/' or '/tenant/plugins/'`,
      );
      continue;
    }

    const isTenant = item.path.startsWith('/tenant/plugins/');
    const parentName = isTenant ? 'TenantRoot' : 'AdminRoot';

    // Strip prefix to make a relative child path
    const prefix = isTenant ? '/tenant/' : '/admin/';
    const childPath = item.path.startsWith(prefix)
      ? item.path.slice(prefix.length)
      : item.path.replace(/^\//, '');

    const routeName = `plugin-${item.pluginName}-${item.name}`;

    // Skip if already registered
    if (registeredPluginRouteNames.has(routeName)) continue;
    if (router.hasRoute(routeName)) continue;

    router.addRoute(parentName, {
      name: routeName,
      path: childPath,
      component: item.component as Component,
      meta: {
        title: item.title || item.name,
        icon: item.icon,
        hideInMenu: item.hidden === true,
        activePath: item.hidden ? item.path.replace(/\/:[^/]+$/, '') : undefined,
      },
    });
    registeredPluginRouteNames.add(routeName);

    // Collect visible menu entries (MenuRecordRaw format) for the sidebar
    // Only show menus matching the current side's path prefix
    const matchesSide = side === 'admin'
      ? item.path.startsWith('/admin/plugins/')
      : item.path.startsWith('/tenant/plugins/');
    if (!item.hidden && matchesSide) {
      menuEntries.push({
        name: item.title || item.name,
        path: item.path,
        icon: item.icon,
        order: item.sortOrder ?? 100,
        show: true,
      });
    }
  }

  // Cache for re-append after locale change
  cachedPluginMenuEntries = menuEntries;

  // Merge into accessStore
  _mergePluginMenusIntoAccessStore(menuEntries);
}

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
 */
export async function ensurePluginRoutes(router: Router, endpoint: string = '/admin') {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  if (_pluginRoutesReady && _pluginRoutesReadySide === side) return;

  const slotsStore = usePluginSlotsStore();
  const extensionsStore = usePluginExtensionsStore();

  // 端切换时清理旧端插件状态，避免路由名冲突导致新端菜单缺失
  removeAllPluginPageRoutes(router);
  slotsStore.clearAll();
  extensionsStore.clearAll();

  try {
    // 预加载内置插件模块
    const builtinNames = getBuiltinPluginNames();
    for (const name of builtinNames) {
      try { await loadPluginComponents(name); } catch { /* skip */ }
    }

    // 从 API 获取已启用插件列表
    const apiUrl = side === 'tenant' ? '/tenant/plugins' : '/admin/plugins';
    const resp = await requestClient.get<{ items?: PluginListItem[] }>(apiUrl, {
      params: { 'filter[status][eq]': 'enabled', 'page[size]': 50 },
    });
    const plugins: PluginListItem[] = resp?.items ?? [];

    for (const plugin of plugins) {
      const scope = getPluginScope(plugin);
      if (!shouldLoadForSide(scope, side)) continue;
      const frontend = plugin.manifest?.extensions?.frontend;
      if (!frontend) continue;

      let pluginMod: Record<string, unknown>;
      try {
        pluginMod = await loadPluginComponents(plugin.name);
      } catch {
        continue;
      }
      registerPluginSlots(plugin.name, frontend, pluginMod, slotsStore);
    }

    // 注册插件页面路由
    registerPluginPageRoutes(router, slotsStore, side);
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
 * 1. 清空当前所有插槽
 * 2. 卸载所有已加载的插件模块
 * 3. 重新从 API 获取已启用插件列表并注册插槽
 */
export async function refreshPluginSlots(endpoint: string = '/admin', router?: Router) {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  const slotsStore = usePluginSlotsStore();
  const extensionsStore = usePluginExtensionsStore();

  // Clean up previously registered plugin routes
  if (router) {
    removeAllPluginPageRoutes(router);
  }

  slotsStore.clearAll();
  extensionsStore.clearAll();

  try {
    // admin 端从 /admin/plugins 获取，tenant 端从 /tenant/plugins 获取（后端按 scope + 租户分配过滤）
    const apiUrl = side === 'tenant' ? '/tenant/plugins' : '/admin/plugins';
    const resp = await requestClient.get<{
      items?: PluginListItem[];
    }>(apiUrl, {
      params: {
        'filter[status][eq]': 'enabled',
        'page[size]': 50,
      },
    });

    const plugins: PluginListItem[] = resp?.items ?? [];

    for (const plugin of plugins) {
      const scope = getPluginScope(plugin);
      if (!shouldLoadForSide(scope, side)) continue;

      const frontend = plugin.manifest?.extensions?.frontend;
      if (!frontend) continue;

      let pluginMod: Record<string, unknown>;
      try {
        pluginMod = await loadPluginComponents(plugin.name);
      } catch {
        continue;
      }

      registerPluginSlots(plugin.name, frontend, pluginMod, slotsStore);
    }

    // Register plugin page routes after all slots are loaded
    if (router) {
      registerPluginPageRoutes(router, slotsStore, side);
    }
    _pluginRoutesReady = true;
    _pluginRoutesReadySide = side;
  } catch (err: unknown) {
    console.error('[refreshPluginSlots] Failed:', err);
  }
}

export function usePluginFrontendInit(endpoint: string = '/admin') {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  const slotsStore = usePluginSlotsStore();
  const router = useRouter();

  async function initPluginSlots() {
    // ── Phase 1: 预加载内置插件模块（只加载 + 调 setup，不注册插槽） ──
    const builtinNames = getBuiltinPluginNames();
    for (const name of builtinNames) {
      try {
        await loadPluginComponents(name);
      } catch {
        // 内置插件加载失败，静默跳过
      }
    }

    // ── Phase 2: 从 API 获取已启用插件列表，按 scope 过滤后注册插槽 ──
    let apiSucceeded = false;
    try {
      const apiUrl = side === 'tenant' ? '/tenant/plugins' : '/admin/plugins';
      const resp = await requestClient.get<{
        items?: PluginListItem[];
      }>(apiUrl, {
        params: {
          'filter[status][eq]': 'enabled',
          'page[size]': 50,
        },
      });

      const plugins: PluginListItem[] = resp?.items ?? [];
      apiSucceeded = true;

      for (const plugin of plugins) {
        // ★ Scope 过滤：只加载当前端允许的插件
        const scope = getPluginScope(plugin);
        if (!shouldLoadForSide(scope, side)) continue;

        const frontend = plugin.manifest?.extensions?.frontend;
        if (!frontend) continue;

        let pluginMod: Record<string, unknown>;
        try {
          pluginMod = await loadPluginComponents(plugin.name);
        } catch (loadErr: unknown) {
          console.error(`[PluginFrontendInit] Failed to load plugin '${plugin.name}':`, loadErr);
          continue;
        }

        registerPluginSlots(plugin.name, frontend, pluginMod, slotsStore);
      }

      // ★ Register plugin page routes after all slots are loaded
      registerPluginPageRoutes(router, slotsStore, side);
    } catch (err: unknown) {
      console.error('[PluginFrontendInit] Failed to fetch plugins from API:', err);
    }

    // ── Phase 3: API 失败兜底（dev 模式后端未启动时） ──
    if (!apiSucceeded && builtinNames.length > 0) {
      for (const name of builtinNames) {
        try {
          const pluginMod = await loadPluginComponents(name);
          for (const [exportName, exportValue] of Object.entries(pluginMod)) {
            if (
              exportName[0] &&
              exportName[0] === exportName[0].toUpperCase() &&
              exportName !== 'default' &&
              typeof exportValue === 'object' &&
              exportValue !== null
            ) {
              slotsStore.registerSlot('headerWidgets', {
                pluginName: name,
                name: `${name}-${exportName}`,
                component: markRaw(exportValue as Component),
                sortOrder: 100,
              });
            }
          }
        } catch {
          // 静默跳过
        }
      }
    }
  }

  onMounted(async () => {
    await initPluginSlots();
  });

  return { initPluginSlots };
}
