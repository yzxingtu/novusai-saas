/**
 * NovusDoc Pro 插件前端入口
 *
 * 职责：
 * 1. 注册 i18n 翻译
 * 2. 注入协作相关样式
 * 3. 向 novusdoc 编辑器注入 Collaboration/CollaborationCursor 扩展
 * 4. 导出 CollabClient 供编辑器页面使用
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

  // 向 novusdoc 编辑器注入协作扩展（如果 novusdoc 已加载）
  _injectCollabExtensions();
}

/**
 * 尝试向 novusdoc 编辑器扩展系统注入 Collaboration 相关扩展。
 *
 * novusdoc 通过 registerEditorExtension() 开放扩展注入点，
 * novusdoc-pro 在 setup() 时注入 Collaboration 和 CollaborationCursor。
 *
 * 注意：实际的 Y.Doc 实例在编辑器创建时由 CollabClient 提供，
 * 此处仅注册扩展工厂，编辑器初始化时会调用 getAllExtensions() 获取。
 */
function _injectCollabExtensions(): void {
  try {
    // 通过宿主插件加载系统获取 novusdoc 模块
    const novusdocMod = (window as unknown as Record<string, Record<string, unknown>>)
      .NovusPlugin_novusdoc;

    if (!novusdocMod?.registerEditorExtension) {
      // novusdoc 尚未加载 — pro 加载顺序可能在 novusdoc 之后
      // 延迟重试一次
      setTimeout(() => {
        const mod = (window as unknown as Record<string, Record<string, unknown>>)
          .NovusPlugin_novusdoc;
        if (mod?.registerEditorExtension) {
          _doInject(mod.registerEditorExtension as (ext: unknown) => void);
        }
      }, 500);
      return;
    }

    _doInject(novusdocMod.registerEditorExtension as (ext: unknown) => void);
  } catch (e) {
    console.warn('[novusdoc-pro] Failed to inject collab extensions:', e);
  }
}

function _doInject(registerFn: (ext: unknown) => void): void {
  // Collaboration 和 CollaborationCursor 扩展需要 Y.Doc，
  // 但在 setup() 时还没有具体文档的 Y.Doc 实例。
  // 这里注册一个占位标记，实际扩展创建在编辑器组件中完成。
  // 编辑器页面检测到 pro 已加载后，使用 CollabClient.doc 创建真正的扩展。
  registerFn({
    name: 'novusdoc-pro-collab-marker',
    type: 'extension',
    // 标记：告诉编辑器页面 pro 协作扩展已就绪
    _proCollabReady: true,
  });
}
