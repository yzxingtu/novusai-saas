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
import { useAccessStore, useUserStore } from '@vben/stores';

import * as AntDesignVue from 'ant-design-vue';

import { registerCaptchaProvider as registerCaptchaProviderRegistry } from '#/components/business/captcha';
import {
  mountRichTextEditor,
  RichTextEditor,
} from '#/components/business/rich-text-editor';
import { $t } from '#/locales';
import { router } from '#/router';
import { getCurrentEndpoint } from '#/router/access';
import { useAIPanelStore } from '#/store';
import { TokenStorage } from '#/store/shared/token-storage';
import { usePluginExtensionsStore } from '#/stores/plugin-extensions';
import { usePluginSlotsStore } from '#/stores/plugin-slots';
import { checkPermission } from '#/utils/access';
import { downloadBlob } from '#/utils/download';
import {
  buildPluginApiBase,
  getPluginHostEndpoint,
} from '#/utils/plugin-runtime-context';
import { requestClient } from '#/utils/request';

// Re-export for dev mode: plugins import { $t, IconifyIcon, ... } from '@novus/plugin-shared' / 开发态供插件复用
export {
  $t,
  buildPluginApiBase,
  downloadBlob,
  getAccessCodes,
  getAuthToken,
  getCurrentUser,
  getPluginHostEndpoint,
  hasAccessByCodes,
  IconifyIcon,
  mountRichTextEditor,
  openAIPanel,
  registerCaptchaProviderRegistry as registerCaptchaProvider,
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

function getAccessCodes(): string[] {
  try {
    const accessStore = useAccessStore();
    return [...accessStore.accessCodes];
  } catch {
    return [];
  }
}

function hasAccessByCodes(
  codes: string | string[] | undefined,
  options: {
    mode?: 'all' | 'any';
  } = {},
): boolean {
  let requestedCodes: string[] = [];
  if (Array.isArray(codes)) {
    requestedCodes = codes;
  } else if (codes) {
    requestedCodes = [codes];
  }
  if (requestedCodes.length === 0) {
    return true;
  }

  const currentCodes = getAccessCodes();
  if (currentCodes.includes('*')) {
    return true;
  }

  if (options.mode === 'all') {
    return requestedCodes.every((code) => currentCodes.includes(code));
  }

  return checkPermission(requestedCodes, currentCodes);
}

export interface OpenAIPanelOptions {
  agentId?: number;
  conversationId?: null | number;
  message?: null | string;
}

function openAIPanel(options: OpenAIPanelOptions = {}): void {
  try {
    const aiPanelStore = useAIPanelStore();
    aiPanelStore.openWithContext({
      agentId: options.agentId,
      conversationId: options.conversationId ?? null,
      message: options.message ?? null,
    });
  } catch (error) {
    console.error('[PluginShared] Failed to open AI panel', error);
  }
}

/**
 * @deprecated Plugin extensions store is runtime-only and not part of
 * declarative plugin manifest contract.
 * / 已弃用：插件扩展 Store 仅运行时可用，不属于声明式插件 manifest 正式契约。
 */
type PluginExtensionsStoreAccessor = typeof usePluginExtensionsStore;

export interface NovusPluginSharedAPI {
  /** HTTP request client / HTTP 请求客户端 */
  requestClient: typeof requestClient;
  /** Current authenticated plugin host endpoint / 当前认证插件宿主端别 */
  getPluginHostEndpoint: typeof getPluginHostEndpoint;
  /** Build current-host plugin API base / 构建当前宿主端插件 API 前缀 */
  buildPluginApiBase: typeof buildPluginApiBase;
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
  /**
   * @deprecated Experimental runtime-only store; avoid new plugin dependencies.
   * / 已弃用：实验运行时能力，不建议新增插件依赖。
   */
  usePluginExtensionsStore?: PluginExtensionsStoreAccessor;
  /** Register plugin-internal i18n messages only; host menu/page titles still come from plugin.yaml manifest. / 仅注册插件内部文案；宿主菜单与页面标题仍来自 plugin.yaml manifest。 */
  registerLocale: (
    locale: string,
    prefix: string,
    messages: Record<string, unknown>,
  ) => void;
  /** Get current endpoint JWT Access Token (for Socket.IO and other non-HTTP auth) / 获取当前端 JWT Access Token（供 Socket.IO 等非 HTTP 通道鉴权） */
  getAuthToken: () => null | string;
  /** Get current access codes snapshot / 获取当前权限码快照 */
  getAccessCodes: () => string[];
  /** Check access codes with host-consistent semantics / 使用宿主一致语义检查权限码 */
  hasAccessByCodes: (
    codes: string | string[] | undefined,
    options?: { mode?: 'all' | 'any' },
  ) => boolean;
  /** Get current logged-in user info (for collaboration, comments, etc.) / 获取当前登录用户信息（供协作、评论等场景） */
  getCurrentUser: () => { id: null | number; name: string; username: string };
  /** Vue Router instance (for plugin in-page navigation) / Vue Router 实例（供插件页面内导航使用） */
  router: typeof router;
  /** Register captcha provider component / 注册验证码提供方组件 */
  registerCaptchaProvider: typeof registerCaptchaProviderRegistry;
  /** Download blob as file (handles cross-browser quirks) / 下载 Blob 为文件（处理跨浏览器兼容） */
  downloadBlob: typeof downloadBlob;
  /** Open the global AI panel with optional message/agent/conversation seed / 打开全局 AI 面板并可附带消息、智能体或对话种子 */
  openAIPanel: typeof openAIPanel;
}

/**
 * Mount shared dependencies to window (call once)
 * 将共享依赖挂载到 window（调用一次即可）
 */
export function exposePluginShared(): void {
  const w = window as unknown as Record<string, unknown>;

  // Vue 核心 / Vue runtime
  w.Vue = Vue;

  // Vue Router / 路由
  w.VueRouter = VueRouter;

  // Ant Design Vue / UI 组件库
  w.AntDesignVue = AntDesignVue;

  // Vben Common UI / Icons（供插件 UMD external 全局映射）
  w.VbenCommonUi = VbenCommonUi;
  w.VbenIcons = VbenIcons;

  // NovusAI 插件共享 API / plugin bridge namespace
  w.NovusPluginShared = {
    requestClient,
    getPluginHostEndpoint,
    buildPluginApiBase,
    $t,
    IconifyIcon,
    RichTextEditor,
    mountRichTextEditor,
    usePluginSlotsStore,
    usePluginExtensionsStore,
    registerLocale: _registerPluginLocale,
    getAuthToken,
    getAccessCodes,
    getCurrentUser,
    hasAccessByCodes,
    router,
    registerCaptchaProvider: registerCaptchaProviderRegistry,
    downloadBlob,
    openAIPanel,
  } satisfies NovusPluginSharedAPI;
}

/**
 * Merge plugin-provided translation messages into global i18n instance.
 * This only affects plugin-internal copy and does not rewrite manifest-derived menu/page titles.
 * `prefix` is the namespace wrapper, so messages should use relative keys such as
 * `{ title, description }` instead of already-prefixed keys like `plugin.foo.title`.
 * 将插件提供的翻译消息合并到全局 i18n 实例。
 * 这只影响插件内部文案，不会改写由 manifest 派生的菜单/页面标题。
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
