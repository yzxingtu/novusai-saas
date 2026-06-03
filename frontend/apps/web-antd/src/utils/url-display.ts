import { $t } from '#/locales';

const HTTP_PROTOCOL_RE = /^https?:$/i;

function tryParseHttpUrl(value: string): null | URL {
  try {
    const parsed = new URL(value);
    return HTTP_PROTOCOL_RE.test(parsed.protocol) ? parsed : null;
  } catch {
    return null;
  }
}

function decodePathSegment(segment: string) {
  if (!segment) {
    return '';
  }
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

function normalizeReadableSegment(segment: string) {
  const decoded = decodePathSegment(segment)
    .replace(/\.[a-z0-9]{2,8}$/iu, '')
    .replaceAll(/[-_]+/g, ' ')
    .replaceAll(/\s+/g, ' ')
    .trim();
  return decoded;
}

function buildReadablePathLabel(parsed: URL) {
  const segments = parsed.pathname
    .split('/')
    .map((segment) => normalizeReadableSegment(segment))
    .filter(Boolean);
  if (segments.length === 0) {
    return '';
  }

  const candidateSegments = segments.slice(-2);
  const label = candidateSegments.join(' / ').trim();
  if (!label) {
    return '';
  }
  return label.length > 48 ? `${label.slice(0, 47)}…` : label;
}

export function isHttpUrl(value: unknown): value is string {
  return typeof value === 'string' && Boolean(tryParseHttpUrl(value.trim()));
}

export function normalizeHttpUrlForDedup(value: string) {
  const parsed = tryParseHttpUrl(value.trim());
  if (!parsed) {
    return value.trim();
  }

  parsed.hash = '';
  parsed.hostname = parsed.hostname.toLowerCase();
  if (
    (parsed.protocol === 'https:' && parsed.port === '443') ||
    (parsed.protocol === 'http:' && parsed.port === '80')
  ) {
    parsed.port = '';
  }

  const normalizedPathname = parsed.pathname.replace(/\/+$/u, '') || '/';
  parsed.pathname = normalizedPathname;
  parsed.searchParams.sort();

  const pathname = parsed.pathname === '/' ? '' : parsed.pathname;
  const search = parsed.search || '';
  return `${parsed.protocol}//${parsed.host}${pathname}${search}`;
}

export function getUrlHostLabel(value: string) {
  const parsed = tryParseHttpUrl(value.trim());
  if (!parsed) {
    return '';
  }
  return parsed.hostname.replace(/^www\./iu, '');
}

export function getUrlDisplayLabel(value: string, explicitLabel?: string) {
  const normalizedLabel =
    typeof explicitLabel === 'string' ? explicitLabel.trim() : '';
  const normalizedValue = value.trim();
  if (normalizedLabel) {
    const explicitIsUrl = isHttpUrl(normalizedLabel);
    if (!explicitIsUrl) {
      return normalizedLabel;
    }
    if (!normalizedValue) {
      return normalizedLabel;
    }
    const explicitKey = normalizeHttpUrlForDedup(normalizedLabel);
    const valueKey = normalizeHttpUrlForDedup(normalizedValue);
    if (explicitKey !== valueKey) {
      return normalizedLabel;
    }
  }

  const parsed = tryParseHttpUrl(normalizedValue);
  if (!parsed) {
    return $t('common.globalAiChat.referenceLinkFallback');
  }

  const hostLabel = getUrlHostLabel(value);
  const readablePath = buildReadablePathLabel(parsed);
  if (hostLabel && readablePath) {
    return `${hostLabel} / ${readablePath}`;
  }
  if (hostLabel) {
    return hostLabel;
  }
  return $t('common.globalAiChat.referenceLinkFallback');
}

export function isDefaultUrlDisplayLabel(label: string, value: string) {
  const normalizedLabel = label.trim();
  if (!normalizedLabel) {
    return true;
  }
  return (
    normalizedLabel === getUrlDisplayLabel(value) ||
    normalizedLabel === getUrlHostLabel(value) ||
    normalizedLabel === $t('common.globalAiChat.referenceLinkFallback')
  );
}
