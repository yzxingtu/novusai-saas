import type { RouteMeta } from 'vue-router';

export type RouteTitleLocaleMap = Record<string, string>;
export interface ResolveRouteMetaTitleOptions {
  hasLocaleKey?: (key: string) => boolean;
  locale?: string;
  translate?: (key: string) => string;
}

export function normalizeRouteTitleLocaleMap(
  value: unknown,
): RouteTitleLocaleMap | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return undefined;
  }

  const normalizedEntries = Object.entries(value).filter(
    ([key, item]): item is string =>
      typeof key === 'string' &&
      key.trim().length > 0 &&
      typeof item === 'string' &&
      item.trim().length > 0,
  );
  if (normalizedEntries.length === 0) {
    return undefined;
  }

  return Object.fromEntries(normalizedEntries);
}

export function resolveRouteTitleLocaleMap(
  titleLocaleMap?: RouteTitleLocaleMap,
  locale?: string,
): string | undefined {
  if (!titleLocaleMap) {
    return undefined;
  }

  const resolvedLocale = (locale ?? '').toLowerCase();
  const normalized = resolvedLocale.replaceAll('_', '-');

  const exact =
    titleLocaleMap[locale ?? ''] ??
    titleLocaleMap[normalized] ??
    titleLocaleMap[normalized.replaceAll('-', '_')];
  if (exact) {
    return exact;
  }

  if (normalized.startsWith('zh')) {
    return (
      titleLocaleMap['zh-CN'] ??
      titleLocaleMap.zh ??
      titleLocaleMap.zh_CN ??
      titleLocaleMap.en ??
      Object.values(titleLocaleMap)[0]
    );
  }

  if (normalized.startsWith('en')) {
    return (
      titleLocaleMap.en ??
      titleLocaleMap['en-US'] ??
      titleLocaleMap.en_US ??
      titleLocaleMap['zh-CN'] ??
      Object.values(titleLocaleMap)[0]
    );
  }

  return (
    titleLocaleMap['zh-CN'] ??
    titleLocaleMap.en ??
    Object.values(titleLocaleMap)[0]
  );
}

export function resolveRouteMetaTitle(
  meta?: Partial<RouteMeta>,
  options: ResolveRouteMetaTitleOptions = {},
): string {
  const localizedTitle = resolveRouteTitleLocaleMap(
    normalizeRouteTitleLocaleMap(meta?.titleLocaleMap),
    options.locale,
  );
  if (localizedTitle) {
    return localizedTitle;
  }

  const rawTitle = typeof meta?.title === 'string' ? meta.title : '';
  if (
    rawTitle.includes('.') &&
    typeof options.hasLocaleKey === 'function' &&
    typeof options.translate === 'function' &&
    options.hasLocaleKey(rawTitle)
  ) {
    return options.translate(rawTitle);
  }
  return rawTitle;
}
