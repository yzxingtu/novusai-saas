import { useAppConfig } from '@vben/hooks';

const LOOPBACK_HOSTNAMES = new Set(['0.0.0.0', '127.0.0.1', 'localhost']);

function normalizeApiUrl(url: null | string | undefined): string {
  return (typeof url === 'string' ? url : '').trim().replace(/\/+$/, '');
}

function normalizeHostname(hostname: string): string {
  return hostname.trim().replace(/^\[|\]$/g, '').toLowerCase();
}

function isLoopbackHostname(hostname: string): boolean {
  const normalized = normalizeHostname(hostname);
  return normalized === '::1' || LOOPBACK_HOSTNAMES.has(normalized);
}

export function resolveApiUrl(
  rawApiUrl: null | string | undefined,
  options: {
    currentHostname?: string;
    isProduction?: boolean;
  } = {},
): string {
  const normalizedRawApiUrl = normalizeApiUrl(rawApiUrl);
  if (!normalizedRawApiUrl || options.isProduction) {
    return normalizedRawApiUrl;
  }

  try {
    const parsed = new URL(normalizedRawApiUrl);
    if (!/^https?:$/.test(parsed.protocol)) {
      return normalizedRawApiUrl;
    }

    if (!isLoopbackHostname(parsed.hostname)) {
      return normalizedRawApiUrl;
    }

    const currentHostname = options.currentHostname?.trim();
    if (!currentHostname || isLoopbackHostname(currentHostname)) {
      return normalizedRawApiUrl;
    }

    parsed.hostname = currentHostname;
    return parsed.toString().replace(/\/+$/, '');
  } catch {
    return normalizedRawApiUrl;
  }
}

export function getAppApiUrl(): string {
  const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
  const currentHostname =
    typeof window === 'undefined' ? undefined : window.location.hostname;

  return resolveApiUrl(apiURL, {
    currentHostname,
    isProduction: import.meta.env.PROD,
  });
}
