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

import type { ApiEndpoint } from '#/api';

import {
  buildPluginAssetUrl,
  getPluginAssetAuthHeaders,
} from '#/utils/plugin-asset';

type PluginModule = Record<string, unknown>;
type PluginCacheKey = string;
type PluginScopeKey = string;
type PluginPublicEndpoint = 'admin' | 'tenant' | 'user';

export interface PluginFrontendRuntimeContract {
  dev_entry?: string;
  release_manifest?: string;
}

export type PluginAssetLoadOptions =
  | {
      endpoint: ApiEndpoint;
      publicEndpoint?: never;
    }
  | {
      endpoint?: never;
      publicEndpoint: PluginPublicEndpoint;
    };

export interface PluginReleaseManifest {
  assets: string[];
  css: string[];
  entry: string;
  format: string;
  global_var: string;
}

/** Loaded plugin cache / 已加载的插件缓存 */
const loadedPlugins: Map<PluginCacheKey, PluginModule> = new Map();
const loadedPluginGlobals: Map<PluginCacheKey, string> = new Map();

/** Loading Promise cache (prevent duplicate loading) / 加载中的 Promise 缓存（防止重复加载） */
const loadingPromises: Map<PluginCacheKey, Promise<PluginModule>> = new Map();
/** CSS loading Promise cache (prevent duplicate loading) / CSS 解析中的 Promise 缓存（防止重复加载） */
const cssLoadingPromises: Map<PluginCacheKey, Promise<void>> = new Map();

/** Unloaded plugin cache keys (prevent race with in-flight loading) / 已卸载缓存键集合（防止与加载中 Promise 竞态） */
const unloadedPluginCacheKeys: Set<PluginCacheKey> = new Set();

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

function normalizePluginLoadOptions(
  loadOptions: PluginAssetLoadOptions,
): PluginAssetLoadOptions {
  if (loadOptions.publicEndpoint && loadOptions.endpoint) {
    throw new Error(
      'Plugin loader scope must use either endpoint or publicEndpoint, not both',
    );
  }
  if (loadOptions.publicEndpoint || loadOptions.endpoint) {
    return loadOptions;
  }
  throw new Error(
    'Plugin loader scope is required: pass endpoint for authenticated pages or publicEndpoint for public assets',
  );
}

function resolveEndpointScope(loadOptions: PluginAssetLoadOptions): string {
  const normalizedLoadOptions = normalizePluginLoadOptions(loadOptions);
  if (normalizedLoadOptions.publicEndpoint) {
    return `public:${normalizedLoadOptions.publicEndpoint}`;
  }
  return `auth:${normalizedLoadOptions.endpoint}`;
}

function toPluginScopeKey(
  pluginName: string,
  loadOptions: PluginAssetLoadOptions,
): PluginScopeKey {
  return `${pluginName}::${resolveEndpointScope(loadOptions)}`;
}

function getRuntimeContractSignature(
  runtimeContract?: PluginFrontendRuntimeContract,
): string {
  const devEntry = normalizeRelativeAssetPath(runtimeContract?.dev_entry || '');
  const releaseManifest = getReleaseManifestPath(runtimeContract);
  return `dev=${devEntry || '-'}|manifest=${releaseManifest}`;
}

function extractPluginScopeKey(cacheKey: PluginCacheKey): PluginScopeKey {
  const segments = cacheKey.split('::');
  if (segments.length < 2) {
    return cacheKey;
  }
  return `${segments[0]}::${segments[1]}`;
}

function extractRuntimeSignature(cacheKey: PluginCacheKey): string {
  const segments = cacheKey.split('::');
  if (segments.length <= 2) {
    return '';
  }
  return segments.slice(2).join('::');
}

function toPluginCacheKey(
  pluginName: string,
  runtimeContract: PluginFrontendRuntimeContract | undefined,
  loadOptions: PluginAssetLoadOptions,
): PluginCacheKey {
  return `${toPluginScopeKey(pluginName, loadOptions)}::${getRuntimeContractSignature(runtimeContract)}`;
}

export function getPluginRuntimeCacheKey(
  pluginName: string,
  runtimeContract: PluginFrontendRuntimeContract | undefined,
  loadOptions: PluginAssetLoadOptions,
): PluginCacheKey {
  return toPluginCacheKey(
    pluginName,
    runtimeContract,
    normalizePluginLoadOptions(loadOptions),
  );
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
    throw new TypeError(
      `Plugin release manifest field '${fieldName}' must be an array`,
    );
  }

  const normalizedItems: string[] = [];
  for (const item of value) {
    if (typeof item !== 'string') {
      throw new TypeError(
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
    throw new Error(
      `Plugin '${pluginName}' release manifest must be an object`,
    );
  }

  const raw = payload as Record<string, unknown>;
  const entry = normalizeRelativeAssetPath(
    typeof raw.entry === 'string' ? raw.entry : '',
  );
  if (!entry) {
    throw new Error(
      `Plugin '${pluginName}' release manifest is missing a valid entry`,
    );
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
  runtimeContract?: PluginFrontendRuntimeContract,
  _loadOptions?: PluginAssetLoadOptions,
): string {
  const url = new URL(
    `/__plugin_dev__/${pluginName}/entry`,
    window.location.origin,
  );
  const devEntry = normalizeRelativeAssetPath(runtimeContract?.dev_entry || '');
  if (devEntry) {
    url.searchParams.set('entry', devEntry);
  }
  url.searchParams.set('t', String(Date.now()));
  return `${url.pathname}${url.search}${url.hash}`;
}

async function loadPluginReleaseManifest(
  pluginName: string,
  runtimeContract: PluginFrontendRuntimeContract | undefined,
  loadOptions: PluginAssetLoadOptions,
): Promise<PluginReleaseManifest> {
  const normalizedLoadOptions = normalizePluginLoadOptions(loadOptions);
  const manifestUrl = buildPluginAssetUrl(
    pluginName,
    getReleaseManifestPath(runtimeContract),
    {
      endpoint: normalizedLoadOptions.endpoint,
      publicEndpoint: normalizedLoadOptions.publicEndpoint,
    },
  );
  const manifestHeaders = getPluginAssetAuthHeaders({
    endpoint: normalizedLoadOptions.endpoint,
    publicEndpoint: normalizedLoadOptions.publicEndpoint,
  });
  const response = await fetch(manifestUrl, {
    headers: manifestHeaders,
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

async function loadPluginReleaseModule(
  pluginName: string,
  runtimeContract: PluginFrontendRuntimeContract | undefined,
  loadOptions: PluginAssetLoadOptions,
): Promise<PluginModule> {
  const normalizedLoadOptions = normalizePluginLoadOptions(loadOptions);
  const cacheKey = toPluginCacheKey(
    pluginName,
    runtimeContract,
    normalizedLoadOptions,
  );
  const scopeKey = toPluginScopeKey(pluginName, normalizedLoadOptions);
  const releaseManifest = await loadPluginReleaseManifest(
    pluginName,
    runtimeContract,
    normalizedLoadOptions,
  );
  for (const [
    existingCacheKey,
    existingGlobalVar,
  ] of loadedPluginGlobals.entries()) {
    if (
      existingCacheKey !== cacheKey &&
      existingGlobalVar === releaseManifest.global_var &&
      extractRuntimeSignature(existingCacheKey) !==
        extractRuntimeSignature(cacheKey)
    ) {
      throw new Error(
        `Plugin global '${releaseManifest.global_var}' conflicts across runtime variants ('${existingCacheKey}' vs '${cacheKey}')`,
      );
    }
  }
  await loadPluginCSS(
    cacheKey,
    scopeKey,
    pluginName,
    releaseManifest.css,
    normalizedLoadOptions,
  );

  return await new Promise<PluginModule>((resolve, reject) => {
    const scriptUrl = buildPluginAssetUrl(pluginName, releaseManifest.entry, {
      endpoint: normalizedLoadOptions.endpoint,
      publicEndpoint: normalizedLoadOptions.publicEndpoint,
    });
    const script = document.createElement('script');
    script.dataset.novusPlugin = pluginName;
    script.dataset.novusPluginScope = scopeKey;
    script.dataset.novusPluginRole = 'script';
    script.src = scriptUrl;
    script.async = true;

    script.addEventListener('load', () => {
      const globalVar = releaseManifest.global_var;
      const m = (window as unknown as Record<string, unknown>)[globalVar] as
        | PluginModule
        | undefined;

      if (m) {
        loadedPluginGlobals.set(cacheKey, globalVar);
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

function _injectPluginCSS(
  cacheKey: PluginCacheKey,
  scopeKey: PluginScopeKey,
  pluginName: string,
  cssFileName: string,
  loadOptions: PluginAssetLoadOptions,
): void {
  const normalizedLoadOptions = normalizePluginLoadOptions(loadOptions);
  const normalizedPath = normalizeRelativeAssetPath(cssFileName);
  if (!normalizedPath) {
    throw new Error(
      `Rejected invalid CSS asset path '${cssFileName}' for plugin '${pluginName}'`,
    );
  }

  const cssId = `novus-plugin-css-${cacheKey.replaceAll(/[^\w-]/g, '_')}-${normalizedPath.replaceAll(/[^\w-]/g, '_')}`;
  if (document.querySelector(`#${cssId}`)) {
    return;
  }

  const link = document.createElement('link');
  link.id = cssId;
  link.dataset.novusPlugin = pluginName;
  link.dataset.novusPluginScope = scopeKey;
  link.dataset.novusPluginRole = 'stylesheet';
  link.rel = 'stylesheet';
  link.href = buildPluginAssetUrl(pluginName, normalizedPath, {
    endpoint: normalizedLoadOptions.endpoint,
    publicEndpoint: normalizedLoadOptions.publicEndpoint,
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
  cacheKey: PluginCacheKey,
  scopeKey: PluginScopeKey,
  pluginName: string,
  cssFiles: string[] = [],
  loadOptions: PluginAssetLoadOptions,
): Promise<void> {
  if (cssFiles.length === 0) {
    return;
  }

  const pending = cssLoadingPromises.get(cacheKey);
  if (pending) {
    return pending;
  }

  const task = (async () => {
    const uniqueCss = normalizeManifestAssetList('css', cssFiles);
    for (const cssFile of uniqueCss) {
      _injectPluginCSS(cacheKey, scopeKey, pluginName, cssFile, loadOptions);
    }
  })();

  cssLoadingPromises.set(cacheKey, task);
  try {
    await task;
  } finally {
    cssLoadingPromises.delete(cacheKey);
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
  runtimeContract: PluginFrontendRuntimeContract | undefined,
  loadOptions: PluginAssetLoadOptions,
): Promise<PluginModule> {
  if (!SAFE_PLUGIN_NAME_RE.test(pluginName)) {
    console.warn(
      `[PluginLoader] Rejected invalid plugin name: '${pluginName}'`,
    );
    return {};
  }

  const normalizedLoadOptions = normalizePluginLoadOptions(loadOptions);
  const cacheKey = toPluginCacheKey(
    pluginName,
    runtimeContract,
    normalizedLoadOptions,
  );

  // 已缓存 / Cache hit
  const cached = loadedPlugins.get(cacheKey);
  if (cached) return cached;

  // 正在加载中 / In-flight load
  const existing = loadingPromises.get(cacheKey);
  if (existing) return existing;

  const staleScopeCacheKeys = getPluginCacheKeys(
    pluginName,
    normalizedLoadOptions,
  ).filter((key) => key !== cacheKey);
  if (staleScopeCacheKeys.length > 0) {
    unloadPlugin(pluginName, normalizedLoadOptions);
  }

  unloadedPluginCacheKeys.delete(cacheKey);

  const promise = (async (): Promise<PluginModule> => {
    let mod: PluginModule;

    if (pluginRuntimeEnv.isDev()) {
      try {
        mod = (await import(
          /* @vite-ignore */
          buildPluginDevEntryUrl(
            pluginName,
            runtimeContract,
            normalizedLoadOptions,
          )
        )) as PluginModule;
      } catch (error) {
        console.warn(
          `[PluginLoader] Dev entry load failed for '${pluginName}', falling back to release bundle.`,
          error,
        );
        mod = await loadPluginReleaseModule(
          pluginName,
          runtimeContract,
          normalizedLoadOptions,
        );
      }
    } else {
      mod = await loadPluginReleaseModule(
        pluginName,
        runtimeContract,
        normalizedLoadOptions,
      );
    }

    // Race guard: skip caching if plugin was unloaded during async load
    // / 竞态保护：异步加载期间若插件已卸载则跳过缓存
    if (unloadedPluginCacheKeys.has(cacheKey)) {
      return mod;
    }

    if (typeof mod.setup === 'function') {
      try {
        (mod.setup as () => void)();
      } catch (error) {
        unloadPlugin(pluginName, normalizedLoadOptions);
        console.error(
          `[PluginLoader] setup() failed for '${pluginName}':`,
          error,
        );
        throw new Error(`Plugin '${pluginName}' setup() failed`, {
          cause: error,
        });
      }
    }

    if (unloadedPluginCacheKeys.has(cacheKey)) {
      return mod;
    }

    loadedPlugins.set(cacheKey, mod);
    return mod;
  })();

  loadingPromises.set(cacheKey, promise);
  try {
    return await promise;
  } finally {
    loadingPromises.delete(cacheKey);
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
  runtimeContract: PluginFrontendRuntimeContract | undefined,
  loadOptions: PluginAssetLoadOptions,
): Promise<null | unknown> {
  try {
    const mod = await loadPluginComponents(
      pluginName,
      runtimeContract,
      loadOptions,
    );
    return mod[componentName] ?? null;
  } catch {
    console.error(
      `Failed to get component '${componentName}' from plugin '${pluginName}'`,
    );
    return null;
  }
}

function getPluginScopePrefixes(
  pluginName: string,
  loadOptions?: PluginAssetLoadOptions,
): PluginScopeKey[] {
  if (loadOptions) {
    return [
      toPluginScopeKey(pluginName, normalizePluginLoadOptions(loadOptions)),
    ];
  }

  const prefix = `${pluginName}::`;
  const scopePrefixes = new Set<PluginScopeKey>();
  for (const key of [
    ...loadedPlugins.keys(),
    ...loadedPluginGlobals.keys(),
    ...loadingPromises.keys(),
    ...cssLoadingPromises.keys(),
  ]) {
    if (!key.startsWith(prefix)) {
      continue;
    }
    scopePrefixes.add(extractPluginScopeKey(key));
  }

  for (const node of document.querySelectorAll(
    `script[data-novus-plugin="${pluginName}"], link[data-novus-plugin="${pluginName}"]`,
  )) {
    const scopeKey = (node as HTMLElement).dataset.novusPluginScope;
    if (scopeKey?.startsWith(prefix)) {
      scopePrefixes.add(scopeKey);
    }
  }

  return [...scopePrefixes];
}

function getPluginCacheKeys(
  pluginName: string,
  loadOptions?: PluginAssetLoadOptions,
): PluginCacheKey[] {
  const scopePrefixes = getPluginScopePrefixes(pluginName, loadOptions);
  const prefixSet = new Set(scopePrefixes);

  return [
    ...new Set(
      [
        ...loadedPlugins.keys(),
        ...loadedPluginGlobals.keys(),
        ...loadingPromises.keys(),
        ...cssLoadingPromises.keys(),
      ].filter((key) =>
        prefixSet.size === 0
          ? key.startsWith(`${pluginName}::`)
          : prefixSet.has(extractPluginScopeKey(key)),
      ),
    ),
  ];
}

/**
 * Check if a plugin scope is loaded
 * 检查插件作用域是否已加载
 */
export function isPluginLoadedInScope(
  pluginName: string,
  loadOptions: PluginAssetLoadOptions,
): boolean {
  const [scopePrefix] = getPluginScopePrefixes(pluginName, loadOptions);
  if (!scopePrefix) {
    return false;
  }
  return [...loadedPlugins.keys()].some(
    (key) => extractPluginScopeKey(key) === scopePrefix,
  );
}

/**
 * Check if a plugin is loaded
 * 检查插件是否已加载
 */
export function isPluginLoaded(
  pluginName: string,
  loadOptions?: PluginAssetLoadOptions,
): boolean {
  if (loadOptions) {
    return isPluginLoadedInScope(pluginName, loadOptions);
  }
  return [...loadedPlugins.keys()].some((key) =>
    key.startsWith(`${pluginName}::`),
  );
}

/**
 * Unload plugin (clear cache + remove script tags)
 * 卸载插件（清除缓存 + 移除 script 标签）
 */
export function unloadPlugin(
  pluginName: string,
  loadOptions?: PluginAssetLoadOptions,
): void {
  const scopePrefixes = getPluginScopePrefixes(pluginName, loadOptions);
  const scopePrefixSet = new Set(scopePrefixes);
  const cacheKeys = getPluginCacheKeys(pluginName, loadOptions);
  for (const cacheKey of cacheKeys) {
    unloadedPluginCacheKeys.add(cacheKey);
  }

  for (const key of loadedPlugins.keys()) {
    if (
      scopePrefixSet.size === 0
        ? key.startsWith(`${pluginName}::`)
        : scopePrefixSet.has(extractPluginScopeKey(key))
    ) {
      loadedPlugins.delete(key);
    }
  }
  for (const key of loadingPromises.keys()) {
    if (
      scopePrefixSet.size === 0
        ? key.startsWith(`${pluginName}::`)
        : scopePrefixSet.has(extractPluginScopeKey(key))
    ) {
      loadingPromises.delete(key);
    }
  }
  for (const key of cssLoadingPromises.keys()) {
    if (
      scopePrefixSet.size === 0
        ? key.startsWith(`${pluginName}::`)
        : scopePrefixSet.has(extractPluginScopeKey(key))
    ) {
      cssLoadingPromises.delete(key);
    }
  }

  const globalVars = new Set<string>();
  for (const [key, value] of loadedPluginGlobals.entries()) {
    if (
      scopePrefixSet.size > 0
        ? !scopePrefixSet.has(extractPluginScopeKey(key))
        : !key.startsWith(`${pluginName}::`)
    ) {
      continue;
    }
    globalVars.add(value);
    loadedPluginGlobals.delete(key);
  }

  if (scopePrefixSet.size === 0) {
    const scripts = document.querySelectorAll(
      `script[data-novus-plugin="${pluginName}"]`,
    );
    for (const s of scripts) {
      s.remove();
    }

    const cssNodes = document.querySelectorAll(
      `link[data-novus-plugin="${pluginName}"]`,
    );
    for (const cssNode of cssNodes) {
      cssNode.remove();
    }
  } else {
    for (const scopeKey of scopePrefixSet) {
      const scripts = document.querySelectorAll(
        `script[data-novus-plugin="${pluginName}"][data-novus-plugin-scope="${scopeKey}"]`,
      );
      for (const scriptNode of scripts) {
        scriptNode.remove();
      }

      const cssNodes = document.querySelectorAll(
        `link[data-novus-plugin="${pluginName}"][data-novus-plugin-scope="${scopeKey}"]`,
      );
      for (const cssNode of cssNodes) {
        cssNode.remove();
      }
    }
  }

  const hasRemainingPluginScopes =
    [...loadedPlugins.keys(), ...loadedPluginGlobals.keys()].some((key) =>
      key.startsWith(`${pluginName}::`),
    ) ||
    document.querySelector(`script[data-novus-plugin="${pluginName}"]`) !==
      null ||
    document.querySelector(`link[data-novus-plugin="${pluginName}"]`) !== null;
  if (!hasRemainingPluginScopes) {
    if (globalVars.size === 0) {
      globalVars.add(toGlobalVarName(pluginName));
    }
    for (const globalVar of globalVars) {
      (window as unknown as Record<string, unknown>)[globalVar] = undefined;
    }
  }
}
