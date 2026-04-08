import { $t } from '#/locales';

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

export interface RichTextRuntimeOperationResult {
  data?: Record<string, unknown>;
  error_type?: string;
  message: string;
  success: boolean;
}

export type RichTextRuntimeOperationHandler = (
  params: Record<string, unknown>,
) =>
  | Promise<RichTextRuntimeOperationResult>
  | RichTextRuntimeOperationResult;

export interface RichTextRuntimeOperation {
  description?: string;
  handler?: RichTextRuntimeOperationHandler;
  label: string;
  name: string;
  params?: Record<string, unknown>;
  readonly: boolean;
}

function isOperationResult(value: unknown): value is RichTextRuntimeOperationResult {
  return (
    !!value &&
    typeof value === 'object' &&
    'success' in value &&
    typeof (value as { success?: unknown }).success === 'boolean' &&
    'message' in value &&
    typeof (value as { message?: unknown }).message === 'string'
  );
}

function resolveMessage<TArgs extends unknown[]>(
  value: SuccessMessageInput<TArgs> | undefined,
  fallback: string,
  ...args: TArgs
): string {
  if (!value) return fallback;
  return typeof value === 'function' ? value(...args) : value;
}

function normalizeExecutionResult<TParams extends AnyRecord>(input: {
  fallbackMessage: string;
  params: TParams;
  result: Awaited<OperationExecutionResult>;
  successMessage?: SuccessMessageInput<[TParams]>;
}): RichTextRuntimeOperationResult {
  if (isOperationResult(input.result)) {
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

function createOperationHandler<TParams extends AnyRecord>(
  options: ParameterizedOperationOptions<TParams>,
): RichTextRuntimeOperationHandler {
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

export function createParameterizedRuntimeOperation<
  TParams extends AnyRecord = AnyRecord,
>(
  options: ParameterizedOperationOptions<TParams>,
): RichTextRuntimeOperation {
  return {
    name: options.name,
    label: options.label,
    description: options.description,
    readonly: options.readonly,
    params: options.params,
    handler: createOperationHandler(options),
  };
}

export function createSimpleRuntimeOperation(
  options: SimpleOperationOptions,
): RichTextRuntimeOperation {
  return createParameterizedRuntimeOperation({
    ...options,
    params: undefined,
  });
}

