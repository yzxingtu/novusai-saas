/**
 * 企业网盘插件前端入口
 */
import type { NovusPluginSharedAPI } from './types';

import NetDiskPage from './pages/NetDiskPage.vue';
import NetDiskAdminPage from './pages/NetDiskAdminPage.vue';
import NetdiskWidget from './NetdiskWidget.vue';
import { zhCN, enUS } from './locales';
import { NETDISK_STYLES } from './styles';

export function setup(): void {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI & {
      registerSlot?: (slot: string, component: unknown, options?: Record<string, unknown>) => void;
    } | undefined;

  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.netdisk', zhCN);
    shared.registerLocale('zh',    'plugin.netdisk', zhCN);
    shared.registerLocale('en-US', 'plugin.netdisk', enUS);
    shared.registerLocale('en',    'plugin.netdisk', enUS);
  }

  if (shared?.registerSlot) {
    shared.registerSlot('headerNavRight', NetdiskWidget, { order: 10, key: 'netdisk-nav' });
  }

  if (!document.getElementById('netdisk-plugin-styles')) {
    const style = document.createElement('style');
    style.id = 'netdisk-plugin-styles';
    style.textContent = NETDISK_STYLES;
    document.head.appendChild(style);
  }
}

export { NetDiskPage, NetDiskAdminPage, NetdiskWidget };
