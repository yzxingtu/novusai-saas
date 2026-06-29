import type { ApiEndpoint } from '#/api';

type PluginHostEndpoint = Extract<ApiEndpoint, 'admin' | 'tenant'>;

const SAFE_PLUGIN_NAME_RE = /^[a-z][\da-z]*(?:-[\da-z]+)*$/;

let activePluginHostEndpoint: null | PluginHostEndpoint = null;

function normalizePluginHostEndpoint(
  endpoint: null | string | undefined,
): null | PluginHostEndpoint {
  if (endpoint === 'admin' || endpoint === 'tenant') {
    return endpoint;
  }
  return null;
}

function resolveEndpointFromPath(
  path: null | string | undefined,
): null | PluginHostEndpoint {
  const normalizedPath = String(path || '').trim();
  if (normalizedPath.startsWith('/admin')) {
    return 'admin';
  }
  if (normalizedPath.startsWith('/tenant')) {
    return 'tenant';
  }
  return null;
}

function getBrowserPathname(): string {
  return typeof window === 'undefined' ? '' : window.location.pathname;
}

export function setActivePluginHostEndpoint(
  endpoint: ApiEndpoint | null | undefined,
): void {
  activePluginHostEndpoint = normalizePluginHostEndpoint(endpoint);
}

export function getActivePluginHostEndpoint(): null | PluginHostEndpoint {
  return activePluginHostEndpoint;
}

export function getPluginHostEndpoint(
  fallbackPath: null | string | undefined = getBrowserPathname(),
): null | PluginHostEndpoint {
  return activePluginHostEndpoint ?? resolveEndpointFromPath(fallbackPath);
}

export function buildPluginApiBase(
  pluginName: string,
  fallbackPath?: null | string,
): string {
  const normalizedPluginName = pluginName.trim();
  if (!SAFE_PLUGIN_NAME_RE.test(normalizedPluginName)) {
    throw new Error(`Invalid plugin name '${pluginName}'`);
  }

  const endpoint = getPluginHostEndpoint(fallbackPath);
  if (!endpoint) {
    throw new Error(
      `Cannot resolve host endpoint for plugin '${normalizedPluginName}'`,
    );
  }

  return `/${endpoint}/plugins/${normalizedPluginName}/api`;
}
