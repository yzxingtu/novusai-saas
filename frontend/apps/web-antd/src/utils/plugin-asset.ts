import type { ApiEndpoint } from '#/api';

import { getCurrentEndpoint } from '#/router/access';
import { TokenStorage } from '#/store/shared/token-storage';
import { ensureTraceIdHeader } from '#/utils/request/trace';

const PLUGIN_ASSET_AUTH_COOKIE = 'novus_plugin_asset_token';
const PLUGIN_ASSET_PREFIX = '/plugin-assets/';
const PLUGIN_PUBLIC_ASSET_PREFIX = '/plugin-public-assets/';
const PLUGIN_ICON_PREFIX = '/plugin-icons/';
type PublicPluginAssetEndpoint = 'admin' | 'tenant' | 'user';

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

function normalizePluginAssetPath(
  pluginName: string,
  assetPath: string,
  publicEndpoint?: PublicPluginAssetEndpoint,
): string {
  const raw = (assetPath || '').trim();
  if (!raw) {
    if (publicEndpoint) {
      return `${PLUGIN_PUBLIC_ASSET_PREFIX}${publicEndpoint}/${pluginName}/`;
    }
    return `/plugin-assets/${pluginName}/`;
  }
  if (isExternalAssetUrl(raw)) {
    return raw;
  }
  if (raw.startsWith(PLUGIN_PUBLIC_ASSET_PREFIX)) {
    return raw;
  }
  if (raw.startsWith('/plugin-assets/')) {
    return raw;
  }
  if (raw.startsWith('/')) {
    return raw;
  }
  if (publicEndpoint) {
    return `${PLUGIN_PUBLIC_ASSET_PREFIX}${publicEndpoint}/${pluginName}/${raw.replace(/^\/+/, '')}`;
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
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  if (!token) {
    document.cookie = `${PLUGIN_ASSET_AUTH_COOKIE}=; Max-Age=0; Path=/; SameSite=Lax${secure}`;
    return;
  }

  document.cookie = `${PLUGIN_ASSET_AUTH_COOKIE}=${encodeURIComponent(token)}; Path=/; SameSite=Lax${secure}`;
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
  options: ApiEndpoint | { endpoint?: ApiEndpoint; publicEndpoint?: PublicPluginAssetEndpoint } = getCurrentEndpoint(),
): HeadersInit {
  const normalizedOptions =
    typeof options === 'string' ? { endpoint: options } : options;
  if (normalizedOptions.publicEndpoint) {
    return {};
  }

  const endpoint = normalizedOptions.endpoint ?? getCurrentEndpoint();
  syncPluginAssetAuthCookie(endpoint);
  const token = TokenStorage.getToken(endpoint);
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  ensureTraceIdHeader(headers);
  return headers;
}

export function buildPluginAssetUrl(
  pluginName: string,
  assetPath: string,
  options: BuildPluginAssetUrlOptions = {},
): string {
  const normalized = normalizePluginAssetPath(
    pluginName,
    assetPath,
    options.publicEndpoint,
  );
  if (isExternalAssetUrl(normalized)) {
    return normalized;
  }

  if (options.publicEndpoint) {
    return appendQueryParams(normalized, options);
  }

  const endpoint = options.endpoint ?? getCurrentEndpoint();
  syncPluginAssetAuthCookie(endpoint);
  return appendQueryParams(normalized, options);
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
