import { ensureLucideIconCatalogRegistered, listIcons } from '@vben/icons';
import type { Recordable } from '@vben/types';

/**
 * Local icon cache, populated from registered collections only.
 * 本地图标缓存，仅来自已注册的本地图标集合。
 */
export const ICONS_MAP: Recordable<string[]> = {};

const PENDING_REQUESTS: Recordable<Promise<string[]>> = {};

/**
 * Load icons from local collections without any online Iconify request.
 * 从本地图标集合加载图标，禁止任何在线 Iconify 请求。
 */
export async function fetchIconsData(prefix: string): Promise<string[]> {
  const normalizedPrefix = prefix.trim();
  if (!normalizedPrefix) {
    return [];
  }

  if (Reflect.has(ICONS_MAP, normalizedPrefix) && ICONS_MAP[normalizedPrefix]) {
    return ICONS_MAP[normalizedPrefix];
  }
  if (
    Reflect.has(PENDING_REQUESTS, normalizedPrefix) &&
    PENDING_REQUESTS[normalizedPrefix]
  ) {
    return PENDING_REQUESTS[normalizedPrefix];
  }

  PENDING_REQUESTS[normalizedPrefix] = (async () => {
    try {
      if (normalizedPrefix === 'lucide') {
        ICONS_MAP[normalizedPrefix] = [
          ...(await ensureLucideIconCatalogRegistered()),
        ];
        return ICONS_MAP[normalizedPrefix];
      }

      ICONS_MAP[normalizedPrefix] = listIcons('', normalizedPrefix);
      return ICONS_MAP[normalizedPrefix];
    } catch (error) {
      console.error(
        `Failed to load local icons for prefix ${normalizedPrefix}:`,
        error,
      );
      return [];
    } finally {
      delete PENDING_REQUESTS[normalizedPrefix];
    }
  })();

  return PENDING_REQUESTS[normalizedPrefix];
}
