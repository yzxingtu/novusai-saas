/**
 * Tabbar sessionStorage self-healing utility
 * Tabbar sessionStorage 自愈工具
 *
 * Goals:
 * 1) Clean up legacy error keys (e.g., core-tabbar)
 * 2) Limit persisted tabs count to prevent state bloat from long-running tabs
 * 3) Deduplicate tabs caused by query differences (default dedup by path)
 * 目标：
 * 1) 清理历史错误 key（如 core-tabbar）
 * 2) 限制持久化 tabs 数量，避免单标签页长期运行后状态膨胀
 * 3) 收敛 query 导致的重复 tab（默认按 path 去重）
 */

const LEGACY_TABBAR_KEY = 'core-tabbar';
const TABBAR_KEY_SUFFIX = '-core-tabbar';

const DEFAULT_MAX_PERSISTED_TABS = 30;
const MAX_PAYLOAD_BYTES = 512 * 1024;

interface PersistedTabMeta {
  affixTab?: boolean;
  fullPathKey?: boolean;
}

interface PersistedTab {
  fullPath?: string;
  key?: string;
  meta?: PersistedTabMeta;
  path?: string;
  query?: Record<string, unknown>;
}

interface PersistedTabbarState {
  tabs?: PersistedTab[];
}

function isTabbarStorageKey(key: string, namespace?: string): boolean {
  if (key === LEGACY_TABBAR_KEY) return true;
  if (namespace && key === `${namespace}-core-tabbar`) return true;
  return key.endsWith(TABBAR_KEY_SUFFIX);
}

function getTabbarStorageKeys(namespace?: string): string[] {
  const keys: string[] = [];
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (!key) continue;
    if (isTabbarStorageKey(key, namespace)) {
      keys.push(key);
    }
  }
  return keys;
}

function normalizeTabKey(tab: PersistedTab): string {
  const fullPathKey = tab.meta?.fullPathKey === true;
  const pageKeyRaw = tab.query?.pageKey;
  let pageKey: string | undefined;
  if (typeof pageKeyRaw === 'string') {
    pageKey = pageKeyRaw;
  } else if (Array.isArray(pageKeyRaw) && typeof pageKeyRaw[0] === 'string') {
    pageKey = pageKeyRaw[0];
  }

  if (typeof pageKey === 'string' && pageKey.length > 0) {
    return pageKey;
  }

  if (
    fullPathKey &&
    typeof tab.fullPath === 'string' &&
    tab.fullPath.length > 0
  ) {
    return tab.fullPath;
  }
  if (typeof tab.path === 'string' && tab.path.length > 0) {
    return tab.path;
  }
  if (typeof tab.key === 'string' && tab.key.length > 0) {
    return tab.key;
  }
  return '';
}

function sanitizeTabs(
  tabs: PersistedTab[],
  maxTabs: number = DEFAULT_MAX_PERSISTED_TABS,
): PersistedTab[] {
  const dedupedReversed: PersistedTab[] = [];
  const seen = new Set<string>();

  for (let i = tabs.length - 1; i >= 0; i--) {
    const tab = tabs[i];
    if (!tab || typeof tab !== 'object') continue;
    const key = normalizeTabKey(tab);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    dedupedReversed.push(tab);
  }

  dedupedReversed.reverse();

  const affixTabs = dedupedReversed.filter((tab) => tab.meta?.affixTab);
  const normalTabs = dedupedReversed.filter((tab) => !tab.meta?.affixTab);

  const keepNormalCount = Math.max(maxTabs - affixTabs.length, 0);
  const keptNormalTabs = normalTabs.slice(-keepNormalCount);

  return [...affixTabs, ...keptNormalTabs];
}

/**
 * Clear all tabbar persisted caches under the current tab
 * 清理当前标签页下所有 tabbar 持久化缓存
 */
export function clearPersistedTabbarStorage(namespace?: string): void {
  const keys = getTabbarStorageKeys(namespace);
  for (const key of keys) {
    sessionStorage.removeItem(key);
  }
}

/**
 * Execute at startup: fix abnormally bloated/duplicate tab persisted data
 * 启动阶段执行：修复异常膨胀/重复 tab 的持久化数据
 */
export function sanitizePersistedTabbarStorage(namespace?: string): void {
  const keys = getTabbarStorageKeys(namespace);
  const currentKey = namespace ? `${namespace}-core-tabbar` : '';
  for (const key of keys) {
    // 清理历史版本遗留 key，避免 sessionStorage 在同标签页内长期膨胀
    if (namespace && key !== currentKey) {
      sessionStorage.removeItem(key);
      continue;
    }

    const raw = sessionStorage.getItem(key);
    if (!raw) {
      sessionStorage.removeItem(key);
      continue;
    }

    if (raw.length > MAX_PAYLOAD_BYTES) {
      sessionStorage.removeItem(key);
      continue;
    }

    try {
      const parsed = JSON.parse(raw) as PersistedTab[] | PersistedTabbarState;
      let tabs: PersistedTab[] = [];
      if (Array.isArray(parsed)) {
        tabs = parsed;
      } else if (Array.isArray(parsed.tabs)) {
        tabs = parsed.tabs;
      }
      const sanitizedTabs = sanitizeTabs(tabs);

      if (sanitizedTabs.length === tabs.length) {
        continue;
      }

      if (Array.isArray(parsed)) {
        sessionStorage.setItem(key, JSON.stringify(sanitizedTabs));
      } else {
        sessionStorage.setItem(key, JSON.stringify({ tabs: sanitizedTabs }));
      }
    } catch {
      sessionStorage.removeItem(key);
    }
  }
}
