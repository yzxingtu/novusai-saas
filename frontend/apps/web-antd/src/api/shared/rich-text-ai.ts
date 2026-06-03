import type { RichTextAiWritingAction } from '#/features/rich-text-ai';
import type { SseRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export interface RichTextAiOperationPayload {
  after_text?: string;
  before_text?: string;
  context_title?: string;
  document_id?: null | number;
  document_title?: string;
  document_type?: string;
  format_instruction?: string;
  history?: Array<{ content: string; role: string }>;
  instruction?: string;
  plain_input_policy?: {
    allowed_actions: RichTextAiWritingAction[];
    enabled: boolean;
    field_kind: string;
  };
  selected_text?: string;
  surface?: string;
  target_lang?: string;
}

export interface RichTextAiOperationDoneEvent {
  action?: string;
  agent_id?: number;
  apply_strategy?: string;
  conversation_id?: number;
  event: 'done';
  output_contract?: string;
}

export interface RichTextAiOperationErrorEvent {
  code?: number | string;
  event: 'error';
  message?: string;
}

export interface RichTextAiOperationStreamHandlers {
  onDone?: (event: RichTextAiOperationDoneEvent) => void;
  onEnd?: () => void;
  onError?: (error: Error | RichTextAiOperationErrorEvent) => void;
  onMessage?: (delta: string) => void;
}

function richTextOperationUrl(
  apiPrefix: string,
  action: RichTextAiWritingAction,
): string {
  return `${apiPrefix}/ai/rich-text/operations/${action}`;
}

function parseSseDataChunk(
  rawChunk: string,
  buffer: { value: string },
  handleData: (data: string) => void,
) {
  buffer.value += rawChunk;
  const events = buffer.value.split('\n\n');
  buffer.value = events.pop() ?? '';

  for (const eventText of events) {
    const dataLines = eventText
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart());
    if (dataLines.length === 0) continue;
    handleData(dataLines.join('\n'));
  }
}

function dispatchRichTextAiSsePayload(
  data: string,
  handlers: RichTextAiOperationStreamHandlers,
) {
  if (!data || data === '[DONE]') return;

  let event: Record<string, unknown>;
  try {
    event = JSON.parse(data) as Record<string, unknown>;
  } catch {
    return;
  }

  if (event.event === 'message') {
    const delta = typeof event.delta === 'string' ? event.delta : '';
    if (delta) handlers.onMessage?.(delta);
    return;
  }

  if (event.event === 'done') {
    handlers.onDone?.(event as unknown as RichTextAiOperationDoneEvent);
    return;
  }

  if (event.event === 'error' || event.error === true) {
    handlers.onError?.({
      code:
        typeof event.code === 'string' || typeof event.code === 'number'
          ? event.code
          : undefined,
      event: 'error',
      message: typeof event.message === 'string' ? event.message : undefined,
    });
  }
}

export async function streamRichTextAiOperationApi(
  apiPrefix: string,
  action: RichTextAiWritingAction,
  payload: RichTextAiOperationPayload,
  handlers: RichTextAiOperationStreamHandlers,
  options: Pick<SseRequestOptions, 'abortController'> = {},
): Promise<void> {
  const buffer = { value: '' };
  await requestClient.postSSE(
    richTextOperationUrl(apiPrefix, action),
    payload,
    {
      abortController: options.abortController,
      async onMessage(rawChunk: string) {
        parseSseDataChunk(rawChunk, buffer, (data) =>
          dispatchRichTextAiSsePayload(data, handlers),
        );
      },
      async onEnd() {
        parseSseDataChunk('\n\n', buffer, (data) =>
          dispatchRichTextAiSsePayload(data, handlers),
        );
        handlers.onEnd?.();
      },
      onError(error: Error) {
        handlers.onError?.(error);
      },
    },
  );
}
