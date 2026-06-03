// @vitest-environment happy-dom
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePluginSlotsStore } from '../plugin-slots';

const adminPluginApiMocks = vi.hoisted(() => ({
  getPluginSlotsApi: vi.fn(),
}));

const tenantPluginApiMocks = vi.hoisted(() => ({
  getTenantPluginSlotsApi: vi.fn(),
}));

const pluginLoaderMocks = vi.hoisted(() => ({
  getPluginRuntimeCacheKey: vi.fn(
    (
      pluginName: string,
      runtimeContract?: { dev_entry?: string; release_manifest?: string },
      loadOptions?: { endpoint?: string; publicEndpoint?: string },
    ) =>
      `${pluginName}::${loadOptions?.endpoint ?? loadOptions?.publicEndpoint ?? 'unknown'}::${runtimeContract?.release_manifest ?? runtimeContract?.dev_entry ?? 'plugin.manifest.json'}`,
  ),
  loadPluginComponents: vi.fn(),
  unloadPlugin: vi.fn(),
}));

const iconMocks = vi.hoisted(() => ({
  ensureLucideIconCatalogRegistered: vi.fn(async () => {}),
}));

vi.mock('#/api/admin/plugin', () => ({
  getPluginSlotsApi: adminPluginApiMocks.getPluginSlotsApi,
}));

vi.mock('#/api/tenant/plugin', () => ({
  getTenantPluginSlotsApi: tenantPluginApiMocks.getTenantPluginSlotsApi,
}));

vi.mock('#/utils/plugin-loader', () => ({
  getPluginRuntimeCacheKey: pluginLoaderMocks.getPluginRuntimeCacheKey,
  loadPluginComponents: pluginLoaderMocks.loadPluginComponents,
  unloadPlugin: pluginLoaderMocks.unloadPlugin,
}));

vi.mock('@vben/icons', () => ({
  ensureLucideIconCatalogRegistered:
    iconMocks.ensureLucideIconCatalogRegistered,
}));

vi.mock('@vben/preferences', () => ({
  preferences: {
    app: {
      locale: 'zh-CN',
    },
  },
}));

function createEmptySlotsResponse() {
  return {
    dashboard_widgets: [],
    floating_panels: [],
    header_widgets: [],
    notification_ui: [],
    pages: [],
    settings_tabs: [],
  };
}

describe('plugin-slots store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('passes the endpoint side through to plugin asset loading', async () => {
    tenantPluginApiMocks.getTenantPluginSlotsApi.mockResolvedValue({
      ...createEmptySlotsResponse(),
      pages: [
        {
          component: 'TenantHomePage',
          frontend_runtime: {
            release_manifest: 'manifests/release.json',
          },
          name: 'tenant-home',
          path: '/tenant/plugins/demo-plugin',
          plugin_name: 'demo-plugin',
          title: {
            'zh-CN': '租户插件首页',
          },
        },
      ],
    });
    pluginLoaderMocks.loadPluginComponents.mockResolvedValue({
      TenantHomePage: { name: 'TenantHomePage' },
    });

    const store = usePluginSlotsStore();
    await store.fetchSlots('tenant');

    expect(pluginLoaderMocks.getPluginRuntimeCacheKey).toHaveBeenCalledWith(
      'demo-plugin',
      { release_manifest: 'manifests/release.json' },
      { endpoint: 'tenant' },
    );
    expect(pluginLoaderMocks.loadPluginComponents).toHaveBeenCalledWith(
      'demo-plugin',
      { release_manifest: 'manifests/release.json' },
      { endpoint: 'tenant' },
    );
    expect(store.pages).toHaveLength(1);
    expect(store.pages[0]?.title).toBe('租户插件首页');
  });

  it('preserves the last successful snapshot when a later fetch fails', async () => {
    adminPluginApiMocks.getPluginSlotsApi
      .mockResolvedValueOnce({
        ...createEmptySlotsResponse(),
        pages: [
          {
            component: 'DemoPage',
            name: 'demo-home',
            path: '/admin/plugins/demo-plugin',
            plugin_name: 'demo-plugin',
            title: {
              'zh-CN': '演示插件',
            },
          },
        ],
      })
      .mockResolvedValueOnce({
        ...createEmptySlotsResponse(),
        pages: [
          {
            component: 'BrokenPage',
            name: 'broken-home',
            path: '/admin/plugins/broken-plugin',
            plugin_name: 'broken-plugin',
            title: {
              'zh-CN': '损坏插件',
            },
          },
        ],
      });

    pluginLoaderMocks.loadPluginComponents
      .mockResolvedValueOnce({
        DemoPage: { name: 'DemoPage' },
      })
      .mockResolvedValueOnce({});

    const store = usePluginSlotsStore();
    await store.fetchSlots('admin');

    await expect(store.fetchSlots('admin')).rejects.toThrow(
      /Plugin page registration failed/,
    );

    expect(store.pages).toHaveLength(1);
    expect(store.pages[0]?.pluginName).toBe('demo-plugin');
    expect(store.pages[0]?.title).toBe('演示插件');
  });

  it('unloads existing plugin assets before force-reloading a snapshot', async () => {
    adminPluginApiMocks.getPluginSlotsApi.mockResolvedValue({
      ...createEmptySlotsResponse(),
      pages: [
        {
          component: 'DemoPage',
          name: 'demo-home',
          path: '/admin/plugins/demo-plugin',
          plugin_name: 'demo-plugin',
        },
      ],
    });
    pluginLoaderMocks.loadPluginComponents.mockResolvedValue({
      DemoPage: { name: 'DemoPage' },
    });

    const store = usePluginSlotsStore();
    await store.fetchSlots('admin', { forceReload: true });

    expect(pluginLoaderMocks.unloadPlugin).toHaveBeenCalledWith('demo-plugin', {
      endpoint: 'admin',
    });
  });

  it('memoizes plugin modules by runtime contract, not only by plugin name', async () => {
    adminPluginApiMocks.getPluginSlotsApi.mockResolvedValue({
      ...createEmptySlotsResponse(),
      pages: [
        {
          component: 'DemoPageV1',
          frontend_runtime: {
            release_manifest: 'manifests/release-v1.json',
          },
          name: 'demo-home-v1',
          path: '/admin/plugins/demo-plugin/v1',
          plugin_name: 'demo-plugin',
          title: { 'zh-CN': '演示插件 V1' },
        },
        {
          component: 'DemoPageV2',
          frontend_runtime: {
            release_manifest: 'manifests/release-v2.json',
          },
          name: 'demo-home-v2',
          path: '/admin/plugins/demo-plugin/v2',
          plugin_name: 'demo-plugin',
          title: { 'zh-CN': '演示插件 V2' },
        },
      ],
    });
    pluginLoaderMocks.loadPluginComponents
      .mockResolvedValueOnce({
        DemoPageV1: { name: 'DemoPageV1' },
      })
      .mockResolvedValueOnce({
        DemoPageV2: { name: 'DemoPageV2' },
      });

    const store = usePluginSlotsStore();
    await store.fetchSlots('admin');

    expect(pluginLoaderMocks.loadPluginComponents).toHaveBeenCalledTimes(2);
    expect(pluginLoaderMocks.getPluginRuntimeCacheKey).toHaveBeenCalledTimes(2);
    expect(store.pages).toHaveLength(2);
    expect(store.pages.map((page) => page.name)).toEqual([
      'demo-home-v1',
      'demo-home-v2',
    ]);
  });

  it('projects settings tabs, floating panels, and notification ui from one plugin runtime bundle', async () => {
    adminPluginApiMocks.getPluginSlotsApi.mockResolvedValue({
      ...createEmptySlotsResponse(),
      floating_panels: [
        {
          component: 'OpsPanel',
          frontend_runtime: {
            release_manifest: 'manifests/release.json',
          },
          name: 'ops-panel',
          plugin_name: 'demo-plugin',
          position: 'top-left',
        },
      ],
      notification_ui: [
        {
          component: 'BuildNotification',
          frontend_runtime: {
            release_manifest: 'manifests/release.json',
          },
          name: 'build.finished',
          plugin_name: 'demo-plugin',
        },
      ],
      settings_tabs: [
        {
          component: 'AdvancedSettingsTab',
          frontend_runtime: {
            release_manifest: 'manifests/release.json',
          },
          name: 'advanced-settings',
          plugin_name: 'demo-plugin',
          scope: 'admin',
          title: {
            'zh-CN': '高级设置',
          },
        },
      ],
    });
    pluginLoaderMocks.loadPluginComponents.mockResolvedValue({
      AdvancedSettingsTab: { name: 'AdvancedSettingsTab' },
      BuildNotification: { name: 'BuildNotification' },
      OpsPanel: { name: 'OpsPanel' },
    });

    const store = usePluginSlotsStore();
    await store.fetchSlots('admin');

    expect(pluginLoaderMocks.loadPluginComponents).toHaveBeenCalledTimes(1);
    expect(pluginLoaderMocks.loadPluginComponents).toHaveBeenCalledWith(
      'demo-plugin',
      { release_manifest: 'manifests/release.json' },
      { endpoint: 'admin' },
    );

    expect(store.settingsTabs).toHaveLength(1);
    expect(store.settingsTabs[0]?.title).toBe('高级设置');
    expect(store.settingsTabs[0]?.scope).toBe('admin');

    expect(store.floatingPanels).toHaveLength(1);
    expect(store.floatingPanels[0]?.position).toBe('top-left');

    expect(store.notificationUI).toHaveLength(1);
    expect(store.notificationUI[0]?.event).toBe('build.finished');
  });
});
