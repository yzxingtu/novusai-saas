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
import { requestClient } from '#/utils/request';
import { $t } from '#/locales';
import { usePluginSlotsStore } from '#/stores/plugin-slots';

// Re-export for dev mode: plugins import { $t, IconifyIcon, ... } from '@novus/plugin-shared'
export { requestClient, $t, IconifyIcon, usePluginSlotsStore };

export interface NovusPluginSharedAPI {
  /** HTTP 请求客户端 */
  requestClient: typeof requestClient;
  /** i18n 翻译函数 */
  $t: typeof $t;
  /** 图标组件 */
  IconifyIcon: typeof IconifyIcon;
  /** 插件槽位 Store */
  usePluginSlotsStore: typeof usePluginSlotsStore;
  /** 注册插件国际化消息 */
  registerLocale: (locale: string, prefix: string, messages: Record<string, unknown>) => void;
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
    registerLocale: _registerPluginLocale,
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
      // 将 "plugin.my-plugin" → { plugin: { "my-plugin": messages } }
      const parts = prefix.split('.');
      let nested: Record<string, unknown> = messages;
      for (let i = parts.length - 1; i >= 0; i--) {
        nested = { [parts[i]!]: nested };
      }
      i18n.global.mergeLocaleMessage(locale, nested);
    }
  } catch {
    console.error('[PluginShared] Failed to register plugin locale');
  }
}
