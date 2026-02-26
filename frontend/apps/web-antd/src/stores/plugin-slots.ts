/**
 * 插件插槽 Store (Pinia)
 *
 * 管理插件注册的 UI 插槽（顶栏 Widget、浮动面板、Dashboard 组件、设置页签等）。
 * 布局组件通过此 Store 渲染插件 UI。
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';

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
  [key: string]: unknown;
}

export const usePluginSlotsStore = defineStore('plugin-slots', () => {
  const headerWidgets = ref<PluginSlotItem[]>([]);
  const floatingPanels = ref<PluginSlotItem[]>([]);
  const dashboardWidgets = ref<PluginSlotItem[]>([]);
  const settingsTabs = ref<PluginSlotItem[]>([]);
  const sidebarMenus = ref<PluginSlotItem[]>([]);

  function registerSlot(
    slotType: string,
    item: PluginSlotItem,
  ) {
    const target = _getSlotList(slotType);
    if (target) {
      const exists = target.value.some(
        (i) => i.pluginName === item.pluginName && i.name === item.name,
      );
      if (exists) return;
      target.value.push(item);
      target.value.sort((a, b) => (a.sortOrder ?? 100) - (b.sortOrder ?? 100));
    }
  }

  function unregisterPlugin(pluginName: string) {
    for (const list of [headerWidgets, floatingPanels, dashboardWidgets, settingsTabs, sidebarMenus]) {
      list.value = list.value.filter((item) => item.pluginName !== pluginName);
    }
  }

  function clearAll() {
    headerWidgets.value = [];
    floatingPanels.value = [];
    dashboardWidgets.value = [];
    settingsTabs.value = [];
    sidebarMenus.value = [];
  }

  function _getSlotList(slotType: string) {
    const map: Record<string, typeof headerWidgets> = {
      headerWidgets,
      floatingPanels,
      dashboardWidgets,
      settingsTabs,
      sidebarMenus,
    };
    return map[slotType];
  }

  return {
    headerWidgets,
    floatingPanels,
    dashboardWidgets,
    settingsTabs,
    sidebarMenus,
    registerSlot,
    unregisterPlugin,
    clearAll,
  };
});
