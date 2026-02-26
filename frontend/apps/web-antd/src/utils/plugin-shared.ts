/**
 * 插件共享依赖暴露
 *
 * 将插件常用的宿主依赖挂载到 window，供插件 UMD 包作为 external 引用。
 * 必须在 bootstrap 早期调用 exposePluginShared()。
 *
 * 插件 vite.config 中 rollupOptions.external 映射:
 *   'vue'                -> window.Vue
 *   'vue-router'         -> window.VueRouter
 *   'ant-design-vue'     -> window.AntDesignVue
 *   '@novus/plugin-shared' -> window.NovusPluginShared
 */

import * as Vue from 'vue';
import * as VueRouter from 'vue-router';
import * as AntDesignVue from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { i18n } from '@vben/locales';
import { useUserStore } from '@vben/stores';
import { requestClient } from '#/utils/request';
import { $t } from '#/locales';
import { usePluginSlotsStore } from '#/stores/plugin-slots';
import { usePluginExtensionsStore } from '#/stores/plugin-extensions';
import { TokenStorage } from '#/store/shared/token-storage';
import { getCurrentEndpoint } from '#/router/access';

// Re-export for dev mode: plugins import { $t, IconifyIcon, ... } from '@novus/plugin-shared'
export { requestClient, $t, IconifyIcon, usePluginSlotsStore, usePluginExtensionsStore, getAuthToken, getCurrentUser };

/**
 * 获取当前端（admin/tenant/user）的 JWT Access Token
 * 供插件 Socket.IO 等非 HTTP 通道鉴权使用
 */
function getAuthToken(): string | null {
  const endpoint = getCurrentEndpoint();
  return TokenStorage.getToken(endpoint);
}

/**
 * 获取当前登录用户信息（供插件协作、评论等场景使用）
 */
function getCurrentUser(): { id: number | null; username: string; name: string } {
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
  } catch { /* store not ready */ }
  return { id: null, username: '', name: '' };
}

export interface NovusPluginSharedAPI {
  /** HTTP 请求客户端 */
  requestClient: typeof requestClient;
  /** i18n 翻译函数 */
  $t: typeof $t;
  /** 图标组件 */
  IconifyIcon: typeof IconifyIcon;
  /** 插件槽位 Store（UI 插槽：headerWidgets / floatingPanels 等） */
  usePluginSlotsStore: typeof usePluginSlotsStore;
  /** 插件扩展 Store（编辑器扩展 / 面板 / 命令） */
  usePluginExtensionsStore: typeof usePluginExtensionsStore;
  /** 注册插件国际化消息 */
  registerLocale: (locale: string, prefix: string, messages: Record<string, unknown>) => void;
  /** 获取当前端 JWT Access Token（供 Socket.IO 等非 HTTP 通道鉴权） */
  getAuthToken: () => string | null;
  /** 获取当前登录用户信息（供协作、评论等场景） */
  getCurrentUser: () => { id: number | null; username: string; name: string };
}

/**
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

  // NovusAI 插件共享 API
  w.NovusPluginShared = {
    requestClient,
    $t,
    IconifyIcon,
    usePluginSlotsStore,
    usePluginExtensionsStore,
    registerLocale: _registerPluginLocale,
    getAuthToken,
    getCurrentUser,
  } satisfies NovusPluginSharedAPI;
}

/**
 * 将插件提供的翻译消息合并到全局 i18n 实例
 */
function _registerPluginLocale(
  locale: string,
  prefix: string,
  messages: Record<string, unknown>,
): void {
  try {
    if (i18n?.global) {
      // 将扁平点分 key（如 'folder.all': '全部文档'）转为嵌套对象
      // 再包裹 prefix（如 "plugin.novusdoc"）→ { plugin: { novusdoc: { folder: { all: '全部文档' } } } }
      const nestedMessages: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(messages)) {
        const keyParts = key.split('.');
        let current: Record<string, unknown> = nestedMessages;
        for (let i = 0; i < keyParts.length - 1; i++) {
          if (!(keyParts[i]! in current) || typeof current[keyParts[i]!] !== 'object') {
            current[keyParts[i]!] = {};
          }
          current = current[keyParts[i]!] as Record<string, unknown>;
        }
        current[keyParts[keyParts.length - 1]!] = value;
      }

      // 包裹 prefix 路径
      const prefixParts = prefix.split('.');
      let wrapped: Record<string, unknown> = nestedMessages;
      for (let i = prefixParts.length - 1; i >= 0; i--) {
        wrapped = { [prefixParts[i]!]: wrapped };
      }
      i18n.global.mergeLocaleMessage(locale, wrapped);
    }
  } catch {
    console.error('[PluginShared] Failed to register plugin locale');
  }
}
