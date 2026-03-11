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

/**
 * Convert plugin name to global variable name: crm-module → NovusPlugin_crm_module
 * 将插件名转为全局变量名: crm-module → NovusPlugin_crm_module
 */
function toGlobalVarName(pluginName: string): string {
  return `NovusPlugin_${pluginName.replaceAll('-', '_')}`;
}

function _injectPluginCSS(pluginName: string, cssFileName: string): void {
  const normalized = cssFileName.replaceAll(/[^\w-]/g, '_');
  const cssId = `novus-plugin-css-${pluginName}-${normalized}`;
  if (document.querySelector(`#${CSS.escape(cssId)}`)) {
    return;
  }

  const link = document.createElement('link');
  link.id = cssId;
  link.rel = 'stylesheet';
  link.href = `/plugin-assets/${pluginName}/${cssFileName.replace(/^\/+/, '')}`;
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
      } catch {
        // 静默：不因 CSS 加载失败影响插件 JS 组件加载
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
  // 已缓存
  const cached = loadedPlugins.get(pluginName);
  if (cached) return cached;

  // 正在加载中
  const existing = loadingPromises.get(pluginName);
  if (existing) return existing;

  const promise = (async (): Promise<Record<string, unknown>> => {
    // 先记录 loadingPromise，再进行 await，避免并发窗口重复注入 script
    await loadPluginCSS(pluginName, cssFiles);

    let mod: Record<string, unknown>;

    if (import.meta.env.DEV) {
      // -------------------------------------------------
      // Dev 模式：Vite 转译源码 → ESM import()
      // 改插件代码后刷新浏览器即可，无需预先 build
      // -------------------------------------------------
      const devUrl = `/plugin-assets/${pluginName}/index.js?t=${Date.now()}`;
      mod = (await import(/* @vite-ignore */ devUrl)) as Record<
        string,
        unknown
      >;
    } else {
      // -------------------------------------------------
      // Production：UMD <script> 注入
      // -------------------------------------------------
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
          reject(
            new Error(
              `Plugin '${pluginName}' loaded but window.${globalVar} not found`,
            ),
          );
        });

        script.addEventListener('error', () => {
          reject(new Error(`Failed to load plugin script: ${scriptUrl}`));
        });

        document.head.append(script);
      });
    }

    // 调用插件 setup() 注册 i18n 等
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
  loadedPlugins.delete(pluginName);
  loadingPromises.delete(pluginName);
  // 移除 script 标签 + 清除全局变量
  const scripts = document.querySelectorAll(
    `script[src*="/plugin-assets/${pluginName}/"]`,
  );
  for (const s of scripts) {
    s.remove();
  }
  const globalVar = toGlobalVarName(pluginName);
  (window as unknown as Record<string, unknown>)[globalVar] = undefined;

  // 移除 CSS
  const cssNodes = document.querySelectorAll(
    `[id^="novus-plugin-css-${pluginName}-"]`,
  );
  for (const cssNode of cssNodes) {
    cssNode.remove();
  }
}
