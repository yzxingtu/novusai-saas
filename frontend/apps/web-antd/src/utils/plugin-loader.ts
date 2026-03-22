/**
 * Plugin frontend dynamic loader utility
 * 插件前端动态加载工具
 *
 * Runtime loading strategy:
 *   - Dev → import Vite-transformed source entry from /__plugin_dev__/{plugin}/entry
 *   - Prod → fetch release manifest first, then inject release JS/CSS assets
 * 运行时加载策略：
 *   - 开发态 → 从 /__plugin_dev__/{plugin}/entry 导入 Vite 转译后的源码入口
 *   - 生产态 → 先读取 release manifest，再注入发布 JS/CSS 产物
 *
 * Design constraints:
 *   - Do not compile backend/plugins source into host frontend bundle
 *   - Plugins must maintain independent build and release
 * 设计约束：
 *   - 不将 backend/plugins 源码编译进宿主前端 bundle
 *   - 插件必须保持独立构建与独立发布
 */

import {
  buildPluginAssetUrl,
  getPluginAssetAuthHeaders,
} from '#/utils/plugin-asset';

type PluginModule = Record<string, unknown>;

export interface PluginFrontendRuntimeContract {
  dev_entry?: string;
  release_manifest?: string;
}

export interface PluginAssetLoadOptions {
  publicEndpoint?: 'admin' | 'tenant' | 'user';
}

export interface PluginReleaseManifest {
  assets: string[];
  css: string[];
  entry: string;
  format: string;
  global_var: string;
}

/** Loaded plugin cache / 已加载的插件缓存 */
const loadedPlugins: Map<string, PluginModule> = new Map();
const loadedPluginGlobals: Map<string, string> = new Map();

/** Loading Promise cache (prevent duplicate loading) / 加载中的 Promise 缓存（防止重复加载） */
const loadingPromises: Map<string, Promise<PluginModule>> = new Map();
/** CSS loading Promise cache (prevent duplicate loading) / CSS 解析中的 Promise 缓存（防止重复加载） */
const cssLoadingPromises: Map<string, Promise<void>> = new Map();

/** Unloaded plugins (prevent race with in-flight loading) / 已卸载集合（防止与加载中 Promise 竞态） */
const unloadedPlugins: Set<string> = new Set();

const SAFE_PLUGIN_NAME_RE = /^[a-z][\da-z]*(?:-[\da-z]+)*$/;
const SAFE_ASSET_SEGMENT_RE = /^[\w.-]+$/;
const RELEASE_MANIFEST_FORMAT = 'novus.plugin.release.v1';

export const pluginRuntimeEnv = {
  isDev(): boolean {
    return Boolean(import.meta.env.DEV);
  },
};

function normalizeRelativeAssetPath(assetPath: string): null | string {
  const normalized = (assetPath || '')
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
        !SAFE_ASSET_SEGMENT_RE.test(segment),
    )
  ) {
    return null;
  }

  return segments.join('/');
}

/**
 * Convert plugin name to global variable name: crm-module → NovusPlugin_crm_module
 * 将插件名转为全局变量名: crm-module → NovusPlugin_crm_module
 */
function toGlobalVarName(pluginName: string): string {
  return `NovusPlugin_${pluginName.replaceAll('-', '_')}`;
}

function getReleaseManifestPath(
  runtimeContract?: PluginFrontendRuntimeContract,
): string {
  const manifestPath = runtimeContract?.release_manifest?.trim();
  if (!manifestPath) {
    return 'plugin.manifest.json';
  }

  const normalized = normalizeRelativeAssetPath(manifestPath);
  if (!normalized) {
    throw new Error(
      `Invalid plugin release manifest path: '${runtimeContract?.release_manifest}'`,
    );
  }
  return normalized;
}

function normalizeManifestAssetList(
  fieldName: 'assets' | 'css',
  value: unknown,
): string[] {
  if (value === undefined || value === null) {
    return [];
  }

  if (!Array.isArray(value)) {
    throw new Error(`Plugin release manifest field '${fieldName}' must be an array`);
  }

  const normalizedItems: string[] = [];
  for (const item of value) {
    if (typeof item !== 'string') {
      throw new Error(
        `Plugin release manifest field '${fieldName}' must only contain strings`,
      );
    }
    const normalized = normalizeRelativeAssetPath(item);
    if (!normalized) {
      throw new Error(
        `Plugin release manifest field '${fieldName}' contains invalid asset path '${item}'`,
      );
    }
    if (!normalizedItems.includes(normalized)) {
      normalizedItems.push(normalized);
    }
  }
  return normalizedItems;
}

export function parsePluginReleaseManifest(
  pluginName: string,
  payload: unknown,
): PluginReleaseManifest {
  if (!payload || typeof payload !== 'object') {
    throw new Error(`Plugin '${pluginName}' release manifest must be an object`);
  }

  const raw = payload as Record<string, unknown>;
  const entry = normalizeRelativeAssetPath(
    typeof raw.entry === 'string' ? raw.entry : '',
  );
  if (!entry) {
    throw new Error(`Plugin '${pluginName}' release manifest is missing a valid entry`);
  }

  const format =
    typeof raw.format === 'string' && raw.format.trim()
      ? raw.format.trim()
      : RELEASE_MANIFEST_FORMAT;
  if (format !== RELEASE_MANIFEST_FORMAT) {
    throw new Error(
      `Plugin '${pluginName}' release manifest format must be '${RELEASE_MANIFEST_FORMAT}'`,
    );
  }

  const globalVar =
    typeof raw.global_var === 'string' && raw.global_var.trim()
      ? raw.global_var.trim()
      : toGlobalVarName(pluginName);

  return {
    assets: normalizeManifestAssetList('assets', raw.assets),
    css: normalizeManifestAssetList('css', raw.css),
    entry,
    format,
    global_var: globalVar,
  };
}

export function buildPluginDevEntryUrl(
  pluginName: string,
  loadOptions: PluginAssetLoadOptions = {},
): string {
  return buildPluginAssetUrl(pluginName, `/__plugin_dev__/${pluginName}/entry`, {
    cacheBust: true,
    publicEndpoint: loadOptions.publicEndpoint,
  });
}

async function loadPluginReleaseManifest(
  pluginName: string,
  runtimeContract?: PluginFrontendRuntimeContract,
  loadOptions: PluginAssetLoadOptions = {},
): Promise<PluginReleaseManifest> {
  const manifestUrl = buildPluginAssetUrl(
    pluginName,
    getReleaseManifestPath(runtimeContract),
    {
      publicEndpoint: loadOptions.publicEndpoint,
    },
  );
  const response = await fetch(manifestUrl, {
    headers: getPluginAssetAuthHeaders({
      publicEndpoint: loadOptions.publicEndpoint,
    }),
  });

  if (!response.ok) {
    throw new Error(
      `Failed to load plugin release manifest '${manifestUrl}' (${response.status})`,
    );
  }

  return parsePluginReleaseManifest(
    pluginName,
    (await response.json()) as unknown,
  );
}

function _injectPluginCSS(
  pluginName: string,
  cssFileName: string,
  loadOptions: PluginAssetLoadOptions = {},
): void {
  const normalizedPath = normalizeRelativeAssetPath(cssFileName);
  if (!normalizedPath) {
    throw new Error(
      `Rejected invalid CSS asset path '${cssFileName}' for plugin '${pluginName}'`,
    );
  }

  const cssId = `novus-plugin-css-${pluginName}-${normalizedPath.replaceAll(/[^\w-]/g, '_')}`;
  if (document.getElementById(cssId)) {
    return;
  }

  const link = document.createElement('link');
  link.id = cssId;
  link.dataset.novusPlugin = pluginName;
  link.dataset.novusPluginRole = 'stylesheet';
  link.rel = 'stylesheet';
  link.href = buildPluginAssetUrl(pluginName, normalizedPath, {
    publicEndpoint: loadOptions.publicEndpoint,
  });
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
  loadOptions: PluginAssetLoadOptions = {},
): Promise<void> {
  if (cssFiles.length === 0) {
    return;
  }

  const pending = cssLoadingPromises.get(pluginName);
  if (pending) {
    return pending;
  }

  const task = (async () => {
    const uniqueCss = normalizeManifestAssetList('css', cssFiles);
    for (const cssFile of uniqueCss) {
      _injectPluginCSS(pluginName, cssFile, loadOptions);
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
  runtimeContract?: PluginFrontendRuntimeContract,
  loadOptions: PluginAssetLoadOptions = {},
): Promise<PluginModule> {
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

  const promise = (async (): Promise<PluginModule> => {
    let mod: PluginModule;

    if (pluginRuntimeEnv.isDev()) {
      mod = (await import(
        /* @vite-ignore */
        buildPluginDevEntryUrl(pluginName, loadOptions)
      )) as PluginModule;
    } else {
      const releaseManifest = await loadPluginReleaseManifest(
        pluginName,
        runtimeContract,
        loadOptions,
      );
      await loadPluginCSS(pluginName, releaseManifest.css, loadOptions);

      mod = await new Promise<PluginModule>((resolve, reject) => {
        const scriptUrl = buildPluginAssetUrl(
          pluginName,
          releaseManifest.entry,
          {
            publicEndpoint: loadOptions.publicEndpoint,
          },
        );
        const script = document.createElement('script');
        script.dataset.novusPlugin = pluginName;
        script.dataset.novusPluginRole = 'script';
        script.src = scriptUrl;
        script.async = true;

        script.addEventListener('load', () => {
          const globalVar = releaseManifest.global_var;
          const m = (window as unknown as Record<string, unknown>)[
            globalVar
          ] as PluginModule | undefined;

          if (m) {
            loadedPluginGlobals.set(pluginName, globalVar);
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
  const globalVar = loadedPluginGlobals.get(pluginName) ?? toGlobalVarName(pluginName);
  loadedPlugins.delete(pluginName);
  loadedPluginGlobals.delete(pluginName);
  loadingPromises.delete(pluginName);
  cssLoadingPromises.delete(pluginName);

  const scripts = document.querySelectorAll(
    `script[data-novus-plugin="${pluginName}"]`,
  );
  for (const s of scripts) {
    s.remove();
  }
  (window as unknown as Record<string, unknown>)[globalVar] = undefined;

  const cssNodes = document.querySelectorAll(
    `link[data-novus-plugin="${pluginName}"]`,
  );
  for (const cssNode of cssNodes) {
    cssNode.remove();
  }
}
