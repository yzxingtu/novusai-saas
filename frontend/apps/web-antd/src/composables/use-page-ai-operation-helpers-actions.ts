import type {
  AnyRecord,
  SuccessMessageInput,
} from './use-page-ai-operation-helpers-core';

import { router } from '#/router';
import { $t } from '#/locales';

import {
  createParameterizedPageOperation,
  createSimplePageOperation,
  defaultSearchMessage,
  resolveMessage,
} from './use-page-ai-operation-helpers-core';

interface RefreshPageOperationOptions {
  action: () => Promise<unknown> | unknown;
  description?: string;
  label?: string;
  name?: string;
  successMessage?: (() => string) | string;
}

interface SavePageOperationOptions {
  action: () => Promise<unknown> | unknown;
  description?: string;
  label?: string;
  name?: string;
  successMessage?: (() => string) | string;
}

interface CreateRecordPageOperationOptions {
  action: () => Promise<unknown> | unknown;
  description?: string;
  label?: string;
  name?: string;
  successMessage?: (() => string) | string;
}

interface KeywordSearchPageOperationOptions {
  action?: (keyword: string) => Promise<unknown> | unknown;
  description?: string;
  keywordDescription?: string;
  label?: string;
  name?: string;
  normalize?: (keyword: string) => string;
  setKeyword: (keyword: string) => void;
  successMessage?: ((keyword: string) => string) | string;
}

interface StructuredSearchPageOperationOptions<
  TParams extends AnyRecord = AnyRecord,
> {
  description?: string;
  label?: string;
  name?: string;
  normalizeParams?: (params: AnyRecord) => TParams;
  params?: Record<string, unknown>;
  runSearch: (params: TParams) => Promise<unknown> | unknown;
  successMessage?: SuccessMessageInput<[TParams]>;
}

interface PrefilledCreatePageOperationOptions<
  TParams extends AnyRecord = AnyRecord,
> {
  description?: string;
  label?: string;
  name?: string;
  normalizeParams?: (params: AnyRecord) => TParams;
  openCreate: (params: TParams) => Promise<unknown> | unknown;
  params?: Record<string, unknown>;
  successMessage?: SuccessMessageInput<[TParams]>;
}

interface OpenPageOperationOptions {
  description?: string;
  label?: string;
  name?: string;
  open?: () => Promise<unknown> | unknown;
  successMessage?: (() => string) | string;
  to?: string;
}

interface OpenCurrentPageOperationOptions {
  available?: () => boolean;
  description?: string;
  label?: string;
  name?: string;
  open: () => Promise<unknown> | unknown;
  successMessage?: (() => string) | string;
  unavailableMessage?: string;
}

export function createRefreshPageOperation(
  options: RefreshPageOperationOptions,
) {
  return createSimplePageOperation({
    name: options.name ?? 'refresh_list',
    label: options.label ?? $t('shared.pageOperation.refreshList'),
    description: options.description ?? $t('shared.pageOperation.desc.refreshList'),
    readonly: true,
    successMessage: options.successMessage,
    action: async () => options.action(),
  });
}

export function createSavePageOperation(options: SavePageOperationOptions) {
  return createSimplePageOperation({
    name: options.name ?? 'save_changes',
    label: options.label ?? $t('shared.pageOperation.save'),
    description: options.description ?? $t('shared.pageOperation.desc.saveChanges'),
    readonly: false,
    successMessage: options.successMessage,
    action: async () => options.action(),
  });
}

export function createCreateRecordPageOperation(
  options: CreateRecordPageOperationOptions,
) {
  return createSimplePageOperation({
    name: options.name ?? 'create_record',
    label: options.label ?? $t('shared.pageOperation.createRecord'),
    description: options.description ?? $t('shared.pageOperation.desc.openCreateForm'),
    readonly: false,
    successMessage:
      options.successMessage ??
      $t('shared.pageOperation.msg.createFormOpenedEmpty'),
    action: async () => options.action(),
  });
}

export function createKeywordSearchPageOperation(
  options: KeywordSearchPageOperationOptions,
) {
  return createParameterizedPageOperation<{ keyword?: string }>({
    name: options.name ?? 'search',
    label: options.label ?? $t('shared.pageOperation.search'),
    description:
      options.description ?? $t('shared.pageOperation.desc.searchByKeyword'),
    readonly: true,
    params: {
      keyword: {
        type: 'string',
        description:
          options.keywordDescription ?? $t('shared.pageOperation.param.keyword'),
      },
    },
    successMessage: (params) =>
      resolveMessage(
        options.successMessage,
        String(params.keyword ?? '').trim()
          ? $t('shared.pageOperation.msg.searchApplied', { fields: 'keyword' })
          : $t('shared.pageOperation.msg.searchCleared'),
        options.normalize
          ? options.normalize(String(params.keyword ?? '').trim())
          : String(params.keyword ?? '').trim(),
      ),
    action: async (params) => {
      const rawKeyword = String(params.keyword ?? '').trim();
      const keyword = options.normalize ? options.normalize(rawKeyword) : rawKeyword;
      options.setKeyword(keyword);
      return await options.action?.(keyword);
    },
  });
}

export function createStructuredSearchPageOperation<
  TParams extends AnyRecord = AnyRecord,
>(options: StructuredSearchPageOperationOptions<TParams>) {
  return createParameterizedPageOperation<TParams>({
    name: options.name ?? 'search',
    label: options.label ?? $t('shared.pageOperation.search'),
    description:
      options.description ?? $t('shared.pageOperation.desc.structuredSearch'),
    readonly: true,
    params: options.params,
    successMessage: (params) =>
      resolveMessage(options.successMessage, defaultSearchMessage(params), params),
    action: async (rawParams) => {
      const params = options.normalizeParams
        ? options.normalizeParams(rawParams)
        : (rawParams as TParams);
      return await options.runSearch(params);
    },
  });
}

export function createPrefilledCreatePageOperation<
  TParams extends AnyRecord = AnyRecord,
>(options: PrefilledCreatePageOperationOptions<TParams>) {
  return createParameterizedPageOperation<TParams>({
    name: options.name ?? 'create_record',
    label: options.label ?? $t('shared.pageOperation.createRecord'),
    description:
      options.description ?? $t('shared.pageOperation.desc.openCreateWithDefaults'),
    readonly: false,
    params: options.params,
    successMessage: (params) =>
      resolveMessage(
        options.successMessage,
        Object.keys(params).length > 0
          ? $t('shared.pageOperation.msg.createFormOpened', {
              fields: Object.keys(params).join(', '),
            })
          : $t('shared.pageOperation.msg.createFormOpenedEmpty'),
        params,
      ),
    action: async (rawParams) => {
      const params = options.normalizeParams
        ? options.normalizeParams(rawParams)
        : (rawParams as TParams);
      return await options.openCreate(params);
    },
  });
}

export function createOpenPageOperation(options: OpenPageOperationOptions) {
  return createSimplePageOperation({
    name: options.name ?? 'open_page',
    label: options.label ?? $t('shared.pageOperation.navigateTo'),
    description: options.description ?? $t('shared.pageOperation.desc.openPage'),
    readonly: true,
    successMessage: options.successMessage,
    action: async () => {
      if (options.open) {
        return await options.open();
      }
      if (options.to) {
        await router.push(options.to);
      }
    },
  });
}

export function createOpenCurrentPageOperation(
  options: OpenCurrentPageOperationOptions,
) {
  return createSimplePageOperation({
    name: options.name ?? 'open_current',
    label: options.label ?? $t('shared.pageOperation.viewDetail'),
    description:
      options.description ?? $t('shared.pageOperation.desc.openCurrentSelection'),
    readonly: true,
    successMessage: options.successMessage,
    action: async () => {
      if (!options.available?.()) {
        return {
          success: false,
          message:
            options.unavailableMessage ??
            $t('shared.pageOperation.msg.noCurrentSelection'),
        };
      }
      return await options.open();
    },
  });
}
