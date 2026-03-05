/**
 * Storage Migration Plugin - Frontend entry point
 *
 * Exports page component for the plugin system to register as a standalone page.
 */
import type { NovusPluginSharedAPI } from './types';

import { zhCN, enUS } from './locales';

export function setup(): void {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI | undefined;

  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.storage-migration', zhCN);
    shared.registerLocale('zh', 'plugin.storage-migration', zhCN);
    shared.registerLocale('en-US', 'plugin.storage-migration', enUS);
    shared.registerLocale('en', 'plugin.storage-migration', enUS);

    // 兼容旧 key（历史页面仍使用 admin.storageMigration.*）
    shared.registerLocale('zh-CN', 'admin.storageMigration', zhCN);
    shared.registerLocale('zh', 'admin.storageMigration', zhCN);
    shared.registerLocale('en-US', 'admin.storageMigration', enUS);
    shared.registerLocale('en', 'admin.storageMigration', enUS);
  }
}

export { default as StorageMigrationPage } from './StorageMigrationPage.vue';
