/**
 * Vite 自定义插件：novus-plugin-loader
 *
 * dev 模式：扫描 backend/plugins/×/frontend/src/index.ts → 虚拟模块 → Vite 编译 SFC（HMR）
 * build 模式：有源码的插件编入主 bundle（code split）；只有 dist/ 的插件复制到输出目录
 *
 * 虚拟模块:
 *   virtual:novus-plugin-{name}      → re-export 插件 index.ts
 *   virtual:novus-plugins-registry   → export BUILTIN_PLUGINS 注册表
 */

import { existsSync, readdirSync, statSync, cpSync, mkdirSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Plugin, ResolvedConfig } from 'vite';

const _dirname = typeof __dirname !== 'undefined'
  ? __dirname
  : dirname(fileURLToPath(import.meta.url));

interface PluginEntry {
  name: string;
  /** 插件 frontend/src/index.ts 绝对路径（有源码时） */
  srcEntry: string | null;
  /** 插件 frontend/dist/ 绝对路径（有预编译产物时） */
  distDir: string | null;
}

const VIRTUAL_PREFIX = 'virtual:novus-plugin-';
const VIRTUAL_REGISTRY = 'virtual:novus-plugins-registry';
const RESOLVED_PREFIX = '\0novus-plugin-';
const RESOLVED_REGISTRY = '\0novus-plugins-registry';

/**
 * 扫描 backend/plugins/ 目录，发现所有有前端的插件
 */
function scanPlugins(pluginsDir: string): PluginEntry[] {
  if (!existsSync(pluginsDir)) return [];

  const entries: PluginEntry[] = [];

  for (const dirName of readdirSync(pluginsDir)) {
    const pluginRoot = join(pluginsDir, dirName);
    if (!statSync(pluginRoot).isDirectory()) continue;

    const srcEntry = join(pluginRoot, 'frontend', 'src', 'index.ts');
    const distDir = join(pluginRoot, 'frontend', 'dist');

    const hasSrc = existsSync(srcEntry);
    const hasDist = existsSync(distDir) && existsSync(join(distDir, 'index.js'));

    if (hasSrc || hasDist) {
      entries.push({
        name: dirName,
        srcEntry: hasSrc ? srcEntry : null,
        distDir: hasDist ? distDir : null,
      });
    }
  }

  return entries;
}

export interface NovusPluginsOptions {
  /**
   * backend/plugins/ 目录的绝对路径
   * @default 自动推导（从 web-antd 根目录出发）
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

  // Scan eagerly so config() (which runs before configResolved) can use the result
  const plugins: PluginEntry[] = scanPlugins(pluginsDir);

  return {
    name: 'novus-plugins-loader',
    enforce: 'pre',

    configResolved(resolvedConfig) {
      config = resolvedConfig;
      isBuild = config.command === 'build';

      if (plugins.length > 0) {
        const names = plugins.map((p) => {
          const mode = p.srcEntry ? 'src' : 'dist';
          return `${p.name} (${mode})`;
        });
        config.logger.info(
          `[novus-plugins] Found ${plugins.length} plugin(s): ${names.join(', ')}`,
        );
      }
    },

    // dev 模式：监控 backend/plugins/ 目录变更，自动触发 HMR
    configureServer(server) {
      if (isBuild) return;
      server.watcher.add(pluginsDir);
      config.logger.info(`[novus-plugins] Watching ${pluginsDir} for changes`);
    },

    resolveId(id) {
      // virtual:novus-plugins-registry
      if (id === VIRTUAL_REGISTRY) {
        return RESOLVED_REGISTRY;
      }
      // virtual:novus-plugin-{name}
      if (id.startsWith(VIRTUAL_PREFIX)) {
        return '\0' + id.slice('virtual:'.length);
      }
      return null;
    },

    load(id) {
      // Registry 模块：导出所有有源码的内置插件
      if (id === RESOLVED_REGISTRY) {
        const srcPlugins = plugins.filter((p) => p.srcEntry);
        if (srcPlugins.length === 0) {
          return 'export const BUILTIN_PLUGINS = {};\n';
        }

        const imports: string[] = [];
        const entries: string[] = [];

        for (const p of srcPlugins) {
          const varName = `__plugin_${p.name.replaceAll('-', '_')}`;
          imports.push(
            `const ${varName} = () => import('${VIRTUAL_PREFIX}${p.name}');`,
          );
          entries.push(`  '${p.name}': ${varName},`);
        }

        return [
          ...imports,
          '',
          'export const BUILTIN_PLUGINS = {',
          ...entries,
          '};',
          '',
        ].join('\n');
      }

      // 单个插件虚拟模块
      if (id.startsWith(RESOLVED_PREFIX)) {
        const pluginName = id.slice(RESOLVED_PREFIX.length);
        const entry = plugins.find((p) => p.name === pluginName);

        if (!entry?.srcEntry) {
          return 'export default {};';
        }

        // Re-export 插件源码入口（仅 named exports，插件 index.ts 无 default export）
        const normalizedPath = entry.srcEntry.replaceAll('\\', '/');
        return `export * from '${normalizedPath}';\n`;
      }

      return null;
    },

    // build 模式：将只有 dist/ 的插件复制到构建输出目录
    writeBundle(outputOptions) {
      if (!isBuild) return;

      const outDir = outputOptions.dir
        ?? (config.build?.outDir
          ? resolve(config.root, config.build.outDir)
          : resolve(config.root, 'dist'));

      for (const plugin of plugins) {
        // 只有 dist/ 且没有源码的插件 → 复制到 plugin-assets/
        if (!plugin.srcEntry && plugin.distDir) {
          const targetDir = join(outDir, 'plugin-assets', plugin.name);
          mkdirSync(targetDir, { recursive: true });
          cpSync(plugin.distDir, targetDir, { recursive: true });
          config.logger.info(
            `[novus-plugins] Copied dist/ for '${plugin.name}' → plugin-assets/${plugin.name}/`,
          );
        }
      }
    },

    // dev 模式：配置插件目录的解析（让插件 SFC import 主项目依赖）
    config() {
      return {
        resolve: {
          alias: {
            '@novus/plugin-shared': resolve(
              _dirname, 'plugin-shared.ts',
            ),
          },
        },
        // 排除插件虚拟模块的预构建（插件源码在项目根目录外，不走 optimizeDeps）
        optimizeDeps: {
          exclude: plugins
            .filter((p) => p.srcEntry)
            .map((p) => `${VIRTUAL_PREFIX}${p.name}`),
        },
      };
    },
  };
}
