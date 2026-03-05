/**
 * 插件插槽 Store (Pinia)
 *
 * 管理插件注册的 UI 插槽（顶栏 Widget、浮动面板、Dashboard 组件、设置页签、
 * 通知 UI、独立页面路由等）。
 *
 * M51-T9: fetchSlots 统一调用后端 GET /plugins/slots API（已按 scope 过滤），
 *         替代旧的"拉全量插件列表 + 读 manifest" 方案。
 */
import type { Component } from 'vue';

import { markRaw, ref } from 'vue';

import { preferences } from '@vben/preferences';

import { defineStore } from 'pinia';

import { getPluginSlotsApi } from '#/api/admin/plugin';
import { getTenantPluginSlotsApi } from '#/api/tenant/plugin';
import { loadPluginComponents } from '#/utils/plugin-loader';

export interface PluginSlotItem {
  pluginName: string;
  name: string;
  component: unknown;
  icon?: string;
  title?: string;
  sortOrder?: number;
  scope?: string;
  path?: string;
  hidden?: boolean;
  position?: string;
  grid?: Record<string, number>;
  event?: string;
  [key: string]: unknown;
}

export const usePluginSlotsStore = defineStore('plugin-slots', () => {
  const headerWidgets = ref<PluginSlotItem[]>([]);
  const floatingPanels = ref<PluginSlotItem[]>([]);
  const dashboardWidgets = ref<PluginSlotItem[]>([]);
  const settingsTabs = ref<PluginSlotItem[]>([]);
  /** 通知中心自定义 UI 组件（notification_ui slot） */
  const notificationUI = ref<PluginSlotItem[]>([]);
  /** 独立页面路由（standalone_pages slot，无侧边菜单） */
  const standalonePages = ref<PluginSlotItem[]>([]);
  /** 是否正在加载插槽数据 */
  const loading = ref(false);

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
  async function fetchSlots(side: 'admin' | 'tenant' = 'admin'): Promise<void> {
    loading.value = true;
    try {
      const resp =
        side === 'tenant'
          ? await getTenantPluginSlotsApi()
          : await getPluginSlotsApi();

      clearAll();
      const pluginStyles = resp.plugin_styles ?? {};

      // 按 slot 类型聚合需要加载的插件模块
      const pluginModCache: Record<string, Record<string, unknown>> = {};
      async function getPluginMod(
        pluginName: string,
      ): Promise<Record<string, unknown>> {
        if (!pluginModCache[pluginName]) {
          try {
            pluginModCache[pluginName] = await loadPluginComponents(
              pluginName,
              pluginStyles[pluginName] ?? [],
            );
          } catch {
            pluginModCache[pluginName] = {};
          }
        }
        return pluginModCache[pluginName];
      }

      const SLOT_MAP: Array<[keyof typeof resp, string]> = [
        ['header_widgets', 'headerWidgets'],
        ['dashboard_widgets', 'dashboardWidgets'],
        ['settings_tabs', 'settingsTabs'],
        ['floating_panels', 'floatingPanels'],
        ['notification_ui', 'notificationUI'],
        ['standalone_pages', 'standalonePages'],
      ];

      for (const [apiKey, storeKey] of SLOT_MAP) {
        const items =
          (resp as unknown as Record<string, typeof resp.header_widgets>)[
            apiKey
          ] ?? [];
        for (const slot of items) {
          let comp: Component | undefined;
          if (slot.component) {
            const mod = await getPluginMod(slot.plugin_name);
            comp = mod[slot.component] as Component | undefined;
            if (comp) comp = markRaw(comp);
          }
          registerSlot(storeKey, {
            pluginName: slot.plugin_name,
            name: slot.name,
            component: comp,
            title: _resolveTitle(slot.title),
            sortOrder: slot.sort_order ?? 100,
            scope: slot.scope,
            path: slot.path,
            icon: slot.icon,
            position: slot.position,
            grid: slot.grid,
            event: typeof slot.event === 'string' ? slot.event : slot.name,
            hidden: storeKey === 'standalonePages',
          });
        }
      }
    } catch (error: unknown) {
      console.warn('[PluginSlotsStore] fetchSlots failed:', error);
    } finally {
      loading.value = false;
    }
  }

  function unregisterPlugin(pluginName: string) {
    for (const list of [
      headerWidgets,
      floatingPanels,
      dashboardWidgets,
      settingsTabs,
      notificationUI,
      standalonePages,
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
    standalonePages.value = [];
  }

  function _getSlotList(slotType: string) {
    const map: Record<string, typeof headerWidgets> = {
      headerWidgets,
      floatingPanels,
      dashboardWidgets,
      settingsTabs,
      notificationUI,
      standalonePages,
    };
    return map[slotType];
  }

  function _resolveTitle(
    title: Record<string, string> | string | undefined,
  ): string | undefined {
    if (!title) return undefined;
    if (typeof title === 'string') return title;

    const locale = (preferences.app.locale ?? '').toLowerCase();
    const normalized = locale.replaceAll('_', '-');

    const exact =
      title[preferences.app.locale] ??
      title[normalized] ??
      title[normalized.replaceAll('-', '_')];
    if (exact) return exact;

    if (normalized.startsWith('zh')) {
      return (
        title['zh-CN'] ??
        title.zh ??
        title.zh_CN ??
        title.en ??
        Object.values(title)[0]
      );
    }
    if (normalized.startsWith('en')) {
      return (
        title.en ??
        title['en-US'] ??
        title.en_US ??
        title['zh-CN'] ??
        Object.values(title)[0]
      );
    }

    return title['zh-CN'] ?? title.en ?? Object.values(title)[0];
  }

  return {
    headerWidgets,
    floatingPanels,
    dashboardWidgets,
    settingsTabs,
    notificationUI,
    standalonePages,
    loading,
    registerSlot,
    unregisterPlugin,
    clearAll,
    fetchSlots,
  };
});
