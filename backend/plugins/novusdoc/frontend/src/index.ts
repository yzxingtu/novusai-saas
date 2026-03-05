/**
 * NovusDoc 插件前端入口
 *
 * 禁止 export default — 插件 index.ts 只使用命名导出
 * 禁止 import from '#/xxx' — 使用 @novus/plugin-shared
 */
import type { NovusPluginSharedAPI } from './types';

import { zhCN, enUS } from './locales';
import './novusdoc.css';

export function setup(): void {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI | undefined;

  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.novusdoc', zhCN);
    shared.registerLocale('zh', 'plugin.novusdoc', zhCN);
    shared.registerLocale('en-US', 'plugin.novusdoc', enUS);
    shared.registerLocale('en', 'plugin.novusdoc', enUS);
  }

}

// Phase A: 页面组件（通过插件菜单路由加载）
export { default as DocumentList } from './views/DocumentList.vue';
export { default as DocumentEditor } from './views/DocumentEditor.vue';
