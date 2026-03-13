/**
 * Plugin frontend dynamic loader utility
 * 插件前端动态加载工具
 *
 * Load via injection mode only:
 *   - Runtime plugins (prod/dev) → load UMD bundle via <script> tag
 * 仅通过注入模式加载：
 *   - 运行时插件（生产/开发）→ 通过 <script> 标签加载 UMD 包
 *
 * Design constraints:
 *   - Do not compile backend/plugins source into host frontend bundle
 *   - Plugins must maintain independent build and release
 * 设计约束：
 *   - 不将 backend/plugins 源码编译进宿主前端 bundle
 *   - 插件必须保持独立构建与独立发布
 */

/** Loaded plugin cache / 已加载的插件缓存 */
const loadedPlugins: Map<string, Record<string, unknown>> = new Map();

/** Loading Promise cache (prevent duplicate loading) / 加载中的 Promise 缓存（防止重复加载） */
const loadingPromises: Map<
  string,
  Promise<Record<string, unknown>>
> = new Map();
/** CSS loading Promise cache (prevent duplicate loading) / CSS 解析中的 Promise 缓存（防止重复加载） */
const cssLoadingPromises: Map<string, Promise<void>> = new Map();

/** Unloaded plugins (prevent race with in-flight loading) / 已卸载集合（防止与加载中 Promise 竞态） */
const unloadedPlugins: Set<string> = new Set();

const SAFE_PLUGIN_NAME_RE = /^[a-z][\da-z]*(?:-[\da-z]+)*$/;
const SAFE_CSS_FILENAME_RE = /^[\w][\w.-]*\.css$/;

/**
 * Convert plugin name to global variable name: crm-module → NovusPlugin_crm_module
 * 将插件名转为全局变量名: crm-module → NovusPlugin_crm_module
 */
function toGlobalVarName(pluginName: string): string {
  return `NovusPlugin_${pluginName.replaceAll('-', '_')}`;
}

function _injectPluginCSS(pluginName: string, cssFileName: string): void {
  const basename = cssFileName.split('/').pop() || '';
  if (!SAFE_CSS_FILENAME_RE.test(basename)) {
    console.warn(
      `[PluginLoader] Rejected invalid CSS filename: '${cssFileName}' for plugin '${pluginName}'`,
    );
    return;
  }

  const normalized = basename.replaceAll(/[^\w-]/g, '_');
  const cssId = `novus-plugin-css-${pluginName}-${normalized}`;
  if (document.querySelector(`#${CSS.escape(cssId)}`)) {
    return;
  }

  const link = document.createElement('link');
  link.id = cssId;
  link.rel = 'stylesheet';
  link.href = `/plugin-assets/${pluginName}/${basename}`;
  document.head.append(link);
}

/**
 * Load plugin CSS by manifest declared styles list.
 * No HEAD probing to avoid browser console 404 noise.
 * 按 manifest 声明的 styles 列表加载插件 CSS。
 * 不做 HEAD 探测，避免浏览器控制台出现大量 404 噪音。
 */
async function loadPluginCSS(
  pluginName: string,
  cssFiles: string[] = [],
): Promise<void> {
  if (cssFiles.length === 0) {
    return;
  }

  const pending = cssLoadingPromises.get(pluginName);
  if (pending) {
    return pending;
  }

  const task = (async () => {
    const uniqueCss = [
      ...new Set(cssFiles.map((it) => it.trim()).filter(Boolean)),
    ];
    for (const cssFile of uniqueCss) {
      try {
        _injectPluginCSS(pluginName, cssFile);
      } catch (err) {
        console.warn(
          `[PluginLoader] CSS injection failed for '${pluginName}/${cssFile}':`,
          err,
        );
      }
    }
  })();

  cssLoadingPromises.set(pluginName, task);
  try {
    await task;
  } finally {
    cssLoadingPromises.delete(pluginName);
  }
}

/**
 * Dynamically load plugin UMD JS bundle (+ CSS)
 * 动态加载插件 UMD JS 包（+ CSS）
 *
 * @param pluginName - Plugin name (kebab-case) / 插件名（kebab-case）
 * @returns Plugin exported module object / 插件导出的模块对象
 */
export async function loadPluginComponents(
  pluginName: string,
  cssFiles: string[] = [],
): Promise<Record<string, unknown>> {
  if (!SAFE_PLUGIN_NAME_RE.test(pluginName)) {
    console.warn(
      `[PluginLoader] Rejected invalid plugin name: '${pluginName}'`,
    );
    return {};
  }

  // 已缓存
  const cached = loadedPlugins.get(pluginName);
  if (cached) return cached;

  // 正在加载中
  const existing = loadingPromises.get(pluginName);
  if (existing) return existing;

  unloadedPlugins.delete(pluginName);

  const promise = (async (): Promise<Record<string, unknown>> => {
    await loadPluginCSS(pluginName, cssFiles);

    let mod: Record<string, unknown>;

    if (import.meta.env.DEV) {
      const devUrl = `/plugin-assets/${pluginName}/index.js?t=${Date.now()}`;
      mod = (await import(/* @vite-ignore */ devUrl)) as Record<
        string,
        unknown
      >;
    } else {
      mod = await new Promise<Record<string, unknown>>((resolve, reject) => {
        const scriptUrl = `/plugin-assets/${pluginName}/index.js`;
        const script = document.createElement('script');
        script.src = scriptUrl;
        script.async = true;

        script.addEventListener('load', () => {
          const globalVar = toGlobalVarName(pluginName);
          const m = (window as unknown as Record<string, unknown>)[
            globalVar
          ] as Record<string, unknown> | undefined;

          if (m) {
            resolve(m);
            return;
          }
          script.remove();
          reject(
            new Error(
              `Plugin '${pluginName}' loaded but window.${globalVar} not found`,
            ),
          );
        });

        script.addEventListener('error', () => {
          script.remove();
          reject(new Error(`Failed to load plugin script: ${scriptUrl}`));
        });

        document.head.append(script);
      });
    }

    // Race guard: skip caching if plugin was unloaded during async load
    // / 竞态保护：异步加载期间若插件已卸载则跳过缓存
    if (unloadedPlugins.has(pluginName)) {
      return mod;
    }

    if (typeof mod.setup === 'function') {
      try {
        (mod.setup as () => void)();
      } catch (error) {
        console.error(
          `[PluginLoader] setup() failed for '${pluginName}':`,
          error,
        );
      }
    }
    loadedPlugins.set(pluginName, mod);
    return mod;
  })();

  loadingPromises.set(pluginName, promise);
  try {
    return await promise;
  } finally {
    loadingPromises.delete(pluginName);
  }
}

/**
 * Get a single exported component from a plugin
 * 获取插件导出的单个组件
 *
 * @param pluginName - Plugin name / 插件名
 * @param componentName - Component name (export key of plugin module) / 组件名（插件模块的导出 key）
 */
export async function getPluginComponent(
  pluginName: string,
  componentName: string,
): Promise<null | unknown> {
  try {
    const mod = await loadPluginComponents(pluginName);
    return mod[componentName] ?? null;
  } catch {
    console.error(
      `Failed to get component '${componentName}' from plugin '${pluginName}'`,
    );
    return null;
  }
}

/**
 * Check if a plugin is loaded
 * 检查插件是否已加载
 */
export function isPluginLoaded(pluginName: string): boolean {
  return loadedPlugins.has(pluginName);
}

/**
 * Unload plugin (clear cache + remove script tags)
 * 卸载插件（清除缓存 + 移除 script 标签）
 */
export function unloadPlugin(pluginName: string): void {
  unloadedPlugins.add(pluginName);
  loadedPlugins.delete(pluginName);
  loadingPromises.delete(pluginName);
  cssLoadingPromises.delete(pluginName);

  const scripts = document.querySelectorAll(
    `script[src*="/plugin-assets/${pluginName}/"]`,
  );
  for (const s of scripts) {
    s.remove();
  }
  const globalVar = toGlobalVarName(pluginName);
  (window as unknown as Record<string, unknown>)[globalVar] = undefined;

  const cssNodes = document.querySelectorAll(
    `[id^="novus-plugin-css-${pluginName}-"]`,
  );
  for (const cssNode of cssNodes) {
    cssNode.remove();
  }
}
