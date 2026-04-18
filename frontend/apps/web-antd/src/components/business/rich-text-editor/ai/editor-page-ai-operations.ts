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

export interface RichTextPageAIOperationResult {
  data?: Record<string, unknown>;
  error_type?: string;
  message: string;
  success: boolean;
}

export type RichTextPageAIOperationHandler = (
  params: Record<string, unknown>,
) => Promise<RichTextPageAIOperationResult> | RichTextPageAIOperationResult;

export interface RichTextPageAIOperation {
  description?: string;
  handler?: RichTextPageAIOperationHandler;
  label: string;
  name: string;
  params?: Record<string, unknown>;
  readonly: boolean;
}

function isOperationResult(
  value: unknown,
): value is RichTextPageAIOperationResult {
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
}): RichTextPageAIOperationResult {
  if (isOperationResult(input.result)) {
    return input.result;
  }

  if (typeof input.result === 'string' && input.result.trim()) {
    return {
      success: true,
      message: input.result.trim(),
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
): RichTextPageAIOperationHandler {
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

export function createParameterizedPageAIOperation<
  TParams extends AnyRecord = AnyRecord,
>(options: ParameterizedOperationOptions<TParams>): RichTextPageAIOperation {
  return {
    name: options.name,
    label: options.label,
    description: options.description,
    readonly: options.readonly,
    params: options.params,
    handler: createOperationHandler(options),
  };
}

export function createSimplePageAIOperation(
  options: SimpleOperationOptions,
): RichTextPageAIOperation {
  return createParameterizedPageAIOperation({
    ...options,
    params: undefined,
  });
}
