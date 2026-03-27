/**
 * Vite custom plugin: novus-plugin-loader
 * Vite 自定义插件：novus-plugin-loader
 *
 * Build mode: copies backend/plugins/{name}/frontend/dist to host output directory plugin-assets/
 * Dev mode: directly transpiles src/ source via Vite, code changes are immediately visible without pre-building UMD bundles
 * build 模式：将 backend/plugins/{name}/frontend/dist 复制到宿主输出目录 plugin-assets/
 * dev 模式：直接通过 Vite 转译 src/ 源码，改代码即刷新可见，无需预先构建 UMD 包
 */

import type { Plugin, ResolvedConfig } from 'vite';

import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
} from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, relative, resolve } from 'node:path';

import { load as parseYaml } from 'js-yaml';

interface PluginEntry {
  name: string;
  /** Plugin frontend/dist/ absolute path (when pre-compiled assets exist) / 插件 frontend/dist/ 绝对路径（有预编译产物时） */
  distDir: null | string;
  /** Plugin frontend dev entry absolute path (when source exists, preferred in dev mode) / 插件前端开发入口绝对路径（有源码时，dev 模式优先使用） */
  srcEntry: null | string;
  /** Plugin frontend/ absolute path / 插件 frontend/ 绝对路径 */
  frontendDir: null | string;
  /** Package names from plugin package.json dependencies (resolved from plugin node_modules in dev mode) / 插件 package.json dependencies 的包名集合（dev 模式从插件 node_modules 解析） */
  deps: Set<string>;
}

function asRecord(value: unknown): null | Record<string, unknown> {
  return value && typeof value === 'object'
    ? (value as Record<string, unknown>)
    : null;
}

function normalizeFrontendContractPath(rawPath: string): null | string {
  const normalized = (rawPath || '')
    .trim()
    .replaceAll('\\', '/')
    .replace(/^\/+/, '');

  if (!normalized || normalized === '.') {
    return null;
  }

  const segments = normalized.split('/');
  if (
    segments.some(
      (segment) =>
        !segment ||
        segment === '.' ||
        segment === '..' ||
        !/^[\w.-]+$/.test(segment),
    )
  ) {
    return null;
  }

  return segments.join('/');
}

function resolvePluginFrontendFile(
  frontendDir: string,
  rawPath: string,
): null | string {
  const normalized = normalizeFrontendContractPath(rawPath);
  if (!normalized) {
    return null;
  }

  const target = resolve(frontendDir, normalized);
  const rel = relative(frontendDir, target);
  if (rel.startsWith('..') || rel === '') {
    return null;
  }

  return target;
}

function resolvePluginDevEntry(
  pluginRoot: string,
  frontendDir: string,
): null | string {
  const manifestPath = join(pluginRoot, 'plugin.yaml');
  const defaultEntry = resolvePluginFrontendFile(frontendDir, 'src/index.ts');
  if (!existsSync(manifestPath)) {
    return defaultEntry;
  }

  try {
    const manifest = asRecord(parseYaml(readFileSync(manifestPath, 'utf8')));
    const extensions = asRecord(manifest?.extensions);
    const frontend = asRecord(extensions?.frontend);
    const dev = asRecord(frontend?.dev);
    const configuredEntry =
      typeof dev?.entry === 'string' && dev.entry.trim()
        ? dev.entry
        : 'src/index.ts';
    return resolvePluginFrontendFile(frontendDir, configuredEntry);
  } catch {
    return defaultEntry;
  }
}

/**
 * Scan backend/plugins/ directory to discover all plugins with frontend
 * 扫描 backend/plugins/ 目录，发现所有有前端的插件
 */
function scanPlugins(pluginsDir: string): PluginEntry[] {
  if (!existsSync(pluginsDir)) return [];

  const entries: PluginEntry[] = [];

  for (const dirName of readdirSync(pluginsDir)) {
    const pluginRoot = join(pluginsDir, dirName);
    if (!statSync(pluginRoot).isDirectory()) continue;

    const frontendDir = join(pluginRoot, 'frontend');
    if (!existsSync(frontendDir) || !statSync(frontendDir).isDirectory())
      continue;

    const distDir = join(frontendDir, 'dist');
    const srcEntry = resolvePluginDevEntry(pluginRoot, frontendDir);
    const hasDist = existsSync(distDir) && statSync(distDir).isDirectory();
    const hasSrc = Boolean(srcEntry && existsSync(srcEntry));

    if (hasDist || hasSrc) {
      let deps = new Set<string>();
      try {
        const pkgPath = join(frontendDir, 'package.json');
        if (existsSync(pkgPath)) {
          const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
          if (pkg.dependencies) {
            deps = new Set(Object.keys(pkg.dependencies));
          }
        }
      } catch {
        // ignore
      }

      entries.push({
        name: dirName,
        distDir: hasDist ? distDir : null,
        srcEntry: hasSrc ? srcEntry : null,
        frontendDir,
        deps,
      });
    }
  }

  return entries;
}

function getPluginMode(
  plugin: PluginEntry,
  isBuildMode: boolean,
): 'dev-src' | 'dist' | 'no-assets' | 'no-dist' {
  if (isBuildMode) {
    return plugin.distDir ? 'dist' : 'no-dist';
  }

  if (plugin.srcEntry) {
    return 'dev-src';
  }

  return plugin.distDir ? 'dist' : 'no-assets';
}

export interface NovusPluginsOptions {
  /**
   * Absolute path to backend/plugins/ directory
   * Example: E:/git_clone/novusai-saas-yudi/backend/plugins
   * backend/plugins/ 目录的绝对路径
   * 例如: E:/git_clone/novusai-saas-yudi/backend/plugins
   */
  pluginsDir?: string;
}

export function novusPluginsLoader(options: NovusPluginsOptions = {}): Plugin {
  let config: ResolvedConfig;
  let isBuild = false;

  if (!options.pluginsDir) {
    throw new Error(
      '[novus-plugins-loader] pluginsDir is required. ' +
        'Pass the absolute path to backend/plugins/ in vite.config.mts.',
    );
  }
  const pluginsDir = options.pluginsDir;
  const initialPlugins: PluginEntry[] = scanPlugins(pluginsDir);
  const getPlugins = (): PluginEntry[] => {
    return isBuild ? initialPlugins : scanPlugins(pluginsDir);
  };

  return {
    name: 'novus-plugins-loader',
    enforce: 'post',

    config(_userConfig, { command }) {
      if (command === 'serve') {
        const discoveredPlugins = getPlugins();
        const hasPluginSrc = discoveredPlugins.some((p) => p.srcEntry);
        if (!hasPluginSrc) return undefined;

        const allPluginDeps: string[] = [];
        for (const p of discoveredPlugins) {
          for (const dep of p.deps) {
            if (!allPluginDeps.includes(dep)) allPluginDeps.push(dep);
          }
        }

        return {
          server: { fs: { strict: false } },
          optimizeDeps:
            allPluginDeps.length > 0 ? { include: allPluginDeps } : undefined,
        };
      }
    },

    configResolved(resolvedConfig) {
      config = resolvedConfig;
      isBuild = config.command === 'build';

      const discoveredPlugins = getPlugins();
      if (discoveredPlugins.length > 0) {
        const names = discoveredPlugins.map((p) => {
          const mode = getPluginMode(p, isBuild);
          return `${p.name}(${mode})`;
        });
        config.logger.info(
          `[novus-plugins] Found ${discoveredPlugins.length} plugin(s): ${names.join(', ')}`,
        );
      }
    },

    async resolveId(id, importer, resolveOptions) {
      if (isBuild || !importer) return null;

      if (id === '@novus/plugin-shared') {
        return resolve(config.root, 'src/utils/plugin-shared.ts');
      }

      if (
        id.startsWith('.') ||
        id.startsWith('/') ||
        id.startsWith('\0') ||
        id.startsWith('/@')
      ) {
        return null;
      }

      const normalizedImporter = importer.replaceAll('\\', '/');
      const plugin = getPlugins().find((p) => {
        if (!p.frontendDir) return false;
        return normalizedImporter.startsWith(
          p.frontendDir.replaceAll('\\', '/'),
        );
      });
      if (!plugin?.frontendDir) return null;

      const pkgName = id.startsWith('@')
        ? id.split('/').slice(0, 2).join('/')
        : (id.split('/')[0] ?? '');
      if (!pkgName) {
        return null;
      }

      if (plugin.deps.has(pkgName)) {
        try {
          const req = createRequire(join(plugin.frontendDir, 'package.json'));
          return { id: req.resolve(id) };
        } catch {
          // continue
        }
      }

      const defaultResolved = await this.resolve(id, importer, {
        ...resolveOptions,
        skipSelf: true,
      });
      if (defaultResolved) return defaultResolved;

      try {
        const req = createRequire(join(plugin.frontendDir, 'package.json'));
        return { id: req.resolve(id) };
      } catch {
        return null;
      }
    },

    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const requestUrl = new URL(req.url ?? '/', 'http://127.0.0.1');
        const match = requestUrl.pathname.match(
          /^\/__plugin_dev__\/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\/entry$/,
        );
        if (!match) return next();

        const pluginName = match[1];
        const plugin = getPlugins().find((p) => p.name === pluginName);
        if (!plugin) return next();

        let srcEntry = plugin.srcEntry;
        const requestedEntry = requestUrl.searchParams.get('entry') || '';
        if (requestedEntry && plugin.frontendDir) {
          const requestedPath = resolvePluginFrontendFile(
            plugin.frontendDir,
            requestedEntry,
          );
          if (requestedPath && existsSync(requestedPath)) {
            srcEntry = requestedPath;
          }
        }

        if (!srcEntry) return next();

        try {
          const fsUrl = `/@fs/${srcEntry.replaceAll('\\', '/')}`;
          const result = await server.transformRequest(fsUrl);
          if (result) {
            res.setHeader('Content-Type', 'application/javascript');
            res.setHeader('Cache-Control', 'no-cache, no-store');
            res.statusCode = 200;
            res.end(result.code);
            return;
          }
        } catch (error: unknown) {
          const message =
            error instanceof Error ? error.message : String(error);
          config.logger.error(
            `[novus-plugins] Transform failed for '${pluginName}': ${message}`,
          );
        }

        next();
      });

      for (const plugin of getPlugins()) {
        if (!plugin.srcEntry) continue;
        const watchDir = dirname(plugin.srcEntry);
        if (existsSync(watchDir)) {
          server.watcher.add(watchDir);
        }
      }
    },

    writeBundle(outputOptions) {
      if (!isBuild) return;

      const outDir =
        outputOptions.dir ??
        (config.build?.outDir
          ? resolve(config.root, config.build.outDir)
          : resolve(config.root, 'dist'));

      for (const plugin of getPlugins()) {
        if (!plugin.distDir) continue;
        const targetDir = join(outDir, 'plugin-assets', plugin.name);
        mkdirSync(targetDir, { recursive: true });
        cpSync(plugin.distDir, targetDir, { recursive: true });
        config.logger.info(
          `[novus-plugins] Copied dist/ for '${plugin.name}' → plugin-assets/${plugin.name}/`,
        );
      }
    },
  };
}
