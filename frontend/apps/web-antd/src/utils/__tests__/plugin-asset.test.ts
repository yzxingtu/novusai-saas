// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TokenStorage } from '#/store/shared/token-storage';
import {
  buildPluginAssetUrl,
  buildPluginIconUrl,
  getPluginAssetAuthHeaders,
} from '#/utils/plugin-asset';

vi.mock('#/router/access', () => ({
  getCurrentEndpoint: () => 'admin',
}));

describe('plugin-asset', () => {
  beforeEach(() => {
    localStorage.clear();
    // eslint-disable-next-line unicorn/no-document-cookie
    document.cookie = 'novus_plugin_asset_token=; Max-Age=0; Path=/';
    TokenStorage.init('vitest');
  });

  it('syncs runtime token into cookie instead of query string', () => {
    TokenStorage.setToken('admin', 'admin-token');

    const url = buildPluginAssetUrl('weather-widget', 'icon.png');

    expect(url).toBe('/plugin-assets/weather-widget/icon.png');
    expect(document.cookie).toContain('novus_plugin_asset_token=admin-token');
  });

  it('preserves plugin-assets absolute paths and merges custom query', () => {
    TokenStorage.setToken('admin', 'admin-token');

    const url = buildPluginAssetUrl(
      'weather-widget',
      '/plugin-assets/weather-widget/plugin.manifest.json',
      {
        query: { locale: 'zh-CN' },
      },
    );

    expect(url).toContain('/plugin-assets/weather-widget/plugin.manifest.json');
    expect(url).toContain('locale=zh-CN');
    expect(document.cookie).toContain('novus_plugin_asset_token=admin-token');
  });

  it('rewrites admin metadata icons to dedicated plugin-icons route', () => {
    TokenStorage.setToken('admin', 'admin-token');

    expect(buildPluginIconUrl('weather-widget', 'icon.png')).toBe(
      '/plugin-icons/weather-widget/icon.png',
    );
    expect(
      buildPluginIconUrl(
        'weather-widget',
        '/plugin-assets/weather-widget/icon.png',
      ),
    ).toBe('/plugin-icons/weather-widget/icon.png');
  });

  it('exposes authorization header for authenticated plugin fetches', () => {
    TokenStorage.setToken('admin', 'admin-token');

    expect(getPluginAssetAuthHeaders('admin')).toMatchObject({
      Authorization: 'Bearer admin-token',
      'X-Trace-ID': expect.any(String),
    });
  });

  it('passes through external urls unchanged', () => {
    expect(
      buildPluginAssetUrl('weather-widget', 'https://cdn.example.com/a.png'),
    ).toBe('https://cdn.example.com/a.png');
    expect(
      buildPluginAssetUrl('weather-widget', 'data:image/png;base64,ZmFrZQ=='),
    ).toBe('data:image/png;base64,ZmFrZQ==');
  });

  it('uses public plugin asset routes without auth headers or cookie sync', () => {
    TokenStorage.setToken('tenant', 'tenant-token');

    expect(
      buildPluginAssetUrl('weather-widget', 'plugin.manifest.json', {
        publicEndpoint: 'tenant',
      }),
    ).toBe('/plugin-public-assets/tenant/weather-widget/plugin.manifest.json');
    expect(getPluginAssetAuthHeaders({ publicEndpoint: 'tenant' })).toEqual({});
    expect(document.cookie).not.toContain('tenant-token');
  });

  it('rejects pre-prefixed public asset routes when publicEndpoint is omitted', () => {
    expect(() =>
      buildPluginAssetUrl(
        'weather-widget',
        '/plugin-public-assets/tenant/weather-widget/plugin.manifest.json',
      ),
    ).toThrow(/requires publicEndpoint='tenant'/);
  });

  it('rejects pre-prefixed public asset routes when publicEndpoint mismatches', () => {
    expect(() =>
      buildPluginAssetUrl(
        'weather-widget',
        '/plugin-public-assets/tenant/weather-widget/plugin.manifest.json',
        {
          publicEndpoint: 'admin',
        },
      ),
    ).toThrow(/does not match publicEndpoint 'admin'/);
  });

  it('rejects authenticated asset routes when publicEndpoint is used', () => {
    expect(() =>
      buildPluginAssetUrl(
        'weather-widget',
        '/plugin-assets/weather-widget/plugin.manifest.json',
        {
          publicEndpoint: 'tenant',
        },
      ),
    ).toThrow(/cannot be loaded with publicEndpoint 'tenant'/);
  });

  it('rejects arbitrary absolute paths outside plugin asset prefixes', () => {
    expect(() =>
      buildPluginAssetUrl('weather-widget', '/assets/shared/plugin.js'),
    ).toThrow(
      /must use \/plugin-assets\/\.\.\. or \/plugin-public-assets\/\.\.\./,
    );
  });

  it('rejects pre-prefixed asset routes that target a different plugin', () => {
    expect(() =>
      buildPluginAssetUrl(
        'weather-widget',
        '/plugin-assets/other-plugin/plugin.manifest.json',
      ),
    ).toThrow(/does not match plugin 'weather-widget'/);
  });

  it('rejects conflicting endpoint and publicEndpoint scope options', () => {
    expect(() =>
      buildPluginAssetUrl('weather-widget', 'plugin.manifest.json', {
        endpoint: 'admin',
        publicEndpoint: 'tenant',
      }),
    ).toThrow(/either endpoint or publicEndpoint/);

    expect(() =>
      getPluginAssetAuthHeaders({
        endpoint: 'admin',
        publicEndpoint: 'tenant',
      }),
    ).toThrow(/either endpoint or publicEndpoint/);
  });

  it('clears legacy plugin auth cookie variants before using public asset routes', () => {
    const cookieSetter = vi.spyOn(document, 'cookie', 'set');

    buildPluginAssetUrl('weather-widget', 'plugin.manifest.json', {
      publicEndpoint: 'tenant',
    });

    const clearWrites = cookieSetter.mock.calls
      .map(([value]) => String(value))
      .filter((value) =>
        value.startsWith('novus_plugin_asset_token=; Max-Age=0;'),
      );

    expect(clearWrites).toEqual(
      expect.arrayContaining([
        expect.stringContaining('Path=/;'),
        expect.stringContaining('Path=/plugin-assets;'),
        expect.stringContaining('Path=/plugin-icons;'),
        expect.stringContaining('Path=/plugin-public-assets;'),
      ]),
    );
  });
});
