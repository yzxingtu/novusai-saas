import type { MaybeRefOrGetter } from 'vue';

import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-registry';

import { toValue } from 'vue';

import {
  appendPageOperations,
  listPageOperations,
  registerPageContextExtras,
} from '#/components/business/ai-slide-panel';

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
  operations?: MaybeRefOrGetter<PageOperation[] | undefined>;
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
  const pageKey = toValue(options.pageKey);
  if (!pageKey) {
    return () => {};
  }

  const cleanupContext = registerPageContextExtras(pageKey, () => {
    const editor = toValue(options.editor);
    const fullText = editor?.getText?.() ?? '';
    const excerptLength = options.excerptLength ?? DEFAULT_EXCERPT_LEN;

    return {
      page_key: pageKey,
      page_data: {
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
      },
    };
  });

  const operations = toValue(options.operations) ?? [];
  const cleanupOps =
    operations.length > 0 ? appendPageOperations(pageKey, operations) : null;

  return () => {
    cleanupContext();
    cleanupOps?.();
  };
}

export async function waitForRichTextEditorOperations(
  pageKey: string,
  options: WaitForRichTextEditorOperationsOptions = {},
): Promise<boolean> {
  const operationName = options.operationName ?? DEFAULT_EDITOR_OPERATION_NAME;
  const pollMs = options.pollMs ?? DEFAULT_POLL_MS;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const operations = listPageOperations(pageKey);
    if (operations.some((operation) => operation.name === operationName)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }

  if (options.warnOnTimeout !== false) {
    console.warn(
      '[RichTextDocumentPageAI] waitForRichTextEditorOperations timed out for "%s" while waiting for "%s".',
      pageKey,
      operationName,
    );
  }

  return false;
}
