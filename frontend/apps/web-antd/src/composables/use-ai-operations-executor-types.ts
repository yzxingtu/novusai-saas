import type { Ref } from 'vue';

import type { VbenFormSchema } from '#/core/adapter/form/setup';

import type { EnhancedFormFieldDescriptor } from './ai-operation-types';
import type { SearchParamEntry } from './use-ai-operations-schema';
import type { ValueResolver } from './use-ai-operations-pagination';

export interface CrudSearchStatePayload {
  rawFormValues?: Record<string, unknown>;
}

export interface CrudOperationExecutorContext {
  resource: string;
  loadList: () => Promise<void>;
  onSearch: (
    params?: Record<string, unknown>,
    state?: CrudSearchStatePayload,
  ) => Promise<void> | void;
  list: Ref<unknown[]>;
  total?: number | Ref<number>;
  currentPage?: ValueResolver<number>;
  pageSize?: ValueResolver<number>;
  setCurrentPage?: (page: number) => Promise<void> | void;
  setPageSize?: (size: number) => Promise<void> | void;
  formPopupApi?: {
    setData: (data: Record<string, unknown>) => { open: () => void };
  } | null;
  formDefaults?: (() => Record<string, unknown>) | Record<string, unknown>;
  detailRoute?: string;
  hasFormSchema: boolean;
  hasRecycleBin?: boolean;
  openRecycleBin?: () => void;
  openExportModal?: () => void;
  pageKey?: string;
  rowKeyField: string;
  displayKeys?: ValueResolver<string[]>;
  searchParamsMap: Record<string, SearchParamEntry>;
  formParamsMap: Record<string, EnhancedFormFieldDescriptor>;
  rawFormSchema: VbenFormSchema[];
  searchOpParams: Record<string, unknown>;
  createOpParams: Record<string, unknown>;
}
