import type { MaybeRefOrGetter } from 'vue';

import type { RichTextRuntimeOperation } from './ai/runtime-operation-types';

import { toValue } from 'vue';

import {
  registerRichTextRuntimeProvider,
  waitForRichTextRuntimeOperation,
} from './ai/runtime-adapter-registry';
import { normalizeRuntimePageKey } from './ai/page-key';

export interface RegisterRichTextDocumentPageAIOptions {
  documentId?: MaybeRefOrGetter<null | number | undefined>;
  documentStatus?: MaybeRefOrGetter<null | string | undefined>;
  documentTitle?: MaybeRefOrGetter<null | string | undefined>;
  editor?: MaybeRefOrGetter<
    | null
    | undefined
    | {
        getText?: () => string;
      }
  >;
  entityDescriptionAppend?: MaybeRefOrGetter<string | undefined>;
  excerptLength?: number;
  extraData?: MaybeRefOrGetter<Record<string, unknown> | undefined>;
  operations?: MaybeRefOrGetter<RichTextRuntimeOperation[] | undefined>;
  pageKey: MaybeRefOrGetter<string>;
  saving?: MaybeRefOrGetter<boolean | null | undefined>;
  wordCount?: MaybeRefOrGetter<null | number | undefined>;
}

export interface WaitForRichTextEditorOperationsOptions {
  operationName?: string;
  pollMs?: number;
  timeoutMs?: number;
  warnOnTimeout?: boolean;
}

const DEFAULT_EXCERPT_LEN = 800;
const DEFAULT_EDITOR_OPERATION_NAME = 'get_editor_html';
const DEFAULT_POLL_MS = 80;
const DEFAULT_TIMEOUT_MS = 2000;

export function registerRichTextDocumentPageAI(
  options: RegisterRichTextDocumentPageAIOptions,
): () => void {
  const pageKey = normalizeRuntimePageKey(toValue(options.pageKey));
  if (!pageKey) {
    return () => {};
  }

  const providerId = `rich-text-document:${pageKey}:${Math.random().toString(36).slice(2, 10)}`;
  return registerRichTextRuntimeProvider({
    providerId,
    pageKey,
    priority: 40,
    getContextData: () => {
      const editor = toValue(options.editor);
      const fullText = editor?.getText?.() ?? '';
      const excerptLength = options.excerptLength ?? DEFAULT_EXCERPT_LEN;

      return {
        ...(toValue(options.entityDescriptionAppend)
          ? {
              entity_description_append: toValue(
                options.entityDescriptionAppend,
              ),
            }
          : {}),
        ...(() => {
          const documentId = toValue(options.documentId);
          return documentId === null || documentId === undefined
            ? {}
            : { document_id: documentId };
        })(),
        ...(toValue(options.documentTitle)
          ? { document_title: toValue(options.documentTitle) }
          : {}),
        ...(toValue(options.documentStatus)
          ? { document_status: toValue(options.documentStatus) }
          : {}),
        ...(() => {
          const wordCount = toValue(options.wordCount);
          return wordCount === null || wordCount === undefined
            ? {}
            : { word_count: wordCount };
        })(),
        ...(() => {
          const saving = toValue(options.saving);
          return saving === null || saving === undefined
            ? {}
            : { is_saving: Boolean(saving) };
        })(),
        has_editor: !!editor,
        document_body_length: fullText.length,
        document_body_text: fullText.slice(0, excerptLength),
        ...toValue(options.extraData),
      };
    },
    getOperations: () => toValue(options.operations) ?? [],
  });
}

export async function waitForRichTextEditorOperations(
  pageKey: string,
  options: WaitForRichTextEditorOperationsOptions = {},
): Promise<boolean> {
  return waitForRichTextRuntimeOperation(normalizeRuntimePageKey(pageKey), {
    operationName: options.operationName ?? DEFAULT_EDITOR_OPERATION_NAME,
    pollMs: options.pollMs ?? DEFAULT_POLL_MS,
    timeoutMs: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    warnOnTimeout: options.warnOnTimeout ?? true,
  });
}
