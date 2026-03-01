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

import { existsSync, readFileSync, readdirSync, statSync, cpSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Plugin, ResolvedConfig } from 'vite';

const _dirname = typeof __dirname !== 'undefined'
  ? __dirname
  : dirname(fileURLToPath(import.meta.url));

/** web-antd 根目录（_dirname = src/utils/ → ../../ = web-antd/） */
const hostAppRoot = resolve(_dirname, '..', '..');

/**
 * 使用宿主应用的 node_modules 上下文来解析裸模块说明符。
 * 插件源码位于 backend/plugins/ 目录外，无法通过标准 Node 模块解析
 * 走到宿主 node_modules，因此需要显式指定解析基路径。
 */
const hostRequire = createRequire(resolve(hostAppRoot, 'package.json'));

function _norm(p: string): string {
  return p.replaceAll('\\', '/');
}

/**
 * 从插件目录下的文件路径中提取插件名称
 * 如 /path/to/plugins/novusdoc-pro/frontend/src/index.ts → 'novusdoc-pro'
 */
function _extractPluginName(normalizedFilePath: string, normalizedPluginsDir: string): string | null {
  if (!normalizedFilePath.startsWith(normalizedPluginsDir)) return null;
  const rel = normalizedFilePath.slice(normalizedPluginsDir.length).replace(/^\//, '');
  const firstSlash = rel.indexOf('/');
  return firstSlash > 0 ? rel.slice(0, firstSlash) : rel || null;
}


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

/**
 * 检查插件声明的 npm 依赖是否已安装到宿主 node_modules。
 * 缺失依赖的插件直接标记为 blocked 并跳过编译。
 * 插件的 npm 依赖由后端启用生命周期负责安装，Vite 侧不自动安装。
 */
function _checkPluginNpmDeps(
  plugins: PluginEntry[],
  pluginsDir: string,
  cfg: ResolvedConfig,
): Set<string> {
  const blocked = new Set<string>();

  for (const p of plugins) {
    if (!p.srcEntry) continue;
    const yamlPath = join(pluginsDir, p.name, 'plugin.yaml');
    if (!existsSync(yamlPath)) continue;

    try {
      const content = readFileSync(yamlPath, 'utf-8');
      // 简易解析 npm_dependencies 列表（避免引入 yaml 解析器）
      const match = content.match(/npm_dependencies:\s*\n((?:\s+-\s+.+\n?)*)/);
      if (!match) continue;

      const deps = (match[1] ?? '')
        .split('\n')
        .map((line) => line.replace(/^\s*-\s*/, '').trim())
        .filter(Boolean);

      const missing: string[] = [];
      for (const dep of deps) {
        // 提取纯包名（去掉版本号）：
        // "@tiptap/vue-3"       → "@tiptap/vue-3"
        // "@tiptap/vue-3@^2.0"  → "@tiptap/vue-3"
        // "yjs"                 → "yjs"
        // "yjs@^13.0.0"         → "yjs"
        const pkgName = dep.startsWith('@')
          ? dep.replace(/^(@[^/]+\/[^@]+).*$/, '$1')
          : dep.replace(/@.*$/, '');
        // 直接检查 node_modules 目录，避免 require.resolve 缓存问题
        // pnpm workspace 会在 web-antd/node_modules 或 frontend/node_modules 创建链接
        const inApp = join(hostAppRoot, 'node_modules', pkgName);
        const inRoot = join(hostAppRoot, '..', '..', 'node_modules', pkgName);
        if (!existsSync(inApp) && !existsSync(inRoot)) {
          missing.push(dep);
        }
      }

      if (missing.length === 0) continue;

      // 依赖缺失 → 跳过该插件（不自动安装，由后端启用流程负责）
      blocked.add(p.name);
      cfg.logger.info(
        `[novus-plugins] Plugin '${p.name}' skipped — ${missing.length} npm dep(s) not installed: ` +
        missing.join(', ') +
        `. Enable the plugin in admin panel to auto-install.`,
      );
    } catch {
      // plugin.yaml 解析失败不阻塞启动
    }
  }

  return blocked;
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

  /** 依赖缺失的插件名集合，在 configResolved 中填充 */
  let blockedPlugins = new Set<string>();

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

      // 检查插件声明的 npm 依赖是否已安装，依赖缺失的插件将被跳过
      blockedPlugins = _checkPluginNpmDeps(plugins, pluginsDir, config);
    },

    // dev 模式：监控 backend/plugins/ 目录变更，自动触发 HMR
    configureServer(server) {
      if (isBuild) return;
      server.watcher.add(pluginsDir);

      // 当插件目录发生增删时，使 registry 虚拟模块失效并触发 HMR 更新
      const invalidateRegistry = () => {
        const mod = server.moduleGraph.getModuleById(RESOLVED_REGISTRY);
        if (mod) {
          server.moduleGraph.invalidateModule(mod);
          server.ws.send({ type: 'full-reload', path: '*' });
          config.logger.info('[novus-plugins] Plugin directory changed, triggering reload');
        }
      };

      server.watcher.on('addDir', (path: string) => {
        if (_norm(path).startsWith(_norm(pluginsDir))) invalidateRegistry();
      });
      server.watcher.on('unlinkDir', (path: string) => {
        if (_norm(path).startsWith(_norm(pluginsDir))) invalidateRegistry();
      });

      config.logger.info(`[novus-plugins] Watching ${pluginsDir} for changes`);
    },

    async resolveId(id, importer) {
      // virtual:novus-plugins-registry
      if (id === VIRTUAL_REGISTRY) {
        return RESOLVED_REGISTRY;
      }
      // virtual:novus-plugin-{name}
      if (id.startsWith(VIRTUAL_PREFIX)) {
        return '\0' + id.slice('virtual:'.length);
      }

      // 插件源码文件中的裸模块说明符（如 @tiptap/vue-3、ant-design-vue）
      // 无法通过标准目录上溯找到宿主 node_modules，需要从宿主上下文解析。
      if (
        importer
        && !id.startsWith('.')
        && !id.startsWith('/')
        && !id.startsWith('\0')
        && !id.startsWith('virtual:')
        && !/^[a-zA-Z]:/.test(id)
      ) {
        const normImporter = _norm(importer);
        const normPluginsDir = _norm(pluginsDir);
        if (normImporter.startsWith(normPluginsDir)) {
          // 用宿主根目录的虚拟文件作为 importer，让 Vite 按宿主上下文解析
          const fakeImporter = resolve(hostAppRoot, '__plugin_resolve__.ts');
          const resolved = await this.resolve(id, fakeImporter, { skipSelf: true });
          if (resolved && !resolved.external) {
            return resolved;
          }
          // Vite 无法解析时，尝试 Node require 兜底
          try {
            return hostRequire.resolve(id);
          } catch {
            // 依赖不可 resolve → 自动将该插件标记为 blocked，防止后续编译报错
            const pluginName = _extractPluginName(normImporter, normPluginsDir);
            if (pluginName && !blockedPlugins.has(pluginName)) {
              blockedPlugins.add(pluginName);
              config.logger.warn(
                `[novus-plugins] Plugin '${pluginName}' SKIPPED — ` +
                `cannot resolve '${id}' (dependency not installed). ` +
                `Enable the plugin and install its dependencies first.`,
              );
            }
            // 返回空模块而非 null，阻止 Vite 继续尝试解析并报错
            return { id: `\0blocked-dep:${id}`, external: false };
          }
        }
      }

      return null;
    },

    load(id) {
      // 被 blocked 的依赖：返回空模块，防止 Vite 报错
      if (id.startsWith('\0blocked-dep:')) {
        return 'export default {};\n';
      }

      // Registry 模块：导出所有有源码的内置插件
      // 每次加载时重新扫描目录，确保卸载插件后不再引用已删除文件
      if (id === RESOLVED_REGISTRY) {
        const currentPlugins = scanPlugins(pluginsDir);
        const srcPlugins = currentPlugins.filter((p) => p.srcEntry && !blockedPlugins.has(p.name));
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

        // 依赖缺失的插件不加载
        if (blockedPlugins.has(pluginName)) {
          return 'export default {};';
        }

        // 动态查找插件入口（不依赖启动时的 plugins 缓存，支持运行时安装的插件）
        const srcEntry = join(pluginsDir, pluginName, 'frontend', 'src', 'index.ts');
        if (!existsSync(srcEntry)) {
          return 'export default {};';
        }

        // Re-export 插件源码入口（仅 named exports，插件 index.ts 无 default export）
        const normalizedPath = srcEntry.replaceAll('\\', '/');
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
