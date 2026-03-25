/**
 * 配置功能开关 Composable / Config features composable
 *
 * 集中获取 endpoints、batch、detail 等配置，供 WYSIWYG 预览渲染条件用
 */
import { computed } from 'vue';

import type { useCodegenBuilderStore } from '#/store';

export function useConfigFeatures(
  store: ReturnType<typeof useCodegenBuilderStore>,
) {
  const activeEndpointIdx = computed(() =>
    Math.max(0, store.activeEndpointIdx || 0),
  );
  const endpointList = computed(
    () => (store.configJson.endpoints as Record<string, unknown>[]) || [],
  );
  const ep0 = computed(
    () =>
      endpointList.value[activeEndpointIdx.value] ||
      endpointList.value[0] ||
      {},
  );
  const fe = computed(
    () => (ep0.value?.frontend as Record<string, unknown>) || {},
  );
  const batch = computed(
    () => (store.configJson.batch as Record<string, unknown>) || {},
  );
  const clone = computed(
    () =>
      (store.configJson as Record<string, unknown>).clone as
        | Record<string, unknown>
        | undefined,
  );
  const detail = computed(
    () =>
      (store.configJson as Record<string, unknown>).detail as
        | Record<string, unknown>
        | undefined,
  );
  const actions = computed(
    () =>
      ((store.configJson as Record<string, unknown>).actions as Record<
        string,
        unknown
      >[]) || [],
  );

  const displayName = computed(
    () =>
      (store.configJson.display_name as string) ||
      (store.configJson.resource as string) ||
      '',
  );

  const hasRecycleBin = computed(() => !!fe.value.recycle_bin);
  const hasExport = computed(() => !!fe.value.export);
  const hasImport = computed(() => !!fe.value.import);
  const hasBatchDelete = computed(() => !!batch.value?.delete);
  const hasDragSort = computed(() => !!fe.value.drag_sort);
  const hasClone = computed(() => !!clone.value?.enabled);
  const isCardMode = computed(() => fe.value.mode === 'card');
  const formColumns = computed(() => (fe.value.form_columns as number) ?? 1);

  const operationOptions = computed(() => {
    const opts = fe.value.operation_options;
    if (Array.isArray(opts) && opts.length) return opts;
    return ['edit', 'delete'];
  });

  const hasDetail = computed(
    () =>
      !!detail.value?.enabled ||
      (operationOptions.value as string[]).includes('detail'),
  );

  const model = computed(
    () =>
      (store.configJson as Record<string, unknown>).model as
        | Record<string, unknown>
        | undefined,
  );
  const tree = computed(
    () => model.value?.tree as Record<string, unknown> | undefined,
  );
  const hasTree = computed(() => !!tree.value?.enabled);

  const workflow = computed(
    () =>
      (store.configJson as Record<string, unknown>).workflow as
        | Record<string, unknown>
        | undefined,
  );
  const hasWorkflow = computed(
    () => !!(workflow.value?.transitions as unknown[])?.length,
  );

  const defaultSort = computed(
    () => (fe.value.default_sort as string) || '-created_at',
  );
  const pageSize = computed(() => (fe.value.page_size as number) || 20);
  const searchDefaultOpen = computed(() =>
    Boolean(fe.value.search_default_open),
  );
  const quickSearch = computed(() => {
    const value = fe.value.quick_search;
    return value === undefined ? true : value;
  });
  const softDelete = computed(() => !!model.value?.soft_delete);

  const customActions = computed(() => actions.value);

  const detailGroups = computed(
    () =>
      detail.value?.groups as
        | Array<{ title_zh?: string; title_en?: string; fields?: string[] }>[]
        | undefined,
  );

  const allFields = computed(
    () => (store.configJson.fields as Record<string, unknown>[]) || [],
  );

  const searchFields = computed(() =>
    allFields.value.filter(
      (f) =>
        (f as Record<string, unknown>).filterable &&
        (f as Record<string, unknown>).type !== '__divider__' &&
        !(f as Record<string, unknown>).divider,
    ),
  );

  const tableFields = computed(() =>
    allFields.value.filter(
      (f) =>
        (f as Record<string, unknown>).list_visible !== false &&
        (f as Record<string, unknown>).type !== '__divider__' &&
        !(f as Record<string, unknown>).divider,
    ),
  );

  const formFields = computed(() =>
    allFields.value.filter(
      (f) =>
        (f as Record<string, unknown>).divider ||
        (f as Record<string, unknown>).type === '__divider__' ||
        (f as Record<string, unknown>).insertable !== false,
    ),
  );

  const detailFields = computed(() =>
    allFields.value.filter(
      (f) =>
        (f as Record<string, unknown>).type !== '__divider__' &&
        !(f as Record<string, unknown>).divider,
    ),
  );

  return {
    ep0,
    activeEndpointIdx,
    fe,
    batch,
    detail,
    displayName,
    hasDetail,
    hasTree,
    hasWorkflow,
    defaultSort,
    pageSize,
    searchDefaultOpen,
    quickSearch,
    softDelete,
    hasRecycleBin,
    hasExport,
    hasImport,
    hasBatchDelete,
    hasDragSort,
    hasClone,
    isCardMode,
    formColumns,
    operationOptions,
    customActions,
    detailGroups,
    searchFields,
    tableFields,
    formFields,
    detailFields,
    allFields,
  };
}
