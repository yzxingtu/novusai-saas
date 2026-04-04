import { nextTick, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  buildDocumentTitle,
  setupDocumentTitleSync,
} from '../document-title-sync';

describe('document-title-sync', () => {
  beforeEach(() => {
    document.title = 'Initial Title';
  });

  afterEach(() => {
    document.title = 'Initial Title';
  });

  it('recomputes the page title when plugin route metadata is hydrated after bootstrap', async () => {
    const locale = ref('en-US');
    const currentRoute = ref<Record<string, any>>({
      meta: {
        title: '文档管理',
      },
      name: 'AdminPluginPlaceholder',
      path: '/admin/plugins/novusdoc',
    });

    const stop = setupDocumentTitleSync({
      appName: () => 'NovusAI SaaS',
      dynamicTitle: () => true,
      hasLocaleKey: () => false,
      locale: () => locale.value,
      router: { currentRoute } as never,
      translate: (key: string) => key,
    });

    await nextTick();
    expect(document.title).toBe('文档管理 - NovusAI SaaS');

    currentRoute.value = {
      ...currentRoute.value,
      meta: {
        title: '文档管理',
        titleLocaleMap: {
          'zh-CN': '文档管理',
          en: 'Documents',
        },
      },
      name: 'plugin-novusdoc-novusdoc-admin',
    };

    await nextTick();
    expect(document.title).toBe('Documents - NovusAI SaaS');
    stop();
  });

  it('recomputes the page title when the locale changes for plugin routes', async () => {
    const locale = ref('zh-CN');
    const currentRoute = ref<Record<string, any>>({
      meta: {
        title: '文档管理',
        titleLocaleMap: {
          'zh-CN': '文档管理',
          en: 'Documents',
        },
      },
      name: 'plugin-novusdoc-novusdoc-admin',
      path: '/admin/plugins/novusdoc',
    });

    const stop = setupDocumentTitleSync({
      appName: () => 'NovusAI SaaS',
      dynamicTitle: () => true,
      hasLocaleKey: () => false,
      locale: () => locale.value,
      router: { currentRoute } as never,
      translate: (key: string) => key,
    });

    await nextTick();
    expect(document.title).toBe('文档管理 - NovusAI SaaS');

    locale.value = 'en-US';
    await nextTick();
    expect(document.title).toBe('Documents - NovusAI SaaS');
    stop();
  });

  it('recomputes the page title when route metadata is refreshed after locale sync', async () => {
    const locale = ref('zh-CN');
    const refreshSignal = ref(0);
    const currentRoute = ref({
      meta: {
        title: 'Plugin Management',
      },
      name: 'menu:admin.plugin',
      path: '/admin/plugins',
    });

    const stop = setupDocumentTitleSync({
      appName: () => 'NovusAI SaaS',
      dynamicTitle: () => true,
      hasLocaleKey: () => false,
      locale: () => locale.value,
      refreshSignal: () => refreshSignal.value,
      router: { currentRoute } as never,
      translate: (key: string) => key,
    });

    await nextTick();
    expect(document.title).toBe('Plugin Management - NovusAI SaaS');

    currentRoute.value.meta.title = '插件管理';
    refreshSignal.value += 1;

    await nextTick();
    expect(document.title).toBe('插件管理 - NovusAI SaaS');
    stop();
  });

  it('falls back to the app name when the route has no title', () => {
    expect(
      buildDocumentTitle({
        appName: 'NovusAI SaaS',
        hasLocaleKey: () => false,
        locale: 'en-US',
        meta: {},
        translate: (key: string) => key,
      }),
    ).toBe('NovusAI SaaS');
  });
});
