// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildPluginDevEntryUrl,
  getPluginRuntimeCacheKey,
  loadPluginComponents,
  parsePluginReleaseManifest,
  pluginRuntimeEnv,
  unloadPlugin,
} from '../plugin-loader';

const pluginAssetMocks = vi.hoisted(() => ({
  buildPluginAssetUrl: vi.fn(
    (
      pluginName: string,
      assetPath: string,
      options?: {
        cacheBust?: boolean;
        endpoint?: 'admin' | 'tenant' | 'user';
        publicEndpoint?: 'admin' | 'tenant' | 'user';
      },
    ) => {
      const basePath = options?.publicEndpoint
        ? `/plugin-public-assets/${options.publicEndpoint}/${pluginName}/`
        : `/plugin-assets/${pluginName}/`;
      const normalized = assetPath.startsWith('/')
        ? assetPath
        : `${basePath}${assetPath}`;
      if (options?.cacheBust) {
        return `${normalized}${normalized.includes('?') ? '&' : '?'}t=1`;
      }
      return normalized;
    },
  ),
  getPluginAssetAuthHeaders: vi.fn(
    (
      options?:
        | 'admin'
        | {
            endpoint?: 'admin' | 'tenant' | 'user';
            publicEndpoint?: 'admin' | 'tenant' | 'user';
          },
    ) =>
      typeof options === 'object' && options?.publicEndpoint
        ? {}
        : {
            Authorization: 'Bearer admin-token',
            'X-Trace-ID': 'trace-plugin-manifest',
          },
  ),
}));

vi.mock('#/utils/plugin-asset', () => ({
  buildPluginAssetUrl: pluginAssetMocks.buildPluginAssetUrl,
  getPluginAssetAuthHeaders: pluginAssetMocks.getPluginAssetAuthHeaders,
}));

describe('plugin-loader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.head.innerHTML = '';
    document.body.innerHTML = '';
    window.history.replaceState({}, '', '/admin/overview');
    unloadPlugin('demo-plugin');
    vi.spyOn(pluginRuntimeEnv, 'isDev').mockReturnValue(false);
  });

  afterEach(() => {
    unloadPlugin('demo-plugin');
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete (window as unknown as Record<string, unknown> & Window)
      .NovusPlugin_demo_plugin;
  });

  it('builds the dev entry url and forwards runtime dev_entry when provided', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1);

    expect(buildPluginDevEntryUrl('demo-plugin')).toBe(
      '/__plugin_dev__/demo-plugin/entry?t=1',
    );

    expect(
      buildPluginDevEntryUrl('demo-plugin', {
        dev_entry: 'src/index.ts',
      }),
    ).toBe('/__plugin_dev__/demo-plugin/entry?entry=src%2Findex.ts&t=1');
  });

  it('drops invalid dev_entry traversal paths', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1);

    expect(
      buildPluginDevEntryUrl('demo-plugin', {
        dev_entry: '../escape.ts',
      }),
    ).toBe('/__plugin_dev__/demo-plugin/entry?t=1');
  });

  it('rejects invalid release manifest entries', () => {
    expect(() =>
      parsePluginReleaseManifest('demo-plugin', {
        entry: '../bad.js',
      }),
    ).toThrow(/valid entry/);
  });

  it('parses release manifests with default global var fallback', () => {
    expect(
      parsePluginReleaseManifest('demo-plugin', {
        entry: 'plugin.js',
      }),
    ).toEqual({
      assets: [],
      css: [],
      entry: 'plugin.js',
      format: 'novus.plugin.release.v1',
      global_var: 'NovusPlugin_demo_plugin',
    });
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
              window as unknown as Record<string, unknown> & Window
            ).NovusPlugin_demo_plugin = moduleExport;
            queueMicrotask(() => node.dispatchEvent(new Event('load')));
          }
        }
      },
    );

    const mod = await loadPluginComponents(
      'demo-plugin',
      {
        release_manifest: 'manifests/release.json',
      },
      { endpoint: 'admin' },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      '/plugin-assets/demo-plugin/manifests/release.json',
      {
        headers: {
          Authorization: 'Bearer admin-token',
          'X-Trace-ID': 'trace-plugin-manifest',
        },
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

    expect(pluginAssetMocks.getPluginAssetAuthHeaders).toHaveBeenCalledTimes(1);
    expect(pluginAssetMocks.getPluginAssetAuthHeaders).toHaveBeenCalledWith({
      endpoint: 'admin',
      publicEndpoint: undefined,
    });
    expect(setup).toHaveBeenCalledTimes(1);
    expect(mod).toBe(moduleExport);
  });

  it('reloads the same authenticated scope when runtime contract changes', async () => {
    const setup = vi.fn();
    const moduleExport = {
      TenantWidget: { name: 'TenantWidget' },
      setup,
    };
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          entry: url.includes('release-v2.json')
            ? 'assets/plugin-v2.js'
            : 'assets/plugin-v1.js',
          format: 'novus.plugin.release.v1',
          global_var: 'NovusPlugin_demo_plugin',
        }),
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const originalAppend = document.head.append.bind(document.head);
    vi.spyOn(document.head, 'append').mockImplementation(
      (...nodes: Array<Node | string>) => {
        originalAppend(...nodes);
        for (const node of nodes) {
          if (node instanceof HTMLScriptElement) {
            (
              window as unknown as Record<string, unknown> & Window
            ).NovusPlugin_demo_plugin = moduleExport;
            queueMicrotask(() => node.dispatchEvent(new Event('load')));
          }
        }
      },
    );

    await loadPluginComponents(
      'demo-plugin',
      { release_manifest: 'manifests/release-v1.json' },
      { endpoint: 'admin' },
    );
    await loadPluginComponents(
      'demo-plugin',
      { release_manifest: 'manifests/release-v2.json' },
      { endpoint: 'admin' },
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(setup).toHaveBeenCalledTimes(2);

    const scripts = [
      ...document.querySelectorAll('script[data-novus-plugin="demo-plugin"]'),
    ] as HTMLScriptElement[];
    expect(scripts).toHaveLength(1);
    expect(scripts[0]?.dataset.novusPluginScope).toBe(
      'demo-plugin::auth:admin',
    );
    expect(scripts[0]?.getAttribute('src')).toBe(
      '/plugin-assets/demo-plugin/assets/plugin-v2.js',
    );
  });

  it('uses public endpoint asset urls without authenticated headers when requested', async () => {
    const moduleExport = {
      TenantWidget: { name: 'TenantWidget' },
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
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
              window as unknown as Record<string, unknown> & Window
            ).NovusPlugin_demo_plugin = moduleExport;
            queueMicrotask(() => node.dispatchEvent(new Event('load')));
          }
        }
      },
    );

    await loadPluginComponents(
      'demo-plugin',
      { release_manifest: 'manifests/release.json' },
      { publicEndpoint: 'tenant' },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      '/plugin-public-assets/tenant/demo-plugin/manifests/release.json',
      { headers: {} },
    );
    expect(pluginAssetMocks.getPluginAssetAuthHeaders).toHaveBeenCalledWith({
      endpoint: undefined,
      publicEndpoint: 'tenant',
    });

    const cssNode = document.querySelector(
      'link[data-novus-plugin="demo-plugin"]',
    ) as HTMLLinkElement | null;
    expect(cssNode?.getAttribute('href')).toBe(
      '/plugin-public-assets/tenant/demo-plugin/assets/plugin.css',
    );
  });

  it('keeps cache entries isolated per authenticated endpoint scope', async () => {
    const setup = vi.fn();
    const moduleExport = {
      DemoWidget: { name: 'DemoWidget' },
      setup,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
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
              window as unknown as Record<string, unknown> & Window
            ).NovusPlugin_demo_plugin = moduleExport;
            queueMicrotask(() => node.dispatchEvent(new Event('load')));
          }
        }
      },
    );

    await loadPluginComponents(
      'demo-plugin',
      { release_manifest: 'manifests/release.json' },
      { endpoint: 'admin' },
    );
    await loadPluginComponents(
      'demo-plugin',
      { release_manifest: 'manifests/release.json' },
      { endpoint: 'tenant' },
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(setup).toHaveBeenCalledTimes(2);

    const scriptScopes = (
      [
        ...document.querySelectorAll('script[data-novus-plugin="demo-plugin"]'),
      ] as HTMLScriptElement[]
    ).map((node) => node.dataset.novusPluginScope);
    expect(scriptScopes).toEqual(
      expect.arrayContaining([
        'demo-plugin::auth:admin',
        'demo-plugin::auth:tenant',
      ]),
    );
  });

  it('keeps public and authenticated cache entries isolated for the same side', async () => {
    const setup = vi.fn();
    const moduleExport = {
      DemoWidget: { name: 'DemoWidget' },
      setup,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
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
              window as unknown as Record<string, unknown> & Window
            ).NovusPlugin_demo_plugin = moduleExport;
            queueMicrotask(() => node.dispatchEvent(new Event('load')));
          }
        }
      },
    );

    await loadPluginComponents(
      'demo-plugin',
      { release_manifest: 'manifests/release.json' },
      { endpoint: 'tenant' },
    );
    await loadPluginComponents(
      'demo-plugin',
      { release_manifest: 'manifests/release.json' },
      { publicEndpoint: 'tenant' },
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);

    const scriptScopes = (
      [
        ...document.querySelectorAll('script[data-novus-plugin="demo-plugin"]'),
      ] as HTMLScriptElement[]
    ).map((node) => node.dataset.novusPluginScope);
    expect(scriptScopes).toEqual(
      expect.arrayContaining([
        'demo-plugin::auth:tenant',
        'demo-plugin::public:tenant',
      ]),
    );
  });

  it('derives runtime cache keys from scope and runtime contract, not only plugin name', () => {
    expect(
      getPluginRuntimeCacheKey(
        'demo-plugin',
        { release_manifest: 'manifests/release-v1.json' },
        { endpoint: 'tenant' },
      ),
    ).not.toBe(
      getPluginRuntimeCacheKey(
        'demo-plugin',
        { release_manifest: 'manifests/release-v2.json' },
        { endpoint: 'tenant' },
      ),
    );

    expect(
      getPluginRuntimeCacheKey(
        'demo-plugin',
        { release_manifest: 'manifests/release.json' },
        { endpoint: 'tenant' },
      ),
    ).not.toBe(
      getPluginRuntimeCacheKey(
        'demo-plugin',
        { release_manifest: 'manifests/release.json' },
        { publicEndpoint: 'tenant' },
      ),
    );
  });

  it('does not cache a plugin module when setup throws', async () => {
    const failingSetup = vi.fn(() => {
      throw new Error('setup boom');
    });
    const succeedingSetup = vi.fn();
    let moduleExport: Record<string, unknown> = {
      DemoWidget: { name: 'DemoWidget' },
      setup: failingSetup,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
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
              window as unknown as Record<string, unknown> & Window
            ).NovusPlugin_demo_plugin = moduleExport;
            queueMicrotask(() => node.dispatchEvent(new Event('load')));
          }
        }
      },
    );

    await expect(
      loadPluginComponents('demo-plugin', undefined, { endpoint: 'admin' }),
    ).rejects.toThrow(/setup\(\) failed/);

    moduleExport = {
      DemoWidget: { name: 'DemoWidget' },
      setup: succeedingSetup,
    };

    const mod = await loadPluginComponents('demo-plugin', undefined, {
      endpoint: 'admin',
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(failingSetup).toHaveBeenCalledTimes(1);
    expect(succeedingSetup).toHaveBeenCalledTimes(1);
    expect(mod).toBe(moduleExport);
  });

  it('rejects calls that omit plugin loader scope', async () => {
    await expect(
      loadPluginComponents(
        'demo-plugin',
        undefined,
        {} as Parameters<typeof loadPluginComponents>[2],
      ),
    ).rejects.toThrow(/Plugin loader scope is required/);
  });

  it('rejects calls that pass both endpoint and publicEndpoint', async () => {
    await expect(
      loadPluginComponents('demo-plugin', undefined, {
        endpoint: 'admin',
        publicEndpoint: 'tenant',
      } as unknown as Parameters<typeof loadPluginComponents>[2]),
    ).rejects.toThrow(/either endpoint or publicEndpoint/);
  });
});
