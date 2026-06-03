import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, normalize } from 'node:path';
import process from 'node:process';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { novusPluginsLoader } from '../../../build/vite-plugin-novus-plugins';

function invokePluginHook<TArgs extends unknown[], TResult>(
  hook:
    | ((...args: TArgs) => TResult)
    | undefined
    | { handler: (...args: TArgs) => TResult },
  ...args: TArgs
): TResult | undefined {
  if (!hook) {
    return undefined;
  }
  return typeof hook === 'function' ? hook(...args) : hook.handler(...args);
}

function createPluginFixture(): {
  cleanup: () => void;
  pluginsDir: string;
  srcEntry: string;
} {
  const root = mkdtempSync(join(tmpdir(), 'novus-plugin-dev-'));
  const pluginsDir = join(root, 'backend', 'plugins');
  const pluginDir = join(pluginsDir, 'demo-plugin');
  const frontendDir = join(pluginDir, 'frontend');
  const srcDir = join(frontendDir, 'src');
  const srcEntry = join(srcDir, 'index.ts');

  mkdirSync(srcDir, { recursive: true });
  writeFileSync(
    join(pluginDir, 'plugin.yaml'),
    [
      'name: demo-plugin',
      'version: "1.0.0"',
      'display_name:',
      '  zh-CN: "Demo"',
      '  en: "Demo"',
      'description:',
      '  zh-CN: "Demo"',
      '  en: "Demo"',
      'author: ""',
      'icon: ""',
      'scope: admin_only',
      'capabilities: []',
      'dependencies:',
      '  python: []',
      '  plugins: []',
      'pricing:',
      '  type: free',
      'extensions:',
      '  frontend:',
      '    pages:',
      '      - name: "demo_page"',
      '        path: "/admin/plugins/demo-plugin"',
      '        component: "DemoPage"',
      '        scope: "admin"',
      '        title:',
      '          zh-CN: "Demo"',
      '          en: "Demo"',
      '    dev:',
      '      entry: "src/index.ts"',
      '',
    ].join('\n'),
    'utf8',
  );
  writeFileSync(
    join(frontendDir, 'package.json'),
    JSON.stringify({
      name: '@novus-plugin/demo-plugin',
      private: true,
      dependencies: {
        vue: '^3.5.0',
      },
    }),
    'utf8',
  );
  writeFileSync(srcEntry, 'export const DemoPage = {};', 'utf8');

  return {
    cleanup: () => rmSync(root, { force: true, recursive: true }),
    pluginsDir,
    srcEntry,
  };
}

describe('vite-plugin-novus-plugins', () => {
  const cleanups: Array<() => void> = [];

  afterEach(() => {
    vi.restoreAllMocks();
    while (cleanups.length > 0) {
      cleanups.pop()?.();
    }
  });

  it('enables dev fs access and optimizeDeps for plugin frontend dependencies', () => {
    const fixture = createPluginFixture();
    cleanups.push(fixture.cleanup);

    const plugin = novusPluginsLoader({ pluginsDir: fixture.pluginsDir });
    const configResult = invokePluginHook(
      plugin.config,
      {},
      { command: 'serve', mode: 'development' },
    );

    expect(configResult).toEqual({
      optimizeDeps: {
        include: ['vue'],
      },
      server: {
        fs: {
          strict: false,
        },
      },
    });
  });

  it('serves vite-transformed plugin dev entry through __plugin_dev__ middleware', async () => {
    const fixture = createPluginFixture();
    cleanups.push(fixture.cleanup);

    const plugin = novusPluginsLoader({ pluginsDir: fixture.pluginsDir });
    invokePluginHook(plugin.configResolved, {
      build: { outDir: 'dist' },
      command: 'serve',
      logger: {
        error: vi.fn(),
        info: vi.fn(),
      },
      root: process.cwd(),
    } as any);

    let middleware:
      | ((req: { url?: string }, res: any, next: () => void) => Promise<void>)
      | undefined;
    const transformRequest = vi
      .fn()
      .mockResolvedValue({ code: 'export const DemoPage = {};' });
    const watcherAdd = vi.fn();

    invokePluginHook(plugin.configureServer, {
      middlewares: {
        use(handler: typeof middleware) {
          middleware = handler;
        },
      },
      transformRequest,
      watcher: {
        add: watcherAdd,
      },
    } as any);

    expect(watcherAdd).toHaveBeenCalledWith(dirname(fixture.srcEntry));
    expect(middleware).toBeDefined();

    const headers: Record<string, string> = {};
    let body = '';
    const next = vi.fn();
    const res = {
      end(value: string) {
        body = value;
      },
      setHeader(name: string, value: string) {
        headers[name] = value;
      },
      statusCode: 0,
    };

    await middleware?.(
      { url: '/__plugin_dev__/demo-plugin/entry?t=123' },
      res,
      next,
    );

    expect(transformRequest).toHaveBeenCalledWith(
      `/@fs/${normalize(fixture.srcEntry).replaceAll('\\', '/')}`,
    );
    expect(headers['Content-Type']).toBe('application/javascript');
    expect(headers['Cache-Control']).toBe('no-cache, no-store');
    expect(res.statusCode).toBe(200);
    expect(body).toBe('export const DemoPage = {};');
    expect(next).not.toHaveBeenCalled();
  });

  it('falls through when the requested plugin has no dev source entry', async () => {
    const fixture = createPluginFixture();
    cleanups.push(fixture.cleanup);

    rmSync(fixture.srcEntry);

    const plugin = novusPluginsLoader({ pluginsDir: fixture.pluginsDir });
    invokePluginHook(plugin.configResolved, {
      build: { outDir: 'dist' },
      command: 'serve',
      logger: {
        error: vi.fn(),
        info: vi.fn(),
      },
      root: process.cwd(),
    } as any);

    let middleware:
      | ((req: { url?: string }, res: any, next: () => void) => Promise<void>)
      | undefined;
    const transformRequest = vi.fn();
    const next = vi.fn();

    invokePluginHook(plugin.configureServer, {
      middlewares: {
        use(handler: typeof middleware) {
          middleware = handler;
        },
      },
      transformRequest,
      watcher: {
        add: vi.fn(),
      },
    } as any);

    await middleware?.(
      { url: '/__plugin_dev__/demo-plugin/entry?t=456' },
      {
        end: vi.fn(),
        setHeader: vi.fn(),
        statusCode: 0,
      },
      next,
    );

    expect(transformRequest).not.toHaveBeenCalled();
    expect(next).toHaveBeenCalledTimes(1);
  });
});
