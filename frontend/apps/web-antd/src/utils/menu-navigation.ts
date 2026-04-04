import type { MenuRecordRaw, RouteMeta } from '@vben/types';

import { normalizePageKey } from '#/components/business/ai-slide-panel/page-key-utils';
import { getEndpointFromPath } from '#/utils/endpoint';

interface RouteMetaAI {
  capabilities?: string[];
  category?: string;
  description?: string;
  disabledCapabilities?: string[] | string;
  disabledOperations?: string[] | string;
  keywords?: string[];
  mode?: string;
  pageContextKey?: string;
}

interface MenuWithMeta extends MenuRecordRaw {
  children?: MenuWithMeta[];
  meta?: Record<string, unknown> | RouteMeta;
}

interface MenuSemanticMetadata {
  capabilities: string[];
  category?: string;
  description?: string;
  keywords: string[];
}

export interface MenuNavigationEntry {
  breadcrumb: string[];
  capabilities: string[];
  category?: string;
  description?: string;
  endpoint: string;
  icon?: MenuRecordRaw['icon'];
  key: string;
  keywords: string[];
  path: string;
  pageKey: string;
  title: string;
}

export interface MenuNavigationSearchResult extends MenuNavigationEntry {
  score: number;
}

export type MenuNavigationResolution =
  | {
      candidates: MenuNavigationEntry[];
      kind: 'ambiguous_match';
    }
  | {
      candidates?: MenuNavigationEntry[];
      kind: 'not_found';
    }
  | {
      entry: MenuNavigationEntry;
      kind: 'already_on_page';
    }
  | {
      entry: MenuNavigationEntry;
      kind: 'success';
    };

export interface NavigationContextData {
  breadcrumb: string[];
  endpoint: string;
  page_key: string;
  path: string;
}

export interface SerializedMenuNavigationEntry {
  breadcrumb: string[];
  capabilities?: string[];
  category?: string;
  description?: string;
  endpoint: string;
  keywords?: string[];
  page_key: string;
  path: string;
  title: string;
}

interface BuildMenuNavigationEntriesOptions {
  currentEndpoint?: string;
  menus: MenuRecordRaw[];
  translate?: (label: string) => string;
}

interface ResolveMenuNavigationTargetOptions {
  currentPath?: string;
  currentPageKey?: string;
  entries: MenuNavigationEntry[];
  target: string;
}

const MENU_QUERY_FILLER_RE =
  /(帮我|请帮我|请|麻烦|我想|想要|我要|能不能|可以帮我|给我|一下|一个|一条|一份|新增|添加|新建|创建|打开|进入|跳转|切到|前往|go to|navigate to|switch to|jump to|open|create|add|new)/g;

function normalizeSearchText(value: string): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replaceAll(/[\s/_-]+/g, ' ')
    .replaceAll(/[()[\]{}.,:;!?'"`~@#$%^&*+=|<>\\]+/g, ' ')
    .replaceAll(/\s+/g, ' ');
}

function compactSearchText(value: string): string {
  return normalizeSearchText(value).replaceAll(' ', '');
}

function buildLoosePattern(input: string): null | RegExp {
  const normalized = compactSearchText(input);
  if (!normalized) return null;
  const escaped = [...normalized]
    .map((char) => (/[\\^$.*+?()[\]{}|]/.test(char) ? `\\${char}` : char))
    .join('.*');
  return new RegExp(escaped);
}

function resolveDisplayTitle(
  menu: MenuWithMeta,
  translate?: (label: string) => string,
): string {
  const rawName = typeof menu.name === 'string' ? menu.name : '';
  const rawMetaTitle =
    typeof menu.meta === 'object' &&
    menu.meta !== null &&
    typeof (menu.meta as { title?: unknown }).title === 'string'
      ? ((menu.meta as { title?: string }).title ?? '')
      : '';

  const translatedName = rawName ? (translate?.(rawName) ?? rawName) : '';
  const translatedMetaTitle = rawMetaTitle
    ? (translate?.(rawMetaTitle) ?? rawMetaTitle)
    : '';

  return (
    translatedName ||
    translatedMetaTitle ||
    rawName ||
    rawMetaTitle ||
    menu.path
  );
}

function normalizeStringArray(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const value of values) {
    const text = String(value ?? '').trim();
    const normalizedText = normalizeSearchText(text);
    if (!text || !normalizedText || seen.has(normalizedText)) continue;
    normalized.push(text);
    seen.add(normalizedText);
  }
  return normalized;
}

function resolveMenuMetaAi(menu: MenuWithMeta): RouteMetaAI | undefined {
  if (typeof menu.meta !== 'object' || menu.meta === null) {
    return undefined;
  }
  const meta = menu.meta as { ai?: RouteMetaAI };
  if (!meta.ai || typeof meta.ai !== 'object') {
    return undefined;
  }
  return meta.ai;
}

function resolveMenuPageKey(menu: MenuWithMeta): string {
  const metaAi = resolveMenuMetaAi(menu);
  return normalizePageKey(metaAi?.pageContextKey ?? menu.path);
}

function resolveMenuSemanticMetadata(options: {
  menu: MenuWithMeta;
}): MenuSemanticMetadata {
  const metaAi = resolveMenuMetaAi(options.menu);

  return {
    description:
      typeof metaAi?.description === 'string' ? metaAi.description : undefined,
    keywords: normalizeStringArray(metaAi?.keywords),
    capabilities: normalizeStringArray(metaAi?.capabilities),
    category:
      typeof metaAi?.category === 'string' && metaAi.category.trim()
        ? metaAi.category
        : undefined,
  };
}

function stripMenuQueryFillers(value: string): string {
  return normalizeSearchText(value).replaceAll(MENU_QUERY_FILLER_RE, ' ').trim();
}

function buildSemanticQueryVariants(target: string): string[] {
  const variants = new Set<string>();
  const normalizedTarget = normalizeSearchText(target);
  const strippedTarget = stripMenuQueryFillers(target);

  const addVariant = (value: string) => {
    const normalized = normalizeSearchText(value);
    if (!normalized) return;
    variants.add(normalized);
  };

  addVariant(normalizedTarget);
  addVariant(strippedTarget);

  return [...variants];
}

function scoreMenuNavigationEntry(
  entry: MenuNavigationEntry,
  normalizedTarget: string,
  targetPattern: null | RegExp,
): number {
  if (!normalizedTarget) return 0;

  const targetVariants = buildSemanticQueryVariants(normalizedTarget);
  const path = normalizeSearchText(entry.path);
  const pageKey = normalizeSearchText(entry.pageKey);
  const title = normalizeSearchText(entry.title);
  const breadcrumb = normalizeSearchText(entry.breadcrumb.join(' / '));
  const description = normalizeSearchText(entry.description ?? '');
  const category = normalizeSearchText(entry.category ?? '');
  const keywords = entry.keywords.map((keyword) => normalizeSearchText(keyword));
  const capabilities = entry.capabilities.map((capability) =>
    normalizeSearchText(capability),
  );
  const endpointAdjustedPath = normalizeSearchText(
    entry.path.replace(/^\/(?:admin|tenant)\//, '/'),
  );
  const textualHaystacks = [
    title,
    breadcrumb,
    path,
    pageKey,
    endpointAdjustedPath,
    description,
    category,
    ...keywords,
    ...capabilities,
  ].filter(Boolean);
  const compactHaystacks = textualHaystacks.map((item) => compactSearchText(item));
  const compactTitle = compactSearchText(title);
  const compactBreadcrumb = compactSearchText(breadcrumb);
  const compactKeywords = keywords.map((keyword) => compactSearchText(keyword));
  const compactCapabilities = capabilities.map((capability) =>
    compactSearchText(capability),
  );

  let bestScore = 0;

  for (const variant of targetVariants) {
    const compactVariant = compactSearchText(variant);
    if (!compactVariant) continue;

    if (path === variant || endpointAdjustedPath === variant) {
      bestScore = Math.max(bestScore, 1000);
      continue;
    }
    if (pageKey === variant) {
      bestScore = Math.max(bestScore, 980);
      continue;
    }
    if (title === variant) {
      bestScore = Math.max(bestScore, 960);
      continue;
    }
    if (keywords.includes(variant)) {
      bestScore = Math.max(bestScore, 950);
      continue;
    }
    if (capabilities.includes(variant)) {
      bestScore = Math.max(bestScore, 930);
      continue;
    }
    if (breadcrumb === variant) {
      bestScore = Math.max(bestScore, 920);
      continue;
    }
    if (compactVariant === compactTitle) {
      bestScore = Math.max(bestScore, 910);
      continue;
    }
    if (compactKeywords.includes(compactVariant)) {
      bestScore = Math.max(bestScore, 900);
      continue;
    }
    if (compactCapabilities.includes(compactVariant)) {
      bestScore = Math.max(bestScore, 880);
      continue;
    }
    if (compactVariant === compactBreadcrumb) {
      bestScore = Math.max(bestScore, 870);
      continue;
    }

    if (title.includes(variant)) {
      bestScore = Math.max(bestScore, 890);
    }
    if (keywords.some((keyword) => keyword.includes(variant))) {
      bestScore = Math.max(bestScore, 880);
    }
    if (description.includes(variant)) {
      bestScore = Math.max(bestScore, 860);
    }
    if (capabilities.some((capability) => capability.includes(variant))) {
      bestScore = Math.max(bestScore, 840);
    }
    if (breadcrumb.includes(variant)) {
      bestScore = Math.max(bestScore, 830);
    }
    if (pageKey.includes(variant)) {
      bestScore = Math.max(bestScore, 810);
    }
    if (path.includes(variant) || endpointAdjustedPath.includes(variant)) {
      bestScore = Math.max(bestScore, 790);
    }
    if (category && category === variant) {
      bestScore = Math.max(bestScore, 770);
    }

    if (compactHaystacks.some((item) => item.includes(compactVariant))) {
      bestScore = Math.max(bestScore, 720);
    }

    const variantPattern = buildLoosePattern(variant);
    if (
      variantPattern &&
      compactHaystacks.some((item) => variantPattern.test(item))
    ) {
      bestScore = Math.max(bestScore, 640);
    }

    const targetTokens = variant.split(' ').filter(Boolean);
    if (
      targetTokens.length > 1 &&
      textualHaystacks.some((item) =>
        targetTokens.every((token) => item.includes(token)),
      )
    ) {
      bestScore = Math.max(bestScore, 600);
    }
  }

  if (
    bestScore < 640 &&
    targetPattern &&
    compactHaystacks.some((item) => targetPattern.test(item))
  ) {
    bestScore = 620;
  }

  return bestScore;
}

function sortNavigationResults(
  left: MenuNavigationSearchResult,
  right: MenuNavigationSearchResult,
): number {
  if (right.score !== left.score) {
    return right.score - left.score;
  }
  if (left.breadcrumb.length !== right.breadcrumb.length) {
    return left.breadcrumb.length - right.breadcrumb.length;
  }
  return left.title.localeCompare(right.title);
}

export function buildMenuNavigationEntries(
  options: BuildMenuNavigationEntriesOptions,
): MenuNavigationEntry[] {
  const currentEndpoint = options.currentEndpoint;
  const entries: MenuNavigationEntry[] = [];

  function walk(menus: MenuWithMeta[], parents: string[]) {
    for (const menu of menus) {
      if (!menu?.path) continue;
      const endpoint = getEndpointFromPath(menu.path);
      if (currentEndpoint && endpoint !== currentEndpoint) {
        continue;
      }

      const title = resolveDisplayTitle(menu, options.translate);
      const pageKey = resolveMenuPageKey(menu);
      const semanticMetadata = resolveMenuSemanticMetadata({
        menu,
      });
      const breadcrumb = [...parents, title];
      entries.push({
        breadcrumb,
        capabilities: semanticMetadata.capabilities,
        category: semanticMetadata.category,
        description: semanticMetadata.description,
        endpoint,
        icon: menu.icon,
        key: `${menu.path}::${pageKey}`,
        keywords: semanticMetadata.keywords,
        path: menu.path,
        pageKey,
        title,
      });

      if (Array.isArray(menu.children) && menu.children.length > 0) {
        walk(menu.children, breadcrumb);
      }
    }
  }

  walk(options.menus as MenuWithMeta[], []);
  return entries;
}

export function searchMenuNavigationEntries(
  entries: MenuNavigationEntry[],
  target: string,
): MenuNavigationSearchResult[] {
  const normalizedTarget = normalizeSearchText(target);
  if (!normalizedTarget) return [];
  const pattern = buildLoosePattern(target);

  return entries
    .map((entry) => ({
      ...entry,
      score: scoreMenuNavigationEntry(entry, normalizedTarget, pattern),
    }))
    .filter((entry) => entry.score > 0)
    .toSorted(sortNavigationResults);
}

export function resolveMenuNavigationTarget(
  options: ResolveMenuNavigationTargetOptions,
): MenuNavigationResolution {
  const results = searchMenuNavigationEntries(options.entries, options.target);
  if (results.length === 0) {
    return { kind: 'not_found' };
  }

  const [top, second] = results;
  if (!top) {
    return { kind: 'not_found' };
  }

  const currentPageKey = normalizePageKey(options.currentPageKey ?? '');
  const currentPath = normalizeSearchText(options.currentPath ?? '');
  if (currentPageKey && currentPageKey === normalizePageKey(top.pageKey)) {
    return { entry: top, kind: 'already_on_page' };
  }
  if (currentPath && currentPath === normalizeSearchText(top.path)) {
    return { entry: top, kind: 'already_on_page' };
  }

  if (
    second &&
    ((top.score >= 900 && second.score >= 900) ||
      (top.score >= 620 && second.score >= top.score - 60))
  ) {
    return {
      candidates: results.slice(0, 5),
      kind: 'ambiguous_match',
    };
  }

  return {
    entry: top,
    kind: 'success',
  };
}

export function serializeMenuNavigationEntry(
  entry: MenuNavigationEntry,
): SerializedMenuNavigationEntry {
  return {
    breadcrumb: entry.breadcrumb,
    ...(entry.capabilities.length > 0
      ? { capabilities: [...entry.capabilities] }
      : {}),
    ...(entry.category ? { category: entry.category } : {}),
    ...(entry.description ? { description: entry.description } : {}),
    endpoint: entry.endpoint,
    ...(entry.keywords.length > 0 ? { keywords: [...entry.keywords] } : {}),
    page_key: entry.pageKey,
    path: entry.path,
    title: entry.title,
  };
}

export function buildCompactMenuNavigationCatalog(
  entries: MenuNavigationEntry[],
  options: {
    maxCapabilitiesPerEntry?: number;
    maxEntries?: number;
    maxKeywordsPerEntry?: number;
  } = {},
): SerializedMenuNavigationEntry[] {
  const maxEntries = options.maxEntries ?? 48;
  const maxKeywordsPerEntry = options.maxKeywordsPerEntry ?? 6;
  const maxCapabilitiesPerEntry = options.maxCapabilitiesPerEntry ?? 4;

  return entries.slice(0, maxEntries).map((entry) => ({
    breadcrumb: entry.breadcrumb,
    ...(entry.capabilities.length > 0
      ? {
          capabilities: entry.capabilities.slice(0, maxCapabilitiesPerEntry),
        }
      : {}),
    ...(entry.category ? { category: entry.category } : {}),
    ...(entry.description ? { description: entry.description } : {}),
    endpoint: entry.endpoint,
    ...(entry.keywords.length > 0
      ? { keywords: entry.keywords.slice(0, maxKeywordsPerEntry) }
      : {}),
    page_key: entry.pageKey,
    path: entry.path,
    title: entry.title,
  }));
}

export function findMenuNavigationEntryByPath(
  entries: MenuNavigationEntry[],
  path: string,
): MenuNavigationEntry | undefined {
  const normalizedPath = normalizeSearchText(path);
  return entries.find(
    (entry) => normalizeSearchText(entry.path) === normalizedPath,
  );
}

export function buildNavigationContext(options: {
  activePath?: string;
  currentPageKey?: string;
  currentPath: string;
  entries: MenuNavigationEntry[];
}): NavigationContextData {
  const currentPageKey = normalizePageKey(
    options.currentPageKey ?? options.currentPath,
  );
  const activeEntry =
    findMenuNavigationEntryByPath(options.entries, options.currentPath) ??
    (options.activePath
      ? findMenuNavigationEntryByPath(options.entries, options.activePath)
      : undefined);

  return {
    breadcrumb: activeEntry?.breadcrumb ?? [],
    endpoint: getEndpointFromPath(options.currentPath),
    page_key: currentPageKey,
    path: options.currentPath,
  };
}
