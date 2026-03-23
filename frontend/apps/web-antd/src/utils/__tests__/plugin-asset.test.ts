// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('#/router/access', () => ({
  getCurrentEndpoint: () => 'admin',
}));

import { TokenStorage } from '#/store/shared/token-storage';
import {
  buildPluginAssetUrl,
  buildPluginIconUrl,
  getPluginAssetAuthHeaders,
} from '#/utils/plugin-asset';

describe('plugin-asset', () => {
  beforeEach(() => {
    localStorage.clear();
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
      buildPluginAssetUrl(
        'weather-widget',
        'data:image/png;base64,ZmFrZQ==',
      ),
    ).toBe('data:image/png;base64,ZmFrZQ==');
  });
});
