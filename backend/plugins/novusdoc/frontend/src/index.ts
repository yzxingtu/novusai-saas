/**
 * NovusDoc plugin frontend entry point
 * NovusDoc 插件前端入口
 */
import type { NovusPluginSharedAPI } from './types';

import DocumentList from './views/DocumentList.vue';
import DocumentEditor from './views/DocumentEditor.vue';
import { zhCN, enUS } from './locales';
import { NOVUSDOC_STYLES } from './styles';

export function setup(): void {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI | undefined;

  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.novusdoc', zhCN);
    shared.registerLocale('zh', 'plugin.novusdoc', zhCN);
    shared.registerLocale('en-US', 'plugin.novusdoc', enUS);
    shared.registerLocale('en', 'plugin.novusdoc', enUS);
  }

  if (!document.getElementById('novusdoc-plugin-styles')) {
    const style = document.createElement('style');
    style.id = 'novusdoc-plugin-styles';
    style.textContent = NOVUSDOC_STYLES;
    document.head.appendChild(style);
  }
}

export {
  DocumentList as NovusDocPage,
  DocumentList as NovusDocAdminPage,
  DocumentEditor as NovusDocEditor,
  DocumentEditor as NovusDocAdminEditor,
};
