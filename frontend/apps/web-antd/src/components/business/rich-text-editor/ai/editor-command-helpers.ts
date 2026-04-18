import type { RichTextPageAIOperation } from './editor-page-ai-operations';

import { $t } from '#/locales';

import { createParameterizedPageAIOperation } from './editor-page-ai-operations';

type EnumValueSet<TValues extends readonly string[]> = TValues[number];

interface BuildEditorEnumParamOptions<TValues extends readonly string[]> {
  defaultValue?: EnumValueSet<TValues>;
  description?: string;
  values: TValues;
}

interface ResolveEditorEnumParamOptions<TValues extends readonly string[]> {
  defaultValue?: EnumValueSet<TValues>;
  normalize?: (raw: string) => string;
  values: TValues;
}

interface ResolveEditorIntParamOptions {
  defaultValue?: number;
  max?: number;
  min?: number;
}

interface CreateEditorEnumCommandOperationOptions<
  TValues extends readonly string[],
> {
  defaultValue: EnumValueSet<TValues>;
  description: string;
  execute: (value: EnumValueSet<TValues>) => boolean | Promise<boolean>;
  failureMessage: string;
  fallbackOnInvalid?: boolean;
  invalidMessage?: string;
  label: string;
  name: string;
  paramDescription: string;
  paramName: string;
  readonly?: boolean;
  successMessage: (value: EnumValueSet<TValues>) => string;
  values: TValues;
}

function defaultNormalizeEditorEnum(raw: string): string {
  return raw.trim().toLowerCase();
}

export function buildEditorEnumParam<TValues extends readonly string[]>(
  options: BuildEditorEnumParamOptions<TValues>,
): Record<string, unknown> {
  return {
    type: 'string',
    enum: [...options.values],
    description: options.description,
    ...(options.defaultValue ? { default: options.defaultValue } : {}),
  };
}

export function buildEditorNumberParam(
  description: string,
): Record<string, unknown> {
  return {
    type: 'number',
    description,
  };
}

export function resolveEditorEnumParam<TValues extends readonly string[]>(
  value: unknown,
  options: ResolveEditorEnumParamOptions<TValues>,
): EnumValueSet<TValues> | undefined {
  const normalize = options.normalize ?? defaultNormalizeEditorEnum;
  const normalized = normalize(String(value ?? ''));
  const candidateValues = [...options.values] as string[];

  if (candidateValues.includes(normalized)) {
    return normalized as EnumValueSet<TValues>;
  }

  if (options.defaultValue) {
    return options.defaultValue;
  }

  return undefined;
}

export function resolveEditorIntParam(
  value: unknown,
  options: ResolveEditorIntParamOptions = {},
): number {
  const fallback = options.defaultValue ?? options.min ?? 0;
  let result = Number(value);

  if (!Number.isFinite(result)) {
    result = fallback;
  }

  result = Math.trunc(result);

  if (options.min !== null && options.min !== undefined) {
    result = Math.max(options.min, result);
  }
  if (options.max !== null && options.max !== undefined) {
    result = Math.min(options.max, result);
  }

  return result;
}

export function createEditorEnumCommandOperation<
  TValues extends readonly string[],
>(
  options: CreateEditorEnumCommandOperationOptions<TValues>,
): RichTextPageAIOperation {
  return createParameterizedPageAIOperation({
    name: options.name,
    label: options.label,
    description: options.description,
    readonly: options.readonly ?? false,
    params: {
      [options.paramName]: buildEditorEnumParam({
        values: options.values,
        description: options.paramDescription,
        defaultValue: options.defaultValue,
      }),
    },
    action: async (params) => {
      const rawValue = params[options.paramName];
      const shouldUseDefault =
        rawValue === null ||
        rawValue === undefined ||
        String(rawValue).trim() === '' ||
        options.fallbackOnInvalid;
      const value = resolveEditorEnumParam(rawValue, {
        values: options.values,
        defaultValue: shouldUseDefault ? options.defaultValue : undefined,
      });

      if (!value) {
        return {
          success: false,
          message: options.invalidMessage ?? $t('common.invalidSelection'),
          error_type: 'invalid_input',
        };
      }

      const success = await options.execute(value);
      return {
        success,
        message: success
          ? options.successMessage(value)
          : options.failureMessage,
      };
    },
  });
}
