import type {
  PageOperation,
  PageOperationResult,
} from '#/components/business/ai-runtime/page-operation-types';

import { $t } from '#/locales';

export type AnyRecord = Record<string, unknown>;
export type MaybePromise<T> = Promise<T> | T;
export type OperationExecutionResult = MaybePromise<unknown>;

export type SuccessMessageInput<TArgs extends unknown[] = [unknown]> =
  | ((...args: TArgs) => string)
  | string;

export interface BaseOperationOptions<TArgs extends unknown[] = [unknown]> {
  description?: string;
  label: string;
  name: string;
  readonly: boolean;
  successMessage?: SuccessMessageInput<TArgs>;
}

export interface ParameterizedOperationOptions<
  TParams extends AnyRecord = AnyRecord,
> extends BaseOperationOptions<[TParams]> {
  action: (params: TParams) => OperationExecutionResult;
  params?: Record<string, unknown>;
}

export interface SimpleOperationOptions extends BaseOperationOptions {
  action: (params: AnyRecord) => OperationExecutionResult;
}

export function isPageOperationResult(value: unknown): value is PageOperationResult {
  return (
    !!value &&
    typeof value === 'object' &&
    'success' in value &&
    typeof (value as { success?: unknown }).success === 'boolean'
  );
}

export function hasOwnKeys(value: AnyRecord | undefined): value is AnyRecord {
  return !!value && Object.keys(value).length > 0;
}

export function resolveMessage<TArgs extends unknown[]>(
  value: SuccessMessageInput<TArgs> | undefined,
  fallback: string,
  ...args: TArgs
): string {
  if (!value) return fallback;
  return typeof value === 'function' ? value(...args) : value;
}

export function expandDotKeys(flat: AnyRecord): AnyRecord {
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

export function normalizeExecutionResult<TParams extends AnyRecord>(input: {
  fallbackMessage: string;
  params: TParams;
  result: Awaited<OperationExecutionResult>;
  successMessage?: SuccessMessageInput<[TParams]>;
}): PageOperationResult {
  if (isPageOperationResult(input.result)) {
    return input.result;
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

export function createOperationHandler<TParams extends AnyRecord>(
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

export function defaultSearchMessage(params: AnyRecord): string {
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

export function getAppliedParamKeys(params: AnyRecord): string[] {
  return Object.entries(params)
    .filter(([, value]) => {
      if (value === undefined || value === null) return false;
      if (typeof value === 'string') return value.trim().length > 0;
      if (Array.isArray(value)) return value.length > 0;
      return true;
    })
    .map(([key]) => key);
}

export function defaultRecordNotFoundMessage(
  operationLabel: string,
  identifier: unknown,
): string {
  return identifier === null || identifier === undefined || identifier === ''
    ? $t('shared.pageOperation.msg.recordNotFound')
    : ($t('shared.pageOperation.msg.recordNotFoundInList', {
        id: identifier,
      }) || `${operationLabel}: record ${identifier} not found`);
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
