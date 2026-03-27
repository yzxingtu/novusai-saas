import { describe, expect, it, vi } from 'vitest';

import {
  buildCurrentRouteReloadTarget,
  syncLocaleNavigation,
} from '../locale-navigation-sync';

describe('locale-navigation-sync', () => {
  it('rebuilds access, plugin routes, tabs, and current route title from the active locale', async () => {
    const accessStore = {
      setAccessMenus: vi.fn(),
      setAccessRoutes: vi.fn(),
    };
    const tabbarStore = {
      getTabs: [
        {
          meta: {} as Record<string, unknown>,
          path: '/admin/plugins/demo-plugin',
        },
        { meta: {} as Record<string, unknown>, path: '/admin/system/codegen' },
      ],
      touchTabs: vi.fn(),
      setUpdateTime: vi.fn(),
    };
    const router = {
      currentRoute: {
        value: {
          hash: '#details',
          name: 'plugin-demo-plugin-home',
          params: { id: '42' },
          path: '/admin/plugins/demo-plugin',
          query: { view: 'summary' },
        },
      },
      getRoutes: vi.fn(() => [
        {
          meta: {
            title: 'plugin.demo.menu',
            titleLocaleMap: { 'zh-CN': '演示插件', en: 'Demo Plugin' },
          },
          path: '/admin/plugins/demo-plugin',
        },
        {
          meta: {
            title: 'admin.system.codegen.name',
            titleLocaleMap: { 'zh-CN': '代码生成', en: 'Codegen' },
          },
          path: '/admin/system/codegen',
        },
      ]),
      replace: vi.fn(() => Promise.resolve()),
    };
    const generateAccess = vi.fn(async () => ({
      accessibleMenus: [{ name: 'demo-menu' }],
      accessibleRoutes: [{ name: 'demo-route' }],
    }));
    const refreshPluginSlots = vi.fn(async () => {});

    await syncLocaleNavigation({
      accessStore,
      endpoint: 'admin',
      generateAccess,
      hasLocaleKey: () => false,
      locale: 'en',
      refreshPluginSlots,
      router: router as never,
      routes: [{ component: {} as never, name: 'AdminRoot', path: '/admin' }],
      tabbarStore,
      translate: (key: string) => key,
      userRoles: ['super_admin'],
    });

    expect(generateAccess).toHaveBeenCalledWith(
      {
        roles: ['super_admin'],
        router,
        routes: [{ component: {} as never, name: 'AdminRoot', path: '/admin' }],
      },
      'admin',
    );
    expect(accessStore.setAccessMenus).toHaveBeenCalledWith([
      { name: 'demo-menu' },
    ]);
    expect(accessStore.setAccessRoutes).toHaveBeenCalledWith([
      { name: 'demo-route' },
    ]);
    expect(refreshPluginSlots).toHaveBeenCalledWith('admin', router, {
      reloadAssets: false,
    });
    expect(tabbarStore.getTabs[0]?.meta?.title).toBe('Demo Plugin');
    expect(tabbarStore.getTabs[1]?.meta?.title).toBe('Codegen');
    expect(tabbarStore.touchTabs).toHaveBeenCalledTimes(1);
    expect(tabbarStore.setUpdateTime).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith({
      force: true,
      hash: '#details',
      name: 'plugin-demo-plugin-home',
      params: { id: '42' },
      query: { view: 'summary' },
    });
  });

  it('falls back to path reload targets when the current route has no name', () => {
    expect(
      buildCurrentRouteReloadTarget({
        hash: '#intro',
        params: {},
        path: '/tenant/plugins/example',
        query: { a: '1' },
      } as never),
    ).toEqual({
      hash: '#intro',
      path: '/tenant/plugins/example',
      query: { a: '1' },
    });
  });
});
