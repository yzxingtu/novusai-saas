/**
 * 插件前端动态加载工具
 *
 * 双模式加载：
 *   1. 内置插件（dev/build 编入主 bundle）→ 从 BUILTIN_PLUGINS 注册表直接 import
 *   2. 运行时插件（生产环境安装）→ 通过 <script> 标签加载 UMD 包
 */

import { BUILTIN_PLUGINS as _RAW_BUILTINS } from 'virtual:novus-plugins-registry';

/** 可变的内置插件注册表（从虚拟模块复制，支持运行时禁用/恢复） */
const builtinLoaders = new Map<string, () => Promise<Record<string, unknown>>>(
  Object.entries(_RAW_BUILTINS as Record<string, () => Promise<Record<string, unknown>>>),
);

/** 已禁用的内置插件集合 */
const disabledBuiltins: Set<string> = new Set();

/** 已加载的插件缓存 */
const loadedPlugins: Map<string, Record<string, unknown>> = new Map();

/** 加载中的 Promise 缓存（防止重复加载） */
const loadingPromises: Map<string, Promise<Record<string, unknown>>> = new Map();

/**
 * 将插件名转为全局变量名: crm-module → NovusPlugin_crm_module
 */
function toGlobalVarName(pluginName: string): string {
  return `NovusPlugin_${pluginName.replaceAll('-', '_')}`;
}

/**
 * 加载插件 CSS 样式（如果存在）
 */
function loadPluginCSS(pluginName: string): void {
  const cssId = `novus-plugin-css-${pluginName}`;
  if (document.getElementById(cssId)) return;

  const link = document.createElement('link');
  link.id = cssId;
  link.rel = 'stylesheet';
  link.href = `/plugin-assets/${pluginName}/${pluginName}.css`;
  document.head.append(link);
}

/**
 * 动态加载插件 UMD JS 包（+ CSS）
 *
 * @param pluginName 插件名（kebab-case）
 * @returns 插件导出的模块对象
 */
export async function loadPluginComponents(
  pluginName: string,
): Promise<Record<string, unknown>> {
  // 已缓存
  const cached = loadedPlugins.get(pluginName);
  if (cached) return cached;

  // 正在加载中
  const existing = loadingPromises.get(pluginName);
  if (existing) return existing;

  // 优先级 1：内置插件（dev/build 时 Vite 编译的插件）
  const builtinLoader = disabledBuiltins.has(pluginName)
    ? undefined
    : builtinLoaders.get(pluginName);
  if (builtinLoader) {
    const promise = builtinLoader().then((mod) => {
      // 调用 setup() 注册 i18n 等
      if (typeof mod.setup === 'function') {
        try {
          (mod.setup as () => void)();
        } catch (err) {
          console.error(`[PluginLoader] setup() failed for '${pluginName}':`, err);
        }
      }
      loadedPlugins.set(pluginName, mod);
      // 暴露到 window 以支持跨插件检测（如 novusdoc 检测 novusdoc-pro）
      const globalVar = toGlobalVarName(pluginName);
      (window as unknown as Record<string, unknown>)[globalVar] = mod;
      loadingPromises.delete(pluginName);
      return mod;
    }).catch((err) => {
      loadingPromises.delete(pluginName);
      throw err;
    });
    loadingPromises.set(pluginName, promise);
    return promise;
  }

  // 优先级 2：UMD 动态加载（运行时安装的插件）
  loadPluginCSS(pluginName);

  const promise = new Promise<Record<string, unknown>>((resolve, reject) => {
    const cacheBust = import.meta.env.DEV ? `?t=${Date.now()}` : '';
    const scriptUrl = `/plugin-assets/${pluginName}/index.js${cacheBust}`;
    const script = document.createElement('script');
    script.src = scriptUrl;
    script.async = true;

    script.addEventListener('load', () => {
      const globalVar = toGlobalVarName(pluginName);
      const mod = (window as unknown as Record<string, unknown>)[globalVar] as
        | Record<string, unknown>
        | undefined;

      if (mod) {
        // 调用插件 setup() 注册 i18n 等
        if (typeof mod.setup === 'function') {
          try {
            (mod.setup as () => void)();
          } catch (err) {
            console.error(`[PluginLoader] setup() failed for '${pluginName}':`, err);
          }
        }
        loadedPlugins.set(pluginName, mod);
        resolve(mod);
      } else {
        reject(
          new Error(
            `Plugin '${pluginName}' loaded but window.${globalVar} not found`,
          ),
        );
      }
      loadingPromises.delete(pluginName);
    });

    script.addEventListener('error', () => {
      loadingPromises.delete(pluginName);
      reject(new Error(`Failed to load plugin script: ${scriptUrl}`));
    });

    document.head.append(script);
  });

  loadingPromises.set(pluginName, promise);
  return promise;
}

/**
 * 获取插件导出的单个组件
 *
 * @param pluginName 插件名
 * @param componentName 组件名（插件模块的导出 key）
 */
export async function getPluginComponent(
  pluginName: string,
  componentName: string,
): Promise<unknown | null> {
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
 * 检查插件是否已加载
 */
export function isPluginLoaded(pluginName: string): boolean {
  return loadedPlugins.has(pluginName);
}

/**
 * 卸载插件（清除缓存 + 移除 script 标签 + 标记内置插件为禁用）
 */
export function unloadPlugin(pluginName: string): void {
  loadedPlugins.delete(pluginName);
  loadingPromises.delete(pluginName);

  // 内置插件：标记为禁用（下次 loadPluginComponents 会跳过）
  if (builtinLoaders.has(pluginName)) {
    disabledBuiltins.add(pluginName);
  }

  // UMD 插件：移除 script 标签 + 清除全局变量
  const scripts = document.querySelectorAll(
    `script[src*="/plugin-assets/${pluginName}/"]`,
  );
  for (const s of scripts) {
    s.remove();
  }
  const globalVar = toGlobalVarName(pluginName);
  delete (window as unknown as Record<string, unknown>)[globalVar];

  // 移除 CSS
  const css = document.getElementById(`novus-plugin-css-${pluginName}`);
  if (css) css.remove();
}

/**
 * 恢复已禁用的内置插件（重新启用后调用）
 */
export function reloadPlugin(pluginName: string): void {
  disabledBuiltins.delete(pluginName);
}

/**
 * 获取所有内置插件名称（供 composable 在 dev 模式下直接加载）
 */
export function getBuiltinPluginNames(): string[] {
  return [...builtinLoaders.keys()];
}
