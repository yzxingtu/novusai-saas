import type {
  PageOperation,
  PageOperationResult,
} from '#/components/business/ai-runtime/page-operation-types';

import { $t } from '#/locales';
import { router } from '#/router';

type AnyRecord = Record<string, unknown>;
type MaybePromise<T> = Promise<T> | T;
type OperationExecutionResult = MaybePromise<unknown>;

type SuccessMessageInput<TArgs extends unknown[] = [unknown]> =
  | ((...args: TArgs) => string)
  | string;

interface BaseOperationOptions<TArgs extends unknown[] = [unknown]> {
  description?: string;
  label: string;
  name: string;
  readonly: boolean;
  successMessage?: SuccessMessageInput<TArgs>;
}

interface ParameterizedOperationOptions<
  TParams extends AnyRecord = AnyRecord,
> extends BaseOperationOptions<[TParams]> {
  action: (params: TParams) => OperationExecutionResult;
  params?: Record<string, unknown>;
}

interface SimpleOperationOptions extends BaseOperationOptions {
  action: (params: AnyRecord) => OperationExecutionResult;
}

interface RefreshPageOperationOptions {
  action: () => OperationExecutionResult;
  description?: string;
  label?: string;
  name?: string;
  successMessage?: (() => string) | string;
}

interface SavePageOperationOptions {
  action: () => OperationExecutionResult;
  description?: string;
  label?: string;
  name?: string;
  successMessage?: (() => string) | string;
}

interface CreateRecordPageOperationOptions {
  action: () => OperationExecutionResult;
  description?: string;
  label?: string;
  name?: string;
  successMessage?: (() => string) | string;
}

interface KeywordSearchPageOperationOptions {
  action?: (keyword: string) => OperationExecutionResult;
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
  runSearch: (params: TParams) => OperationExecutionResult;
  successMessage?: SuccessMessageInput<[TParams]>;
}

interface PrefilledCreatePageOperationOptions<
  TParams extends AnyRecord = AnyRecord,
> {
  description?: string;
  label?: string;
  name?: string;
  normalizeParams?: (params: AnyRecord) => TParams;
  openCreate: (params: TParams) => OperationExecutionResult;
  params?: Record<string, unknown>;
  successMessage?: SuccessMessageInput<[TParams]>;
}

interface OpenPageOperationOptions {
  description?: string;
  label?: string;
  name?: string;
  open?: () => OperationExecutionResult;
  successMessage?: (() => string) | string;
  to?: string;
}

interface OpenCurrentPageOperationOptions {
  available?: () => boolean;
  description?: string;
  label?: string;
  name?: string;
  open: () => OperationExecutionResult;
  successMessage?: (() => string) | string;
  unavailableMessage?: string;
}

interface OpenRecordPageOperationOptions<
  TRecord,
  TParams extends AnyRecord = AnyRecord,
> {
  description?: string;
  label?: string;
  name: string;
  normalizeParams?: (params: AnyRecord) => TParams;
  notFoundMessage?: (params: TParams) => string;
  open: (record: TRecord, params: TParams) => OperationExecutionResult;
  params: Record<string, unknown>;
  readonly?: boolean;
  resolveRecord: (params: TParams) => null | TRecord | undefined;
  resolveRecordId?: (params: TParams, record?: TRecord) => unknown;
  successMessage?: SuccessMessageInput<[TRecord, TParams, string[]]>;
}

interface RecordActionPageOperationOptions<
  TRecord,
  TParams extends AnyRecord = AnyRecord,
> {
  action: (record: TRecord, params: TParams) => OperationExecutionResult;
  description?: string;
  label?: string;
  name: string;
  normalizeParams?: (params: AnyRecord) => TParams;
  notFoundMessage?: (params: TParams) => string;
  params: Record<string, unknown>;
  readonly?: boolean;
  resolveRecord: (params: TParams) => null | TRecord | undefined;
  resolveRecordId?: (params: TParams, record?: TRecord) => unknown;
  successMessage?: SuccessMessageInput<[TRecord, TParams, string[]]>;
}

interface ViewDetailPageOperationOptions {
  description?: string;
  idDescription?: string;
  label?: string;
  name?: string;
  openDetail: (id: number) => OperationExecutionResult;
  successMessage?: SuccessMessageInput<[number]>;
}

interface BuildPageAIFormExtraDataOptions {
  baseDefaults?: AnyRecord;
  defaults?: AnyRecord;
  overrides?: AnyRecord;
  pageKey: string;
  resource?: string;
}

function isPageOperationResult(value: unknown): value is PageOperationResult {
  return (
    !!value &&
    typeof value === 'object' &&
    'success' in value &&
    typeof (value as { success?: unknown }).success === 'boolean'
  );
}

function hasOwnKeys(value: AnyRecord | undefined): value is AnyRecord {
  return !!value && Object.keys(value).length > 0;
}

function resolveMessage<TArgs extends unknown[]>(
  value: SuccessMessageInput<TArgs> | undefined,
  fallback: string,
  ...args: TArgs
): string {
  if (!value) return fallback;
  return typeof value === 'function' ? value(...args) : value;
}

function expandDotKeys(flat: AnyRecord): AnyRecord {
  const result: AnyRecord = {};

  for (const [key, value] of Object.entries(flat)) {
    if (!key.includes('.')) {
      result[key] = value;
      continue;
    }

    const segments = key.split('.');
    let current = result as Record<string, unknown>;
    for (const segment of segments.slice(0, -1)) {
      current[segment] =
        typeof current[segment] === 'object' && current[segment] !== null
          ? current[segment]
          : {};
      current = current[segment] as Record<string, unknown>;
    }
    const lastSegment = segments.at(-1);
    if (lastSegment) {
      current[lastSegment] = value;
    }
  }

  return result;
}

function normalizeExecutionResult<TParams extends AnyRecord>(input: {
  fallbackMessage: string;
  params: TParams;
  result: Awaited<OperationExecutionResult>;
  successMessage?: SuccessMessageInput<[TParams]>;
}): PageOperationResult {
  if (isPageOperationResult(input.result)) {
    return input.result;
  }

  if (input.result === null || input.result === undefined) {
    return {
      success: true,
      message: resolveMessage(
        input.successMessage,
        input.fallbackMessage,
        input.params,
      ),
    };
  }

  return {
    success: true,
    message: resolveMessage(
      input.successMessage,
      input.fallbackMessage,
      input.params,
    ),
  };
}

function createOperationHandler<TParams extends AnyRecord>(
  options: ParameterizedOperationOptions<TParams>,
): PageOperation['handler'] {
  return async (rawParams) => {
    const params = rawParams as TParams;
    const result = await options.action(params);
    return normalizeExecutionResult({
      params,
      result,
      successMessage: options.successMessage,
      fallbackMessage: $t('shared.pageOperation.msg.actionCompleted', {
        target: options.label,
      }),
    });
  };
}

function defaultSearchMessage(params: AnyRecord): string {
  const activeKeys = Object.entries(params)
    .filter(([, value]) => {
      if (value === undefined || value === null) return false;
      if (typeof value === 'string') return value.trim().length > 0;
      if (Array.isArray(value)) return value.length > 0;
      return true;
    })
    .map(([key]) => key);

  return activeKeys.length > 0
    ? $t('shared.pageOperation.msg.searchApplied', {
        fields: activeKeys.join(', '),
      })
    : $t('shared.pageOperation.msg.searchCleared');
}

function getAppliedParamKeys(params: AnyRecord): string[] {
  return Object.entries(params)
    .filter(([, value]) => {
      if (value === undefined || value === null) return false;
      if (typeof value === 'string') return value.trim().length > 0;
      if (Array.isArray(value)) return value.length > 0;
      return true;
    })
    .map(([key]) => key);
}

function defaultRecordNotFoundMessage(
  operationLabel: string,
  identifier: unknown,
): string {
  return identifier === null || identifier === undefined || identifier === ''
    ? $t('shared.pageOperation.msg.recordNotFound')
    : $t('shared.pageOperation.msg.recordNotFoundInList', {
        id: identifier,
      }) || `${operationLabel}: record ${identifier} not found`;
}

export function createParameterizedPageOperation<
  TParams extends AnyRecord = AnyRecord,
>(options: ParameterizedOperationOptions<TParams>): PageOperation {
  return {
    name: options.name,
    label: options.label,
    description: options.description,
    readonly: options.readonly,
    params: options.params,
    handler: createOperationHandler(options),
  };
}

export function createSimplePageOperation(
  options: SimpleOperationOptions,
): PageOperation {
  return createParameterizedPageOperation({
    ...options,
    params: undefined,
  });
}

export function createRefreshPageOperation(
  options: RefreshPageOperationOptions,
): PageOperation {
  return createSimplePageOperation({
    name: options.name ?? 'refresh_list',
    label: options.label ?? $t('shared.pageOperation.refreshList'),
    description: options.description ?? $t('shared.pageOperation.desc.refreshList'),
    readonly: true,
    successMessage: options.successMessage,
    action: async () => {
      return await options.action();
    },
  });
}

export function createSavePageOperation(
  options: SavePageOperationOptions,
): PageOperation {
  return createSimplePageOperation({
    name: options.name ?? 'save_changes',
    label: options.label ?? $t('shared.pageOperation.save'),
    description: options.description ?? $t('shared.pageOperation.desc.saveChanges'),
    readonly: false,
    successMessage: options.successMessage,
    action: async () => {
      return await options.action();
    },
  });
}

export function createCreateRecordPageOperation(
  options: CreateRecordPageOperationOptions,
): PageOperation {
  return createSimplePageOperation({
    name: options.name ?? 'create_record',
    label: options.label ?? $t('shared.pageOperation.createRecord'),
    description: options.description ?? $t('shared.pageOperation.desc.openCreateForm'),
    readonly: false,
    successMessage:
      options.successMessage ??
      $t('shared.pageOperation.msg.createFormOpenedEmpty'),
    action: async () => {
      return await options.action();
    },
  });
}

export function createKeywordSearchPageOperation(
  options: KeywordSearchPageOperationOptions,
): PageOperation {
  return createParameterizedPageOperation<{ keyword?: string }>({
    name: options.name ?? 'search',
    label: options.label ?? $t('shared.pageOperation.search'),
    description: options.description ?? $t('shared.pageOperation.desc.searchByKeyword'),
    readonly: true,
    params: {
      keyword: {
        type: 'string',
        description: options.keywordDescription ?? $t('shared.pageOperation.param.keyword'),
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
      const keyword = options.normalize
        ? options.normalize(rawKeyword)
        : rawKeyword;
      options.setKeyword(keyword);
      return await options.action?.(keyword);
    },
  });
}

export function createStructuredSearchPageOperation<
  TParams extends AnyRecord = AnyRecord,
>(options: StructuredSearchPageOperationOptions<TParams>): PageOperation {
  return createParameterizedPageOperation<TParams>({
    name: options.name ?? 'search',
    label: options.label ?? $t('shared.pageOperation.search'),
    description: options.description ?? $t('shared.pageOperation.desc.structuredSearch'),
    readonly: true,
    params: options.params,
    successMessage: (params) =>
      resolveMessage(
        options.successMessage,
        defaultSearchMessage(params),
        params,
      ),
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
>(options: PrefilledCreatePageOperationOptions<TParams>): PageOperation {
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

export function createOpenPageOperation(
  options: OpenPageOperationOptions,
): PageOperation {
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
): PageOperation {
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

export function createOpenRecordPageOperation<
  TRecord,
  TParams extends AnyRecord = AnyRecord,
>(options: OpenRecordPageOperationOptions<TRecord, TParams>): PageOperation {
  return {
    name: options.name,
    label: options.label ?? $t('shared.pageOperation.viewDetail'),
    description: options.description ?? $t('shared.pageOperation.desc.openRecordById'),
    readonly: options.readonly ?? true,
    params: options.params,
    handler: async (rawParams) => {
      const params = options.normalizeParams
        ? options.normalizeParams(rawParams)
        : (rawParams as TParams);
      const record = options.resolveRecord(params);
      const label = options.label ?? $t('shared.pageOperation.viewDetail');

      if (!record) {
        return {
          success: false,
          message:
            options.notFoundMessage?.(params) ??
            defaultRecordNotFoundMessage(
              label,
              options.resolveRecordId?.(params),
            ),
          error_type: 'record_not_found',
        };
      }

      const result = await options.open(record, params);
      if (isPageOperationResult(result)) {
        return result;
      }

      const appliedKeys = getAppliedParamKeys(params);
      return {
        success: true,
        message:
          typeof options.successMessage === 'function'
            ? options.successMessage(record, params, appliedKeys)
            : (options.successMessage ??
              $t('shared.pageOperation.msg.actionCompleted', {
                target: label,
              })),
      };
    },
  };
}

export function createRecordActionPageOperation<
  TRecord,
  TParams extends AnyRecord = AnyRecord,
>(options: RecordActionPageOperationOptions<TRecord, TParams>): PageOperation {
  return createOpenRecordPageOperation({
    readonly: options.readonly ?? false,
    name: options.name,
    label: options.label,
    description: options.description,
    params: options.params,
    normalizeParams: options.normalizeParams,
    resolveRecord: options.resolveRecord,
    resolveRecordId: options.resolveRecordId,
    notFoundMessage: options.notFoundMessage,
    successMessage: options.successMessage,
    open: options.action,
  });
}

export function createViewDetailPageOperation(
  options: ViewDetailPageOperationOptions,
): PageOperation {
  return createParameterizedPageOperation<{ id: number | string }>({
    name: options.name ?? 'read_row_detail',
    label: options.label ?? $t('shared.pageOperation.viewDetail'),
    description:
      options.description ??
      $t('shared.pageOperation.desc.openDetailByRecordId'),
    readonly: true,
    params: {
      id: {
        type: 'number',
        description: options.idDescription ?? $t('shared.pageOperation.param.recordId'),
        required: true,
      },
    },
    successMessage: (params) =>
      resolveMessage(
        options.successMessage,
        $t('shared.pageOperation.msg.actionCompleted', {
          target: options.label ?? $t('shared.pageOperation.viewDetail'),
        }),
        Number(params.id ?? 0),
      ),
    action: async (params) => {
      const id = Number(params.id ?? 0);
      if (!Number.isFinite(id) || id <= 0) {
        return {
          success: false,
          message: $t('shared.pageOperation.msg.idRequired'),
          error_type: 'invalid_input',
        };
      }
      return await options.openDetail(id);
    },
  });
}

export function buildPageAIFormExtraData(
  options: BuildPageAIFormExtraDataOptions,
): Record<string, unknown> {
  const defaults = {
    ...options.baseDefaults,
    ...options.defaults,
  };

  return {
    _pageKey: options.pageKey,
    ...(options.resource ? { _resource: options.resource } : {}),
    ...(hasOwnKeys(defaults) ? { _defaults: expandDotKeys(defaults) } : {}),
    ...(hasOwnKeys(options.overrides)
      ? { _overrides: expandDotKeys(options.overrides) }
      : {}),
  };
}
