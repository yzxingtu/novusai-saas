import type { AiFieldOption } from './ai-operation-types';

import type { VbenFormSchema } from '#/core/adapter/form/setup';

/** Cache for resolved remote options / 远程选项缓存 */
const _remoteOptionsCache = new Map<string, AiFieldOption[]>();
const _remoteOptionsPending = new Map<string, Promise<AiFieldOption[]>>();
const REMOTE_OPTIONS_TIMEOUT_MS = 8000;

/**
 * Build a stable cache key from resource + field + api function
 * 从 resource + field + api 函数构建稳定的缓存 key
 */
function buildOptionsCacheKey(resource: string, fieldName: string): string {
  return `${resource}::${fieldName}`;
}

/**
 * Resolve remote options for all ApiSelect fields in a schema.
 * Returns a Map<fieldName, options[]>. Uses cache to avoid duplicate requests.
 * 解析 schema 中所有 ApiSelect 字段的远程选项。
 * 返回 Map<字段名, 选项列表>，使用缓存避免重复请求。
 */
export async function resolveRemoteOptions(
  schema: VbenFormSchema[],
  resource: string,
): Promise<Map<string, AiFieldOption[]>> {
  const result = new Map<string, AiFieldOption[]>();
  const tasks: Array<{
    fieldName: string;
    promise: Promise<AiFieldOption[]>;
  }> = [];

  for (const item of schema) {
    const fieldName = item.fieldName as string | undefined;
    const component = item.component as string;
    if (!fieldName) continue;
    if (
      component !== 'ApiSelect' &&
      component !== 'ApiTreeSelect' &&
      component !== 'IdentityRemoteSelect'
    ) {
      continue;
    }

    const props = item.componentProps as Record<string, unknown> | undefined;
    const apiFn = props?.api as ((...args: any[]) => Promise<any>) | undefined;
    if (!apiFn) continue;

    const cacheKey = buildOptionsCacheKey(resource, fieldName);

    // Return cached / 直接返回缓存
    const cachedOptions = _remoteOptionsCache.get(cacheKey);
    if (cachedOptions) {
      result.set(fieldName, cachedOptions);
      continue;
    }

    // Deduplicate in-flight requests / 去重进行中的请求 / 去重正在进行的请求
    const pendingOptionsPromise = _remoteOptionsPending.get(cacheKey);
    if (pendingOptionsPromise) {
      tasks.push({ fieldName, promise: pendingOptionsPromise });
      continue;
    }

    const apiParams = {
      ...(props?.params as Record<string, unknown>),
      'page[size]': 50,
    };
    const resultField = (props?.resultField as string) || 'items';

    const promise = apiFn(apiParams)
      .then((response: any) => {
        let items: any[] = [];
        if (Array.isArray(response)) {
          items = response;
        } else if (response && Array.isArray(response[resultField])) {
          items = response[resultField];
        } else if (response && Array.isArray(response.items)) {
          items = response.items;
        }
        const options: AiFieldOption[] = items.map((item: any) => ({
          label: String(item.label ?? item.name ?? item.title ?? item.id),
          value: item.value ?? item.id,
        }));
        _remoteOptionsCache.set(cacheKey, options);
        _remoteOptionsPending.delete(cacheKey);
        return options;
      })
      .catch(() => {
        _remoteOptionsPending.delete(cacheKey);
        return [] as AiFieldOption[];
      });

    _remoteOptionsPending.set(cacheKey, promise);
    tasks.push({ fieldName, promise });
  }

  // Wait for all in-flight / 等待所有进行中的请求
  const settled = await Promise.allSettled(tasks.map((t) => t.promise));
  for (const [i, task] of tasks.entries()) {
    const s = settled[i];
    if (!s) {
      continue;
    }
    if (s.status === 'fulfilled' && s.value.length > 0) {
      result.set(task.fieldName, s.value);
    }
  }

  return result;
}

export async function ensureRemoteOptionsWithTimeout(
  loader: () => Promise<void>,
): Promise<'ok' | 'timeout'> {
  let timerId: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      loader().then(() => 'ok' as const),
      new Promise<'timeout'>((resolve) => {
        timerId = setTimeout(
          () => resolve('timeout'),
          REMOTE_OPTIONS_TIMEOUT_MS,
        );
      }),
    ]);
  } finally {
    if (timerId !== undefined) {
      clearTimeout(timerId);
    }
  }
}

/**
 * Clear remote options cache for a resource (or all)
 * 清除某资源（或全部）的远程选项缓存
 */
export function clearRemoteOptionsCache(resource?: string): void {
  if (!resource) {
    _remoteOptionsCache.clear();
    return;
  }
  for (const key of _remoteOptionsCache.keys()) {
    if (key.startsWith(`${resource}::`)) {
      _remoteOptionsCache.delete(key);
    }
  }
}
