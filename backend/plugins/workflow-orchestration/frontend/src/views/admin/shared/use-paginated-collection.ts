import type { PaginatedResult } from '../../../types/admin';

import { ref } from 'vue';

interface CollectionLoadParams<TQuery extends Record<string, unknown>> {
  page: number;
  pageSize: number;
  query: TQuery;
}

interface UsePaginatedCollectionOptions<TItem, TQuery extends Record<string, unknown>> {
  initialPageSize?: number;
  initialQuery: TQuery;
  loader: (
    params: CollectionLoadParams<TQuery>,
  ) => Promise<PaginatedResult<TItem>>;
}

export function usePaginatedCollection<
  TItem,
  TQuery extends Record<string, unknown>,
>(options: UsePaginatedCollectionOptions<TItem, TQuery>) {
  const items = ref<TItem[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const page = ref(1);
  const pageSize = ref(options.initialPageSize ?? 10);
  const query = ref<TQuery>({ ...options.initialQuery } as TQuery);

  async function load(): Promise<void> {
    loading.value = true;
    try {
      const result = await options.loader({
        page: page.value,
        pageSize: pageSize.value,
        query: query.value,
      });
      items.value = result.items;
      total.value = result.total;
      page.value = result.page || page.value;
      pageSize.value = result.pageSize || pageSize.value;
    } finally {
      loading.value = false;
    }
  }

  async function reload(): Promise<void> {
    page.value = 1;
    await load();
  }

  async function patchQuery(patch: Partial<TQuery>): Promise<void> {
    query.value = { ...query.value, ...patch };
    await reload();
  }

  async function setPage(nextPage: number): Promise<void> {
    page.value = nextPage;
    await load();
  }

  async function setPageSize(nextPageSize: number): Promise<void> {
    pageSize.value = nextPageSize;
    page.value = 1;
    await load();
  }

  return {
    items,
    load,
    loading,
    page,
    pageSize,
    patchQuery,
    query,
    reload,
    setPage,
    setPageSize,
    total,
  };
}
