import type { AnyRecord, SuccessMessageInput } from './use-page-ai-operation-helpers-core';

import { $t } from '#/locales';

import {
  createParameterizedPageOperation,
  defaultRecordNotFoundMessage,
  getAppliedParamKeys,
  isPageOperationResult,
  resolveMessage,
} from './use-page-ai-operation-helpers-core';

interface OpenRecordPageOperationOptions<
  TRecord,
  TParams extends AnyRecord = AnyRecord,
> {
  description?: string;
  label?: string;
  name: string;
  normalizeParams?: (params: AnyRecord) => TParams;
  notFoundMessage?: (params: TParams) => string;
  open: (record: TRecord, params: TParams) => Promise<unknown> | unknown;
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
  action: (record: TRecord, params: TParams) => Promise<unknown> | unknown;
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
  openDetail: (id: number) => Promise<unknown> | unknown;
  successMessage?: SuccessMessageInput<[number]>;
}

export function createOpenRecordPageOperation<
  TRecord,
  TParams extends AnyRecord = AnyRecord,
>(options: OpenRecordPageOperationOptions<TRecord, TParams>) {
  return {
    name: options.name,
    label: options.label ?? $t('shared.pageOperation.viewDetail'),
    description:
      options.description ?? $t('shared.pageOperation.desc.openRecordById'),
    readonly: options.readonly ?? true,
    params: options.params,
    handler: async (rawParams: Record<string, unknown>) => {
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
            defaultRecordNotFoundMessage(label, options.resolveRecordId?.(params)),
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
>(options: RecordActionPageOperationOptions<TRecord, TParams>) {
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
) {
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
