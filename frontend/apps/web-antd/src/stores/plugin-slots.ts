/**
 * 插件插槽 Store (Pinia)
 *
 * 管理插件注册的 UI 插槽（顶栏 Widget、浮动面板、Dashboard 组件、设置页签、
 * 通知 UI、独立页面路由等）。
 *
 * M51-T9: fetchSlots 统一调用后端 GET /plugins/slots API（已按 scope 过滤），
 *         替代旧的"拉全量插件列表 + 读 manifest" 方案。
 * M60: 前端运行态由 loader 自行读取 release manifest，不再依赖 slots API 回传 CSS 列表。
 */
import type { Component } from 'vue';

import { markRaw, ref } from 'vue';

import { ensureLucideIconCatalogRegistered } from '@vben/icons';
import {
  normalizeRouteTitleLocaleMap,
  resolveRouteTitleLocaleMap,
} from '@vben/utils';

import { defineStore } from 'pinia';

import { getPluginSlotsApi } from '#/api/admin/plugin';
import { getTenantPluginSlotsApi } from '#/api/tenant/plugin';
import {
  getPluginRuntimeCacheKey,
  loadPluginComponents,
  unloadPlugin,
} from '#/utils/plugin-loader';

export interface PluginSlotAI {
  disabled_capabilities?: string[];
  disabled_operations?: string[];
  mode?: 'context_only' | 'disabled' | 'operate';
  page_context_key?: string;
}

const PLUGIN_AI_MODES = new Set<NonNullable<PluginSlotAI['mode']>>([
  'context_only',
  'disabled',
  'operate',
]);

export interface PluginSlotItem {
  pluginName: string;
  name: string;
  component: unknown;
  icon?: string;
  title?: string;
  titleLocaleMap?: Record<string, string>;
  accessCodes?: string[];
  sortOrder?: number;
  scope?: string;
  path?: string;
  hidden?: boolean;
  position?: string;
  grid?: Record<string, number>;
  event?: string;
  ai?: PluginSlotAI;
  [key: string]: unknown;
}

export interface PluginSlotFetchFailure {
  componentName?: string;
  message: string;
  name: string;
  path?: string;
  pluginName: string;
}

export interface PluginSlotFetchResult {
  pageFailures: PluginSlotFetchFailure[];
}

export interface PluginSlotFetchOptions {
  forceReload?: boolean;
}

type EndpointSide = 'admin' | 'tenant';

type PluginSlotSnapshot = {
  dashboardWidgets: PluginSlotItem[];
  floatingPanels: PluginSlotItem[];
  headerWidgets: PluginSlotItem[];
  notificationUI: PluginSlotItem[];
  pages: PluginSlotItem[];
  settingsTabs: PluginSlotItem[];
};

export const usePluginSlotsStore = defineStore('plugin-slots', () => {
  const headerWidgets = ref<PluginSlotItem[]>([]);
  const floatingPanels = ref<PluginSlotItem[]>([]);
  const dashboardWidgets = ref<PluginSlotItem[]>([]);
  const settingsTabs = ref<PluginSlotItem[]>([]);
  /** 通知中心自定义 UI 组件（notification_ui slot） / Notification center UI slot */
  const notificationUI = ref<PluginSlotItem[]>([]);
  /** 插件页面路由（pages slot，无侧边菜单） / Plugin page routes */
  const pages = ref<PluginSlotItem[]>([]);
  /** 是否正在加载插槽数据 / Whether slot data is loading */
  const loading = ref(false);
  let activeFetchCount = 0;
  let activeFetchPromise: null | Promise<PluginSlotFetchResult> = null;
  let activeFetchSide: EndpointSide | null = null;
  let latestFetchRequestId = 0;

  function registerSlot(slotType: string, item: PluginSlotItem) {
    const target = _getSlotList(slotType);
    if (!target) return;
    const exists = target.value.some(
      (i) => i.pluginName === item.pluginName && i.name === item.name,
    );
    if (exists) return;
    target.value.push(item);
    target.value.sort((a, b) => (a.sortOrder ?? 100) - (b.sortOrder ?? 100));
  }

  /**
   * M51-T9: 调用后端 GET /plugins/slots 统一获取当前端已启用插件的插槽数据。
   *
   * - 后端已按 scope + tenant_assignment 过滤，前端无需再过滤。
   * - 对每个有 component 的 slot，加载插件 UMD bundle 并提取组件。
   * - 幂等：先 clearAll 再注册，避免重复。
   */
  async function fetchSlots(
    side: EndpointSide = 'admin',
    options: PluginSlotFetchOptions = {},
  ): Promise<PluginSlotFetchResult> {
    if (activeFetchPromise && activeFetchSide === side) {
      return activeFetchPromise;
    }

    const requestId = ++latestFetchRequestId;
    activeFetchCount += 1;
    loading.value = activeFetchCount > 0;

    const task = (async (): Promise<PluginSlotFetchResult> => {
      const pageFailures: PluginSlotFetchFailure[] = [];
      try {
        const resp =
          side === 'tenant'
            ? await getTenantPluginSlotsApi()
            : await getPluginSlotsApi();

        const hasPluginFrontendSlots = Object.values(resp).some(
          (items) => Array.isArray(items) && items.length > 0,
        );
        if (hasPluginFrontendSlots) {
          await ensureLucideIconCatalogRegistered();
        }

        const nextSnapshot = _createEmptySnapshot();
        const pluginModCache = new Map<string, Record<string, unknown>>();
        const reloadedPlugins = new Set<string>();
        async function getPluginMod(
          pluginName: string,
          frontendRuntime?: {
            dev_entry?: string;
            release_manifest?: string;
          },
        ): Promise<Record<string, unknown>> {
          const pluginCacheKey = getPluginRuntimeCacheKey(
            pluginName,
            frontendRuntime,
            { endpoint: side },
          );
          if (!pluginModCache.has(pluginCacheKey)) {
            try {
              if (options.forceReload && !reloadedPlugins.has(pluginName)) {
                unloadPlugin(pluginName, { endpoint: side });
                reloadedPlugins.add(pluginName);
              }
              pluginModCache.set(
                pluginCacheKey,
                await loadPluginComponents(pluginName, frontendRuntime, {
                  endpoint: side,
                }),
              );
            } catch (error) {
              console.warn(
                `[PluginSlotsStore] failed to load plugin '${pluginName}' for '${pluginCacheKey}'`,
                error,
              );
              pluginModCache.set(pluginCacheKey, {});
            }
          }
          return pluginModCache.get(pluginCacheKey) ?? {};
        }

        const SLOT_MAP: Array<[keyof typeof resp, keyof PluginSlotSnapshot]> = [
          ['header_widgets', 'headerWidgets'],
          ['dashboard_widgets', 'dashboardWidgets'],
          ['settings_tabs', 'settingsTabs'],
          ['floating_panels', 'floatingPanels'],
          ['notification_ui', 'notificationUI'],
          ['pages', 'pages'],
        ];

        for (const [apiKey, storeKey] of SLOT_MAP) {
          const items =
            (resp as unknown as Record<string, typeof resp.header_widgets>)[
              apiKey
            ] ?? [];
          for (const slot of items) {
            let comp: Component | undefined;
            if (slot.component) {
              const mod = await getPluginMod(
                slot.plugin_name,
                slot.frontend_runtime,
              );
              comp = mod[slot.component] as Component | undefined;
              if (comp) {
                comp = markRaw(comp);
              } else if (storeKey === 'pages') {
                pageFailures.push({
                  componentName: slot.component,
                  message: `Plugin page component '${slot.component}' was not exported by plugin '${slot.plugin_name}'`,
                  name: slot.name,
                  path: slot.path,
                  pluginName: slot.plugin_name,
                });
              } else {
                console.warn(
                  `[PluginSlotsStore] plugin component '${slot.component}' missing for slot '${slot.plugin_name}:${slot.name}'`,
                );
                continue;
              }
            }
            _pushSnapshotItem(nextSnapshot[storeKey], {
              ...(slot.ai
                ? {
                    ai: {
                      ...(PLUGIN_AI_MODES.has(
                        slot.ai.mode as NonNullable<PluginSlotAI['mode']>,
                      )
                        ? {
                            mode: slot.ai.mode as NonNullable<
                              PluginSlotAI['mode']
                            >,
                          }
                        : {}),
                      ...(slot.ai.page_context_key
                        ? { page_context_key: slot.ai.page_context_key }
                        : {}),
                      ...(Array.isArray(slot.ai.disabled_capabilities) &&
                      slot.ai.disabled_capabilities.length > 0
                        ? {
                            disabled_capabilities:
                              slot.ai.disabled_capabilities,
                          }
                        : {}),
                      ...(Array.isArray(slot.ai.disabled_operations) &&
                      slot.ai.disabled_operations.length > 0
                        ? { disabled_operations: slot.ai.disabled_operations }
                        : {}),
                    } satisfies PluginSlotAI,
                  }
                : {}),
              pluginName: slot.plugin_name,
              name: slot.name,
              component: comp,
              title: _resolveTitle(slot.title),
              titleLocaleMap: normalizeRouteTitleLocaleMap(slot.title),
              accessCodes:
                Array.isArray(slot.access_codes) && slot.access_codes.length > 0
                  ? slot.access_codes.filter(
                      (code): code is string =>
                        typeof code === 'string' && code.trim().length > 0,
                    )
                  : undefined,
              sortOrder: slot.sort_order ?? 100,
              scope: slot.scope,
              path: slot.path,
              icon: slot.icon,
              position: slot.position,
              grid: slot.grid,
              event: typeof slot.event === 'string' ? slot.event : slot.name,
              hidden: storeKey === 'pages',
            });
          }
        }

        if (pageFailures.length > 0) {
          throw new Error(
            `Plugin page registration failed for ${pageFailures.length} page(s): ${pageFailures
              .map((failure) => `${failure.pluginName}:${failure.name}`)
              .join(', ')}`,
          );
        }

        if (requestId === latestFetchRequestId) {
          _replaceSnapshot(nextSnapshot);
        }
        return { pageFailures };
      } catch (error: unknown) {
        console.warn('[PluginSlotsStore] fetchSlots failed:', error);
        throw error;
      } finally {
        activeFetchCount = Math.max(0, activeFetchCount - 1);
        loading.value = activeFetchCount > 0;
      }
    })();

    activeFetchPromise = task;
    activeFetchSide = side;

    try {
      return await task;
    } finally {
      if (activeFetchPromise === task) {
        activeFetchPromise = null;
        activeFetchSide = null;
      }
    }
  }

  function unregisterPlugin(pluginName: string) {
    for (const list of [
      headerWidgets,
      floatingPanels,
      dashboardWidgets,
      settingsTabs,
      notificationUI,
      pages,
    ]) {
      list.value = list.value.filter((item) => item.pluginName !== pluginName);
    }
  }

  function clearAll() {
    headerWidgets.value = [];
    floatingPanels.value = [];
    dashboardWidgets.value = [];
    settingsTabs.value = [];
    notificationUI.value = [];
    pages.value = [];
  }

  function _getSlotList(slotType: string) {
    const map: Record<string, typeof headerWidgets> = {
      headerWidgets,
      floatingPanels,
      dashboardWidgets,
      settingsTabs,
      notificationUI,
      pages,
    };
    return map[slotType];
  }

  function _createEmptySnapshot(): PluginSlotSnapshot {
    return {
      dashboardWidgets: [],
      floatingPanels: [],
      headerWidgets: [],
      notificationUI: [],
      pages: [],
      settingsTabs: [],
    };
  }

  function _pushSnapshotItem(target: PluginSlotItem[], item: PluginSlotItem) {
    const exists = target.some(
      (existing) =>
        existing.pluginName === item.pluginName && existing.name === item.name,
    );
    if (exists) return;
    target.push(item);
    target.sort((a, b) => (a.sortOrder ?? 100) - (b.sortOrder ?? 100));
  }

  function _replaceSnapshot(snapshot: PluginSlotSnapshot) {
    headerWidgets.value = snapshot.headerWidgets;
    floatingPanels.value = snapshot.floatingPanels;
    dashboardWidgets.value = snapshot.dashboardWidgets;
    settingsTabs.value = snapshot.settingsTabs;
    notificationUI.value = snapshot.notificationUI;
    pages.value = snapshot.pages;
  }

  function _resolveTitle(
    title: Record<string, string> | string | undefined,
  ): string | undefined {
    if (!title) return undefined;
    if (typeof title === 'string') return title;
    return resolveRouteTitleLocaleMap(normalizeRouteTitleLocaleMap(title));
  }

  return {
    headerWidgets,
    floatingPanels,
    dashboardWidgets,
    settingsTabs,
    notificationUI,
    pages,
    loading,
    registerSlot,
    unregisterPlugin,
    clearAll,
    fetchSlots,
  };
});
