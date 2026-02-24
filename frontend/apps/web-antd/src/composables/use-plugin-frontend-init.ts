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

import type { Component } from 'vue';

import { markRaw, onMounted } from 'vue';

import { requestClient } from '#/utils/request';
import { usePluginSlotsStore } from '#/stores/plugin-slots';
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
        title: typeof item.title === 'string' ? item.title : item.title?.['zh-CN'] ?? item.title?.['en'],
        sortOrder: item.sort_order ?? 100,
        scope: item.scope,
        position: item.position,
        grid: item.grid,
      });
    }
  }
}

/**
 * 独立刷新插件前端插槽（可在启用/禁用/卸载后调用，无需 F5）
 *
 * 1. 清空当前所有插槽
 * 2. 卸载所有已加载的插件模块
 * 3. 重新从 API 获取已启用插件列表并注册插槽
 */
export async function refreshPluginSlots(endpoint: string = '/admin') {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  const slotsStore = usePluginSlotsStore();

  slotsStore.clearAll();

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
  } catch (err: unknown) {
    console.error('[refreshPluginSlots] Failed:', err);
  }
}

export function usePluginFrontendInit(endpoint: string = '/admin') {
  const side: EndpointSide = endpoint.includes('tenant') ? 'tenant' : 'admin';
  const slotsStore = usePluginSlotsStore();

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
        } catch {
          continue;
        }

        registerPluginSlots(plugin.name, frontend, pluginMod, slotsStore);
      }
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

  onMounted(() => {
    initPluginSlots();
  });

  return { initPluginSlots };
}
