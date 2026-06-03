import type { Component } from 'vue';

import { zhCN, enUS } from './locales';
import StorageBillingAdminView from './views/admin/index.vue';
import StorageBillingTenantView from './views/tenant/index.vue';

interface SharedApi {
  getAccessCodes?: () => string[];
  hasAccessByCodes?: (codes: string[]) => boolean;
  registerLocale?: (
    locale: string,
    prefix: string,
    messages: Record<string, unknown>,
  ) => void;
}

function getShared(): SharedApi | undefined {
  return (window as unknown as { NovusPluginShared?: SharedApi }).NovusPluginShared;
}

export function setup(): void {
  const shared = getShared();
  if (!shared?.registerLocale) {
    return;
  }

  shared.registerLocale('zh-CN', 'plugin.storage-billing', zhCN);
  shared.registerLocale('zh', 'plugin.storage-billing', zhCN);
  shared.registerLocale('en-US', 'plugin.storage-billing', enUS);
  shared.registerLocale('en', 'plugin.storage-billing', enUS);
}

export const StorageBillingAdminPage = StorageBillingAdminView as Component;
export const StorageBillingTenantPage = StorageBillingTenantView as Component;
