import type { RichTextRuntimeOperationResult } from './runtime-operation-types';

import { $t } from '@vben/locales';

import { createParameterizedRuntimeOperation } from './runtime-operation-types';

const CONTENT_FORMATS = ['html', 'markdown'] as const;
type EditorContentFormat = (typeof CONTENT_FORMATS)[number];

interface BuildEditorContentParamsOptions {
  fieldDescription?: string;
  fieldName?: string;
  formatDescription?: string;
  formatFieldName?: string;
}

interface ResolveEditorContentInputOptions {
  emptyMessage: string;
  ensureHtml: (content: string, format?: string) => string;
  errorType?: string;
  fieldName?: string;
  postprocessHtml?: (html: string) => string;
  preprocessRaw?: (raw: string) => string;
  trim?: boolean;
}

interface ResolvedEditorContentInput {
  contentFormat: EditorContentFormat;
  html: string;
  raw: string;
}

type EditorContentInputResult =
  | RichTextRuntimeOperationResult
  | ResolvedEditorContentInput;

interface CreateEditorContentMutationOperationOptions {
  contentDescription?: string;
  description: string;
  emptyMessage: string;
  ensureHtml: (content: string, format?: string) => string;
  execute: (
    content: ResolvedEditorContentInput,
  ) =>
    | Promise<RichTextRuntimeOperationResult | string>
    | RichTextRuntimeOperationResult
    | string;
  label: string;
  name: string;
  postprocessHtml?: (html: string) => string;
  readonly?: boolean;
}

export function buildEditorContentParams(
  options: BuildEditorContentParamsOptions = {},
): Record<string, unknown> {
  const fieldName = options.fieldName ?? 'content';
  const formatFieldName = options.formatFieldName ?? 'content_format';

  return {
    [fieldName]: {
      type: 'string',
      description: options.fieldDescription ?? $t('common.editorParam.content'),
      required: true,
    },
    [formatFieldName]: {
      type: 'string',
      enum: [...CONTENT_FORMATS],
      description:
        options.formatDescription ?? $t('common.editorParam.contentFormat'),
    },
  };
}

export function getEditorContentFormat(
  params: Record<string, unknown>,
  formatFieldName = 'content_format',
): EditorContentFormat {
  const value = String(params[formatFieldName] ?? '')
    .trim()
    .toLowerCase();
  return value === 'markdown' ? 'markdown' : 'html';
}

export function resolveEditorContentInput(
  params: Record<string, unknown>,
  options: ResolveEditorContentInputOptions,
): EditorContentInputResult {
  const fieldName = options.fieldName ?? 'content';
  const shouldTrim = options.trim !== false;
  const contentFormat = getEditorContentFormat(params);
  const rawInput = String(params[fieldName] ?? '');
  let raw = shouldTrim ? rawInput.trim() : rawInput;

  if (options.preprocessRaw) {
    raw = options.preprocessRaw(raw);
  }

  if (!raw) {
    return {
      success: false,
      message: options.emptyMessage,
      error_type: options.errorType ?? 'invalid_input',
    };
  }

  let html = options.ensureHtml(raw, contentFormat);
  if (options.postprocessHtml) {
    html = options.postprocessHtml(html);
  }

  return {
    raw,
    html,
    contentFormat,
  };
}

export function isEditorContentInputError(
  value: EditorContentInputResult,
): value is RichTextRuntimeOperationResult {
  return (
    !!value &&
    typeof value === 'object' &&
    'success' in value &&
    value.success === false
  );
}

export function createEditorContentMutationOperation(
  options: CreateEditorContentMutationOperationOptions,
) {
  return createParameterizedRuntimeOperation({
    name: options.name,
    label: options.label,
    description: options.description,
    readonly: options.readonly ?? false,
    params: buildEditorContentParams({
      fieldDescription: options.contentDescription,
    }),
    action: async (params) => {
      const resolved = resolveEditorContentInput(params, {
        emptyMessage: options.emptyMessage,
        ensureHtml: options.ensureHtml,
        postprocessHtml: options.postprocessHtml,
      });
      if (isEditorContentInputError(resolved)) {
        return resolved;
      }

      const result = await options.execute(resolved);
      if (
        result &&
        typeof result === 'object' &&
        'success' in result &&
        typeof result.success === 'boolean'
      ) {
        return result as RichTextRuntimeOperationResult;
      }

      return {
        success: true,
        message: String(result ?? ''),
      };
    },
  });
}
