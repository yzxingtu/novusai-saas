/**
 * Plugin shared dependency exposure
 * 插件共享依赖暴露
 *
 * Mounts host dependencies commonly used by plugins onto window for UMD external references.
 * Must call exposePluginShared() early in bootstrap.
 * 将插件常用的宿主依赖挂载到 window，供插件 UMD 包作为 external 引用。
 * 必须在 bootstrap 早期调用 exposePluginShared()。
 *
 * Plugin vite.config rollupOptions.external mapping:
 * 插件 vite.config 中 rollupOptions.external 映射:
 *   'vue'                -> window.Vue
 *   'vue-router'         -> window.VueRouter
 *   'ant-design-vue'     -> window.AntDesignVue
 *   '@vben/common-ui'    -> window.VbenCommonUi
 *   '@vben/icons'        -> window.VbenIcons
 *   '@novus/plugin-shared' -> window.NovusPluginShared
 */

import * as Vue from 'vue';
import * as VueRouter from 'vue-router';


import * as VbenCommonUi from '@vben/common-ui';
import * as VbenIcons from '@vben/icons';
import { IconifyIcon } from '@vben/icons';
import { i18n } from '@vben/locales';
import { useUserStore } from '@vben/stores';

import * as AntDesignVue from 'ant-design-vue';

import {
  listPageOperations,
  registerPageContext,
  registerPageOperations,
} from '#/components/business/ai-slide-panel';
import {
  mountRichTextEditor,
  RichTextEditor,
} from '#/components/business/rich-text-editor';
import { $t } from '#/locales';
import { getCurrentEndpoint } from '#/router/access';
import { router } from '#/router';
import { TokenStorage } from '#/store/shared/token-storage';
import { usePluginExtensionsStore } from '#/stores/plugin-extensions';
import { usePluginSlotsStore } from '#/stores/plugin-slots';
import { requestClient } from '#/utils/request';

// Re-export for dev mode: plugins import { $t, IconifyIcon, ... } from '@novus/plugin-shared'
export {
  $t,
  getAuthToken,
  getCurrentUser,
  IconifyIcon,
  listPageOperations,
  mountRichTextEditor,
  registerPageContext,
  registerPageOperations,
  requestClient,
  RichTextEditor,
  usePluginExtensionsStore,
  usePluginSlotsStore,
};

/**
 * Get current endpoint (admin/tenant/user) JWT Access Token
 * For plugin Socket.IO and other non-HTTP channel authentication
 * 获取当前端（admin/tenant/user）的 JWT Access Token
 * 供插件 Socket.IO 等非 HTTP 通道鉴权使用
 */
function getAuthToken(): null | string {
  const endpoint = getCurrentEndpoint();
  return TokenStorage.getToken(endpoint);
}

/**
 * Get current logged-in user info (for plugin collaboration, comments, etc.)
 * 获取当前登录用户信息（供插件协作、评论等场景使用）
 */
function getCurrentUser(): {
  id: null | number;
  name: string;
  username: string;
} {
  try {
    const userStore = useUserStore();
    const info = userStore.userInfo;
    if (info) {
      return {
        id: info.userId ? Number(info.userId) : null,
        username: info.username || '',
        name: info.realName || info.username || '',
      };
    }
  } catch {
    /* store not ready / 存储未就绪 */
  }
  return { id: null, username: '', name: '' };
}

export interface NovusPluginSharedAPI {
  /** HTTP request client / HTTP 请求客户端 */
  requestClient: typeof requestClient;
  /** i18n translation function / i18n 翻译函数 */
  $t: typeof $t;
  /** Icon component / 图标组件 */
  IconifyIcon: typeof IconifyIcon;
  /** Platform-level rich text editor component / 平台级富文本编辑器组件 */
  RichTextEditor: typeof RichTextEditor;
  /** Imperative mount API for rich text editor / 富文本编辑器命令式挂载 API */
  mountRichTextEditor: typeof mountRichTextEditor;
  /** Plugin slots store (UI slots: headerWidgets / floatingPanels, etc.) / 插件槽位 Store（UI 插槽：headerWidgets / floatingPanels 等） */
  usePluginSlotsStore: typeof usePluginSlotsStore;
  /** Plugin extensions store (editor extensions / panels / commands) / 插件扩展 Store（编辑器扩展 / 面板 / 命令） */
  usePluginExtensionsStore: typeof usePluginExtensionsStore;
  /** Register plugin i18n messages / 注册插件国际化消息 */
  registerLocale: (
    locale: string,
    prefix: string,
    messages: Record<string, unknown>,
  ) => void;
  /** Get current endpoint JWT Access Token (for Socket.IO and other non-HTTP auth) / 获取当前端 JWT Access Token（供 Socket.IO 等非 HTTP 通道鉴权） */
  getAuthToken: () => null | string;
  /** Get current logged-in user info (for collaboration, comments, etc.) / 获取当前登录用户信息（供协作、评论等场景） */
  getCurrentUser: () => { id: null | number; name: string; username: string };
  /** Vue Router instance (for plugin in-page navigation) / Vue Router 实例（供插件页面内导航使用） */
  router: typeof router;
  /** Register page context for AI awareness / 注册页面上下文供 AI 感知 */
  registerPageContext: typeof registerPageContext;
  /** Register page operations for AI invocation / 注册页面操作供 AI 调用 */
  registerPageOperations: typeof registerPageOperations;
  /** List currently registered page operations (e.g. to merge with plugin ops) / 获取当前已注册的页面操作（如与插件操作合并） */
  listPageOperations: typeof listPageOperations;
}

/**
 * Mount shared dependencies to window (call once)
 * 将共享依赖挂载到 window（调用一次即可）
 */
export function exposePluginShared(): void {
  const w = window as unknown as Record<string, unknown>;

  // Vue 核心
  w.Vue = Vue;

  // Vue Router
  w.VueRouter = VueRouter;

  // Ant Design Vue
  w.AntDesignVue = AntDesignVue;

  // Vben Common UI / Icons（供插件 UMD external 全局映射）
  w.VbenCommonUi = VbenCommonUi;
  w.VbenIcons = VbenIcons;

  // NovusAI 插件共享 API
  w.NovusPluginShared = {
    requestClient,
    $t,
    IconifyIcon,
    RichTextEditor,
    mountRichTextEditor,
    usePluginSlotsStore,
    usePluginExtensionsStore,
    registerLocale: _registerPluginLocale,
    getAuthToken,
    getCurrentUser,
    router,
    listPageOperations,
    registerPageContext,
    registerPageOperations,
  } satisfies NovusPluginSharedAPI;
}

/**
 * Merge plugin-provided translation messages into global i18n instance
 * 将插件提供的翻译消息合并到全局 i18n 实例
 */
const _DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

function _registerPluginLocale(
  locale: string,
  prefix: string,
  messages: Record<string, unknown>,
): void {
  try {
    if (i18n?.global) {
      const nestedMessages: Record<string, unknown> = Object.create(null);
      for (const [key, value] of Object.entries(messages)) {
        const keyParts = key.split('.');
        if (keyParts.length === 0) continue;
        let current: Record<string, unknown> = nestedMessages;
        for (let i = 0; i < keyParts.length - 1; i++) {
          const part = keyParts[i];
          if (!part || _DANGEROUS_KEYS.has(part)) continue;
          if (!(part in current) || typeof current[part] !== 'object') {
            current[part] = Object.create(null);
          }
          current = current[part] as Record<string, unknown>;
        }
        const lastPart = keyParts.at(-1);
        if (!lastPart || _DANGEROUS_KEYS.has(lastPart)) continue;
        current[lastPart] = value;
      }

      const prefixParts = prefix.split('.');
      let wrapped: Record<string, unknown> = nestedMessages;
      for (let i = prefixParts.length - 1; i >= 0; i--) {
        const part = prefixParts[i];
        if (!part || _DANGEROUS_KEYS.has(part)) continue;
        wrapped = { [part]: wrapped };
      }
      i18n.global.mergeLocaleMessage(locale, wrapped);
    }
  } catch {
    console.error('[PluginShared] Failed to register plugin locale');
  }
}
