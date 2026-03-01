/**
 * NovusDoc Pro 插件前端入口
 *
 * 职责：
 * 1. 注册 i18n 翻译
 * 2. 注入协作相关样式
 * 3. 导出 CollabClient / Collaboration / CollaborationCursor 供 novusdoc useCollab 动态检测使用
 */
import type { NovusPluginSharedAPI } from './types';

import { zhCN, enUS } from './locales';
import { NDP_STYLES } from './styles';
import Collaboration from '@tiptap/extension-collaboration';
import CollaborationCursor from '@tiptap/extension-collaboration-cursor';

export { CollabClient } from './collab-client';
export type { CollabClientOptions, CollabUser } from './collab-client';
export { default as OnlineUsers } from './components/OnlineUsers.vue';
export { Collaboration, CollaborationCursor };

export function setup(): void {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI | undefined;

  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.novusdoc-pro', zhCN);
    shared.registerLocale('zh', 'plugin.novusdoc-pro', zhCN);
    shared.registerLocale('en-US', 'plugin.novusdoc-pro', enUS);
    shared.registerLocale('en', 'plugin.novusdoc-pro', enUS);
  }

  if (!document.getElementById('ndp-plugin-styles')) {
    const style = document.createElement('style');
    style.id = 'ndp-plugin-styles';
    style.textContent = NDP_STYLES;
    document.head.appendChild(style);
  }

  // 协作扩展通过 novusdoc 的 useCollab() composable 动态注入，
  // 不再通过 registerEditorExtension() 注入 marker 对象。
  // useCollab 检测到 NovusPlugin_novusdoc_pro.CollabClient 即启用协作。
}
