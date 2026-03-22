// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const pluginAssetMocks = vi.hoisted(() => ({
  buildPluginAssetUrl: vi.fn(
    (
      pluginName: string,
      assetPath: string,
      options?: { cacheBust?: boolean },
    ) => {
      const normalized = assetPath.startsWith('/')
        ? assetPath
        : `/plugin-assets/${pluginName}/${assetPath}`;
      if (options?.cacheBust) {
        return `${normalized}${normalized.includes('?') ? '&' : '?'}t=1`;
      }
      return normalized;
    },
  ),
  getPluginAssetAuthHeaders: vi.fn(() => ({
    Authorization: 'Bearer admin-token',
  })),
}));

vi.mock('#/utils/plugin-asset', () => ({
  buildPluginAssetUrl: pluginAssetMocks.buildPluginAssetUrl,
  getPluginAssetAuthHeaders: pluginAssetMocks.getPluginAssetAuthHeaders,
}));

import {
  buildPluginDevEntryUrl,
  loadPluginComponents,
  parsePluginReleaseManifest,
  pluginRuntimeEnv,
  unloadPlugin,
} from '#/utils/plugin-loader';

describe('plugin-loader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.head.innerHTML = '';
    document.body.innerHTML = '';
    unloadPlugin('demo-plugin');
    vi.spyOn(pluginRuntimeEnv, 'isDev').mockReturnValue(false);
  });

  afterEach(() => {
    unloadPlugin('demo-plugin');
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete (
      window as unknown as Window & Record<string, unknown>
    ).NovusPlugin_demo_plugin;
  });

  it('builds dev entry url from the __plugin_dev__ contract', () => {
    expect(buildPluginDevEntryUrl('demo-plugin')).toBe(
      '/__plugin_dev__/demo-plugin/entry?t=1',
    );
  });

  it('rejects invalid release manifest entries', () => {
    expect(() =>
      parsePluginReleaseManifest('demo-plugin', {
        entry: '../bad.js',
      }),
    ).toThrow(/valid entry/);
  });

  it('loads release manifest before injecting css and script assets', async () => {
    const setup = vi.fn();
    const moduleExport = {
      DemoWidget: { name: 'DemoWidget' },
      setup,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        assets: ['assets/logo.svg'],
        css: ['assets/plugin.css'],
        entry: 'assets/plugin.js',
        format: 'novus.plugin.release.v1',
        global_var: 'NovusPlugin_demo_plugin',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const originalAppend = document.head.append.bind(document.head);
    vi.spyOn(document.head, 'append').mockImplementation(
      (...nodes: Array<Node | string>) => {
        originalAppend(...nodes);
        for (const node of nodes) {
          if (node instanceof HTMLScriptElement) {
            (
              window as unknown as Window & Record<string, unknown>
            ).NovusPlugin_demo_plugin = moduleExport;
            queueMicrotask(() => node.dispatchEvent(new Event('load')));
          }
        }
      },
    );

    const mod = await loadPluginComponents('demo-plugin', {
      release_manifest: 'manifests/release.json',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/plugin-assets/demo-plugin/manifests/release.json',
      {
        headers: { Authorization: 'Bearer admin-token' },
      },
    );

    const cssNode = document.querySelector(
      'link[data-novus-plugin="demo-plugin"]',
    ) as HTMLLinkElement | null;
    expect(cssNode?.getAttribute('href')).toBe(
      '/plugin-assets/demo-plugin/assets/plugin.css',
    );

    const scriptNode = document.querySelector(
      'script[data-novus-plugin="demo-plugin"]',
    ) as HTMLScriptElement | null;
    expect(scriptNode?.getAttribute('src')).toBe(
      '/plugin-assets/demo-plugin/assets/plugin.js',
    );

    expect(pluginAssetMocks.getPluginAssetAuthHeaders).toHaveBeenCalledTimes(
      1,
    );
    expect(setup).toHaveBeenCalledTimes(1);
    expect(mod).toBe(moduleExport);
  });
});
