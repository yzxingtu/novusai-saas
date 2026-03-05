/**
 * DataForge Studio Plugin - Frontend entry point
 */
import type { NovusPluginSharedAPI } from './types';

import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import '@vue-flow/controls/dist/style.css';
import '@vue-flow/minimap/dist/style.css';

import { NCC_STYLES } from './styles';
import { enUS, zhCN } from './locales';

export function setup(): void {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI | undefined;

  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.novus-crud-code', zhCN);
    shared.registerLocale('zh', 'plugin.novus-crud-code', zhCN);
    shared.registerLocale('en-US', 'plugin.novus-crud-code', enUS);
    shared.registerLocale('en', 'plugin.novus-crud-code', enUS);
  }

  if (NCC_STYLES && !document.getElementById('ncc-plugin-styles')) {
    const style = document.createElement('style');
    style.id = 'ncc-plugin-styles';
    style.textContent = NCC_STYLES;
    document.head.appendChild(style);
  }
}

export { default as ProjectList } from './views/ProjectList.vue';
export { default as ProjectDetail } from './views/ProjectDetail.vue';
export { default as SchemaDesigner } from './views/SchemaDesigner.vue';
export { default as DataGrid } from './views/DataGrid.vue';
export { default as FormBuilder } from './views/FormBuilder.vue';
