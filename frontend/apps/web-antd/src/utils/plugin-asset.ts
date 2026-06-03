import type { ApiEndpoint } from '#/api';

import { getCurrentEndpoint } from '#/router/access';
import { TokenStorage } from '#/store/shared/token-storage';
import { ensureTraceIdHeader } from '#/utils/request/trace';

const PLUGIN_ASSET_AUTH_COOKIE = 'novus_plugin_asset_token';
const PLUGIN_ASSET_PREFIX = '/plugin-assets/';
const PLUGIN_PUBLIC_ASSET_PREFIX = '/plugin-public-assets/';
const PLUGIN_ICON_PREFIX = '/plugin-icons/';
type PublicPluginAssetEndpoint = 'admin' | 'tenant' | 'user';
type PluginAssetScopeOptions = Pick<
  BuildPluginAssetUrlOptions,
  'endpoint' | 'publicEndpoint'
>;

type ParsedPluginAssetRoute =
  | {
      kind: 'auth';
      normalized: string;
      pluginName: string;
    }
  | {
      kind: 'public';
      normalized: string;
      pluginName: string;
      publicEndpoint: PublicPluginAssetEndpoint;
    };

export interface BuildPluginAssetUrlOptions {
  cacheBust?: boolean;
  endpoint?: ApiEndpoint;
  publicEndpoint?: PublicPluginAssetEndpoint;
  query?: Record<string, boolean | null | number | string | undefined>;
}

function isExternalAssetUrl(url: string): boolean {
  return (
    url.startsWith('data:') ||
    url.startsWith('blob:') ||
    /^https?:\/\//.test(url)
  );
}

function getPluginAssetBaseOrigin(): string {
  if (typeof window === 'undefined') {
    return 'http://localhost';
  }
  return window.location.origin || 'http://localhost';
}

function isPublicPluginAssetEndpoint(
  value: string,
): value is PublicPluginAssetEndpoint {
  return value === 'admin' || value === 'tenant' || value === 'user';
}

function normalizePluginAssetScopeOptions<T extends PluginAssetScopeOptions>(
  options: T,
): T {
  if (options.endpoint && options.publicEndpoint) {
    throw new Error(
      'Plugin asset scope must use either endpoint or publicEndpoint, not both',
    );
  }
  return options;
}

function parsePrefixedPluginAssetRoute(
  assetPath: string,
): null | ParsedPluginAssetRoute {
  const parsed = new URL(assetPath, getPluginAssetBaseOrigin());
  const normalized = `${parsed.pathname}${parsed.search}${parsed.hash}`;

  if (parsed.pathname.startsWith(PLUGIN_PUBLIC_ASSET_PREFIX)) {
    const [publicEndpoint, pluginName] = parsed.pathname
      .slice(PLUGIN_PUBLIC_ASSET_PREFIX.length)
      .split('/');
    if (!publicEndpoint || !pluginName) {
      throw new Error(`Invalid public plugin asset path '${assetPath}'`);
    }
    if (!isPublicPluginAssetEndpoint(publicEndpoint)) {
      throw new Error(
        `Invalid public plugin asset endpoint '${publicEndpoint}' in '${assetPath}'`,
      );
    }
    return {
      kind: 'public',
      normalized,
      pluginName,
      publicEndpoint,
    };
  }

  if (parsed.pathname.startsWith(PLUGIN_ASSET_PREFIX)) {
    const [pluginName] = parsed.pathname
      .slice(PLUGIN_ASSET_PREFIX.length)
      .split('/');
    if (!pluginName) {
      throw new Error(`Invalid plugin asset path '${assetPath}'`);
    }
    return {
      kind: 'auth',
      normalized,
      pluginName,
    };
  }

  return null;
}

function validatePrefixedPluginAssetRoute(
  pluginName: string,
  assetPath: string,
  route: ParsedPluginAssetRoute,
  options: PluginAssetScopeOptions,
): string {
  if (route.pluginName !== pluginName) {
    throw new Error(
      `Plugin asset path '${assetPath}' does not match plugin '${pluginName}'`,
    );
  }

  if (route.kind === 'public') {
    if (!options.publicEndpoint) {
      throw new Error(
        `Plugin asset path '${assetPath}' requires publicEndpoint='${route.publicEndpoint}'`,
      );
    }
    if (options.publicEndpoint !== route.publicEndpoint) {
      throw new Error(
        `Plugin asset path '${assetPath}' does not match publicEndpoint '${options.publicEndpoint}'`,
      );
    }
    return route.normalized;
  }

  if (options.publicEndpoint) {
    throw new Error(
      `Authenticated plugin asset path '${assetPath}' cannot be loaded with publicEndpoint '${options.publicEndpoint}'`,
    );
  }

  return route.normalized;
}

function normalizePluginAssetPath(
  pluginName: string,
  assetPath: string,
  options: PluginAssetScopeOptions,
): string {
  const raw = (assetPath || '').trim();
  if (!raw) {
    if (options.publicEndpoint) {
      return `${PLUGIN_PUBLIC_ASSET_PREFIX}${options.publicEndpoint}/${pluginName}/`;
    }
    return `/plugin-assets/${pluginName}/`;
  }
  if (isExternalAssetUrl(raw)) {
    return raw;
  }
  const prefixedRoute = parsePrefixedPluginAssetRoute(raw);
  if (prefixedRoute) {
    return validatePrefixedPluginAssetRoute(
      pluginName,
      raw,
      prefixedRoute,
      options,
    );
  }
  if (raw.startsWith('/')) {
    throw new Error(
      `Absolute plugin asset path '${assetPath}' must use /plugin-assets/... or /plugin-public-assets/...`,
    );
  }
  if (options.publicEndpoint) {
    return `${PLUGIN_PUBLIC_ASSET_PREFIX}${options.publicEndpoint}/${pluginName}/${raw.replace(/^\/+/, '')}`;
  }
  return `/plugin-assets/${pluginName}/${raw.replace(/^\/+/, '')}`;
}

function normalizePluginIconPath(pluginName: string, iconPath: string): string {
  const raw = (iconPath || '').trim();
  if (!raw) {
    return `/plugin-icons/${pluginName}/icon.png`;
  }
  if (isExternalAssetUrl(raw)) {
    return raw;
  }
  if (raw.startsWith(PLUGIN_ICON_PREFIX)) {
    return raw;
  }
  if (raw.startsWith(PLUGIN_ASSET_PREFIX)) {
    return raw.replace(PLUGIN_ASSET_PREFIX, PLUGIN_ICON_PREFIX);
  }
  if (raw.startsWith('/')) {
    return raw;
  }
  return `/plugin-icons/${pluginName}/${raw.replace(/^\/+/, '')}`;
}

function syncPluginAssetAuthCookie(endpoint: ApiEndpoint): void {
  if (typeof document === 'undefined') {
    return;
  }

  const token = TokenStorage.getToken(endpoint);
  if (!token) {
    clearPluginAssetAuthCookie();
    return;
  }

  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  // eslint-disable-next-line unicorn/no-document-cookie
  document.cookie = `${PLUGIN_ASSET_AUTH_COOKIE}=${encodeURIComponent(token)}; Path=/; SameSite=Lax${secure}`;
}

function getPluginAssetCookieDomainVariants(hostname: string): string[] {
  const normalizedHost = hostname.trim().toLowerCase();
  if (
    !normalizedHost ||
    normalizedHost === 'localhost' ||
    /^[\d.]+$/.test(normalizedHost)
  ) {
    return [];
  }

  const segments = normalizedHost.split('.').filter(Boolean);
  const variants = new Set<string>([normalizedHost]);
  for (let index = 1; index < segments.length - 1; index += 1) {
    variants.add(segments.slice(index).join('.'));
  }
  return [...variants];
}

function clearPluginAssetAuthCookie(): void {
  if (typeof document === 'undefined') {
    return;
  }

  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  const domains = getPluginAssetCookieDomainVariants(window.location.hostname);
  const paths = [
    '/',
    '/plugin-assets',
    '/plugin-icons',
    '/plugin-public-assets',
  ];

  for (const path of paths) {
    // eslint-disable-next-line unicorn/no-document-cookie
    document.cookie = `${PLUGIN_ASSET_AUTH_COOKIE}=; Max-Age=0; Path=${path}; SameSite=Lax${secure}`;
    for (const domain of domains) {
      // eslint-disable-next-line unicorn/no-document-cookie
      document.cookie = `${PLUGIN_ASSET_AUTH_COOKIE}=; Max-Age=0; Path=${path}; Domain=${domain}; SameSite=Lax${secure}`;
    }
  }
}

function appendQueryParams(
  normalized: string,
  options: BuildPluginAssetUrlOptions,
): string {
  const baseOrigin = window.location.origin || 'http://localhost';
  const url = new URL(normalized, baseOrigin);

  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value === null || value === undefined || value === '') {
      continue;
    }
    url.searchParams.set(key, String(value));
  }

  if (options.cacheBust) {
    url.searchParams.set('t', String(Date.now()));
  }

  return `${url.pathname}${url.search}${url.hash}`;
}

export function getPluginAssetAuthHeaders(
  options:
    | ApiEndpoint
    | {
        endpoint?: ApiEndpoint;
        publicEndpoint?: PublicPluginAssetEndpoint;
      } = getCurrentEndpoint(),
): HeadersInit {
  const normalizedOptions = normalizePluginAssetScopeOptions(
    typeof options === 'string' ? { endpoint: options } : options,
  );
  if (normalizedOptions.publicEndpoint) {
    clearPluginAssetAuthCookie();
    return {};
  }

  const endpoint = normalizedOptions.endpoint ?? getCurrentEndpoint();
  syncPluginAssetAuthCookie(endpoint);
  const token = TokenStorage.getToken(endpoint);
  const headers: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};
  ensureTraceIdHeader(headers);
  return headers;
}

export function buildPluginAssetUrl(
  pluginName: string,
  assetPath: string,
  options: BuildPluginAssetUrlOptions = {},
): string {
  const normalizedOptions = normalizePluginAssetScopeOptions(options);
  const normalized = normalizePluginAssetPath(
    pluginName,
    assetPath,
    normalizedOptions,
  );
  if (isExternalAssetUrl(normalized)) {
    return normalized;
  }

  if (normalizedOptions.publicEndpoint) {
    clearPluginAssetAuthCookie();
    return appendQueryParams(normalized, normalizedOptions);
  }

  const endpoint = normalizedOptions.endpoint ?? getCurrentEndpoint();
  syncPluginAssetAuthCookie(endpoint);
  return appendQueryParams(normalized, normalizedOptions);
}

export function buildPluginIconUrl(
  pluginName: string,
  iconPath: string,
  options: BuildPluginAssetUrlOptions = {},
): string {
  const normalized = normalizePluginIconPath(pluginName, iconPath);
  if (isExternalAssetUrl(normalized)) {
    return normalized;
  }

  const endpoint = options.endpoint ?? getCurrentEndpoint();
  syncPluginAssetAuthCookie(endpoint);
  return appendQueryParams(normalized, options);
}
