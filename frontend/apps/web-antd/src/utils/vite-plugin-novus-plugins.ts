/**
 * Vite 自定义插件：novus-plugin-loader
 *
 * build 模式：将 backend/plugins/{name}/frontend/dist 复制到宿主输出目录 plugin-assets/
 * dev 模式：直接通过 Vite 转译 src/ 源码，改代码即刷新可见，无需预先构建 UMD 包
 */

import type { Plugin, ResolvedConfig } from 'vite';

import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
} from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';

interface PluginEntry {
  name: string;
  /** 插件 frontend/dist/ 绝对路径（有预编译产物时） */
  distDir: null | string;
  /** 插件 frontend/src/index.ts 绝对路径（有源码时，dev 模式优先使用） */
  srcEntry: null | string;
  /** 插件 frontend/ 绝对路径 */
  frontendDir: null | string;
  /** 插件 package.json dependencies 的包名集合（dev 模式从插件 node_modules 解析） */
  deps: Set<string>;
}

/**
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
    const srcEntry = join(frontendDir, 'src', 'index.ts');
    const hasDist =
      existsSync(distDir) && existsSync(join(distDir, 'index.js'));
    const hasSrc = existsSync(srcEntry);

    if (hasDist || hasSrc) {
      // 读取 package.json dependencies（dev 模式用于区分插件专有依赖 vs 宿主共享依赖）
      let deps = new Set<string>();
      try {
        const pkgPath = join(frontendDir, 'package.json');
        if (existsSync(pkgPath)) {
          const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
          if (pkg.dependencies) {
            deps = new Set(Object.keys(pkg.dependencies));
          }
        }
      } catch { /* ignore */ }

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

export interface NovusPluginsOptions {
  /**
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

  const plugins: PluginEntry[] = scanPlugins(pluginsDir);

  return {
    name: 'novus-plugins-loader',
    enforce: 'post',

    // --------------------------------------------------
    // Dev 模式：允许 Vite 访问插件源码 & 依赖
    // --------------------------------------------------
    config(_userConfig, { command }) {
      if (command === 'serve') {
        const hasPluginSrc = plugins.some((p) => p.srcEntry);
        if (!hasPluginSrc) return undefined;

        // 收集所有插件的 dependencies，让 Vite 预打包
        const allPluginDeps: string[] = [];
        for (const p of plugins) {
          for (const dep of p.deps) {
            if (!allPluginDeps.includes(dep)) allPluginDeps.push(dep);
          }
        }

        return {
          // 关闭 strict 模式：dev 需同时访问宿主源码和 backend/plugins/ 插件源码
          server: { fs: { strict: false } },
          // 预打包插件专有依赖（CJS→ESM 转换 + 性能优化）
          optimizeDeps:
            allPluginDeps.length > 0
              ? { include: allPluginDeps }
              : undefined,
        };
      }
    },

    configResolved(resolvedConfig) {
      config = resolvedConfig;
      isBuild = config.command === 'build';

      if (plugins.length > 0) {
        const names = plugins.map((p) => {
          const mode = isBuild
            ? p.distDir
              ? 'dist'
              : 'no-dist'
            : p.srcEntry
              ? 'dev-src'
              : p.distDir
                ? 'dist'
                : 'no-assets';
          return `${p.name}(${mode})`;
        });
        config.logger.info(
          `[novus-plugins] Found ${plugins.length} plugin(s): ${names.join(', ')}`,
        );
      }
    },

    // --------------------------------------------------
    // Dev 模式：从插件 node_modules 解析插件专有依赖
    // --------------------------------------------------
    async resolveId(id, importer, resolveOptions) {
      if (isBuild || !importer) return null;

      // @novus/plugin-shared → 宿主 plugin-shared.ts（所有插件共享）
      if (id === '@novus/plugin-shared') {
        return resolve(config.root, 'src/utils/plugin-shared.ts');
      }

      if (
        id.startsWith('.') ||
        id.startsWith('/') ||
        id.startsWith('\0') ||
        id.startsWith('/@')
      )
        return null;

      const normalizedImporter = importer.replace(/\\/g, '/');
      const plugin = plugins.find((p) => {
        if (!p.frontendDir) return false;
        return normalizedImporter.startsWith(
          p.frontendDir.replace(/\\/g, '/'),
        );
      });
      if (!plugin?.frontendDir) return null;

      // 提取裸模块名（@vue-flow/core/xxx → @vue-flow/core）
      const pkgName = id.startsWith('@')
        ? id.split('/').slice(0, 2).join('/')
        : id.split('/')[0]!;

      // 插件 dependencies 中的包 → 从插件 node_modules 优先解析
      // 这避免宿主中同名包版本不兼容或未预打包的问题
      if (plugin.deps.has(pkgName)) {
        try {
          const req = createRequire(
            join(plugin.frontendDir, 'package.json'),
          );
          return { id: req.resolve(id) };
        } catch {
          // 插件 node_modules 没有，继续走默认解析
        }
      }

      // 非插件专有依赖（vue / ant-design-vue 等）→ Vite 默认解析
      const defaultResolved = await this.resolve(id, importer, {
        ...resolveOptions,
        skipSelf: true,
      });
      if (defaultResolved) return defaultResolved;

      // 最终回退：尝试从插件 node_modules 解析
      try {
        const req = createRequire(
          join(plugin.frontendDir, 'package.json'),
        );
        return { id: req.resolve(id) };
      } catch {
        return null;
      }
    },

    // --------------------------------------------------
    // Dev 模式：拦截 /plugin-assets/{name}/index.js
    //          → Vite 转译 src/index.ts 源码 → 返回 ESM
    // --------------------------------------------------
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const match = req.url?.match(
          /^\/plugin-assets\/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\/index\.js/,
        );
        if (!match) return next();

        const pluginName = match[1];
        const plugin = plugins.find((p) => p.name === pluginName);

        if (!plugin?.srcEntry) return next();

        try {
          const fsUrl = `/@fs/${plugin.srcEntry.replace(/\\/g, '/')}`;
          const result = await server.transformRequest(fsUrl);
          if (result) {
            res.setHeader('Content-Type', 'application/javascript');
            res.setHeader('Cache-Control', 'no-cache, no-store');
            res.statusCode = 200;
            res.end(result.code);
            return;
          }
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : String(e);
          config.logger.error(
            `[novus-plugins] Transform failed for '${pluginName}': ${msg}`,
          );
        }

        next();
      });

      // 监听插件源码目录，文件变动触发浏览器刷新
      for (const plugin of plugins) {
        if (!plugin.frontendDir) continue;
        const srcDir = join(plugin.frontendDir, 'src');
        if (existsSync(srcDir)) {
          server.watcher.add(srcDir);
        }
      }
    },

    // --------------------------------------------------
    // Build 模式：将 dist/ 复制到构建输出目录
    // --------------------------------------------------
    writeBundle(outputOptions) {
      if (!isBuild) return;

      const outDir =
        outputOptions.dir ??
        (config.build?.outDir
          ? resolve(config.root, config.build.outDir)
          : resolve(config.root, 'dist'));

      for (const plugin of plugins) {
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
