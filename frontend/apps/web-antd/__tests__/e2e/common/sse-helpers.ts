import type { Page } from '@playwright/test';

type JsonRecord = Record<string, unknown>;

/**
 * SSE event parsed from the completed stream body.
 * 从完整 SSE 流内容解析出的事件。
 */
export interface SSEEvent {
  data: string;
  event?: string;
}

/**
 * Parsed AI chat SSE done payload.
 * AI 聊天 SSE done 事件载荷。
 */
export interface SSEDonePayload {
  completion_reason?: null | string;
  context_compacted: boolean;
  conversation_id: number;
  duration_ms: number;
  memory_flush_triggered?: boolean;
  memory_recalled: boolean;
  prune_stats?: JsonRecord | null;
  rag_source_kinds: string[];
  termination_reason?: null | string;
  total_tokens: number;
  trace_id?: null | string;
}

/**
 * tool_start event shape.
 * tool_start 事件结构。
 */
export interface ToolStartEvent {
  arguments: JsonRecord;
  id: null | string;
  name: string;
  package_name: null | string;
  skill_name: null | string;
}

/**
 * Audited tool call entry merged with the matching tool_start arguments when available.
 * 审计后的工具调用条目，尽量与对应的 tool_start 参数合并。
 */
export interface ToolCallAudit {
  arguments: JsonRecord | null;
  duration_ms: number;
  error: null | string;
  error_type: null | string;
  name: string;
  output: null | string;
  package_name: null | string;
  skill_name: null | string;
  success: boolean;
  summary: null | string;
  summary_payload: unknown;
}

const NATIVE_WEB_SEARCH_TOOL_NAME = 'native_web_search';

/**
 * Consent request event captured from the stream.
 * 流中的 consent 请求事件。
 */
export interface ToolConsentRequest {
  arguments: JsonRecord;
  name: string;
  package_name: null | string;
  skill_name: null | string;
}

/**
 * Confirmation request event captured from the stream.
 * 流中的确认请求事件。
 */
export interface ConfirmationRequest {
  action: string;
  preview: unknown;
  table: null | string;
}

/**
 * Tool optimization event emitted before execution.
 * 工具优化事件。
 */
export interface OptimizingToolsEvent {
  execution_path: null | string;
  selected: number;
  total: number;
}

interface CapturedChatStream {
  body: string;
  contentType: string;
  done: boolean;
  error: null | string;
  requestAt: number;
  responseAt: number;
  url: string;
}

/**
 * Aggregate metrics for one AI chat turn collected from the SSE response body.
 * 从 SSE 响应体收集的一轮 AI 对话指标。
 */
export interface ChatTurnMetrics {
  actionButtons: JsonRecord[];
  completionReason: null | string;
  confirmationRequests: ConfirmationRequest[];
  contentType: string;
  conversationId: null | number;
  donePayload: null | SSEDonePayload;
  errors: string[];
  events: SSEEvent[];
  executionPath: null | string;
  fullResponse: string;
  isTrueStream: boolean;
  optimizingTools: null | OptimizingToolsEvent;
  redundantSteps: string[];
  selectedSkillNames: string[];
  toolCalls: ToolCallAudit[];
  toolConsentRequests: ToolConsentRequest[];
  toolStarts: ToolStartEvent[];
  totalMs: number;
  traceId: null | string;
  ttfb: number;
  ttft: number;
}

function isJsonRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function readBoolean(value: unknown, fallback = false) {
  return typeof value === 'boolean' ? value : fallback;
}

function readNumber(value: unknown, fallback = 0) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function readString(value: unknown): null | string {
  return typeof value === 'string' && value.trim() ? value : null;
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}

function readRecord(value: unknown): JsonRecord {
  return isJsonRecord(value) ? value : {};
}

function parseSSEEvents(raw: string): SSEEvent[] {
  const events: SSEEvent[] = [];

  for (const block of raw.split('\n\n')) {
    const trimmed = block.trim();
    if (!trimmed) continue;

    const lines = trimmed.split('\n');
    const dataLines: string[] = [];
    let event: string | undefined;

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        event = line.slice(7);
        continue;
      }

      if (line.startsWith('data: ')) {
        dataLines.push(line.slice(6));
      }
    }

    if (dataLines.length === 0) continue;

    events.push({
      data: dataLines.join('\n'),
      event,
    });
  }

  return events;
}

function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  message: string,
) {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(message));
    }, timeoutMs);

    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

function detectRedundantSteps(toolCalls: ToolCallAudit[]) {
  const redundant: string[] = [];
  const seen = new Set<string>();
  let sawFillForm = false;

  for (const toolCall of toolCalls) {
    const normalizedArgs = JSON.stringify(toolCall.arguments ?? {});
    const key = `${toolCall.name}:${normalizedArgs}`;

    if (seen.has(key)) {
      redundant.push(`REDUNDANT:${toolCall.name}`);
    } else {
      seen.add(key);
    }

    if (toolCall.name === 'fill_form') {
      sawFillForm = true;
    }

    if (toolCall.name === 'submit_form' && !sawFillForm) {
      redundant.push('WRONG_ORDER:submit_form_before_fill_form');
    }
  }

  return redundant;
}

function normalizeDonePayload(payload: JsonRecord): SSEDonePayload {
  return {
    completion_reason: readString(payload.completion_reason) ?? null,
    context_compacted: readBoolean(payload.context_compacted),
    conversation_id: readNumber(payload.conversation_id),
    duration_ms: readNumber(payload.duration_ms),
    memory_flush_triggered:
      typeof payload.memory_flush_triggered === 'boolean'
        ? payload.memory_flush_triggered
        : undefined,
    memory_recalled: readBoolean(payload.memory_recalled),
    prune_stats: isJsonRecord(payload.prune_stats) ? payload.prune_stats : null,
    rag_source_kinds: readStringArray(payload.rag_source_kinds),
    termination_reason: readString(payload.termination_reason) ?? null,
    total_tokens: readNumber(payload.total_tokens),
    trace_id: readString(payload.trace_id) ?? null,
  };
}

function mergeToolCallWithStart(
  payload: JsonRecord,
  pendingStarts: Map<string, ToolStartEvent[]>,
) {
  const name =
    readString(payload.name) ??
    readString(readRecord(payload.function).name) ??
    'unknown_tool';
  const queue = pendingStarts.get(name);
  const startEvent = queue?.shift() ?? null;

  return {
    arguments: startEvent?.arguments ?? readRecord(payload.arguments),
    duration_ms: readNumber(payload.duration_ms),
    error: readString(payload.error),
    error_type: readString(payload.error_type),
    name,
    output: readString(payload.output),
    package_name:
      startEvent?.package_name ?? readString(payload.package_name) ?? null,
    skill_name:
      startEvent?.skill_name ?? readString(payload.skill_name) ?? null,
    success:
      typeof payload.success === 'boolean'
        ? payload.success
        : Boolean(payload.output),
    summary: readString(payload.summary),
    summary_payload: payload.summary_payload,
  } satisfies ToolCallAudit;
}

function installChatStreamCapture() {
  const globalWindow = window as typeof globalThis &
    Window & {
      __aiChatStreamCaptureInstalled?: boolean;
      __aiChatStreamRecords?: CapturedChatStream[];
    };

  if (globalWindow.__aiChatStreamCaptureInstalled) {
    return;
  }

  globalWindow.__aiChatStreamCaptureInstalled = true;
  globalWindow.__aiChatStreamRecords ??= [];

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const input = args[0];
    const init = args[1];
    const request =
      typeof Request !== 'undefined' && input instanceof Request ? input : null;
    const url =
      typeof input === 'string'
        ? input
        : request?.url || String((input as { url?: string })?.url || '');
    const method = (init?.method || request?.method || 'GET').toUpperCase();
    const requestAt = Date.now();
    const response = await originalFetch(...args);

    if (method === 'POST' && /\/chat\/stream(?:\?|$)/.test(url)) {
      const record: CapturedChatStream = {
        body: '',
        contentType: response.headers.get('content-type') || '',
        done: false,
        error: null,
        requestAt,
        responseAt: Date.now(),
        url,
      };
      globalWindow.__aiChatStreamRecords?.push(record);

      response
        .clone()
        .text()
        .then((body) => {
          record.body = body;
          record.done = true;
        })
        .catch((error: unknown) => {
          record.error = error instanceof Error ? error.message : String(error);
          record.done = true;
        });
    }

    return response;
  };
}

async function ensureChatStreamCapture(page: Page) {
  await page.addInitScript(installChatStreamCapture);
  await page.evaluate(installChatStreamCapture).catch(() => undefined);
}

async function readChatStreamCount(page: Page) {
  return page
    .evaluate(() => {
      const globalWindow = window as typeof globalThis &
        Window & {
          __aiChatStreamRecords?: CapturedChatStream[];
        };
      return globalWindow.__aiChatStreamRecords?.length ?? 0;
    })
    .catch(() => 0);
}

/**
 * Set up SSE capture for one chat turn.
 * 为单轮聊天建立 SSE 抓取。
 */
export async function interceptChatSSE(
  page: Page,
): Promise<(options?: { timeout?: number }) => Promise<ChatTurnMetrics>> {
  await ensureChatStreamCapture(page);
  const streamIndex = await readChatStreamCount(page);

  return async (
    options: { timeout?: number } = {},
  ): Promise<ChatTurnMetrics> => {
    const timeout = options.timeout ?? 120_000;
    const capture = await withTimeout(
      page
        .waitForFunction(
          (index) => {
            const globalWindow = window as typeof globalThis &
              Window & {
                __aiChatStreamRecords?: CapturedChatStream[];
              };
            const record = globalWindow.__aiChatStreamRecords?.[index];
            return record && record.done ? record : null;
          },
          streamIndex,
          { timeout },
        )
        .then(async () => {
          return page.evaluate((index) => {
            const globalWindow = window as typeof globalThis &
              Window & {
                __aiChatStreamRecords?: CapturedChatStream[];
              };
            return globalWindow.__aiChatStreamRecords?.[index] ?? null;
          }, streamIndex);
        }),
      timeout,
      'Timed out waiting for AI chat SSE response body.',
    );

    if (!capture) {
      throw new Error('Timed out waiting for AI chat SSE capture.');
    }

    const contentType = capture.contentType || '';
    const requestAt = capture.requestAt || Date.now();
    const responseAt = capture.responseAt || Date.now();
    const rawBody = capture.body || '';
    const finishedAt = Date.now();
    const events = parseSSEEvents(rawBody);

    let conversationId: null | number = null;
    let fullResponse = '';
    let donePayload: null | SSEDonePayload = null;
    let executionPath: null | string = null;
    let optimizingTools: null | OptimizingToolsEvent = null;
    let traceId: null | string = null;
    let completionReason: null | string = null;

    const errors: string[] = [];
    const actionButtons: JsonRecord[] = [];
    const toolStarts: ToolStartEvent[] = [];
    const toolCalls: ToolCallAudit[] = [];
    const toolConsentRequests: ToolConsentRequest[] = [];
    const confirmationRequests: ConfirmationRequest[] = [];
    const selectedSkillNames = new Set<string>();
    const pendingStarts = new Map<string, ToolStartEvent[]>();
    let sawNativeWebSearchProgress = false;

    if (capture.error) {
      errors.push(capture.error);
    }

    let messageEventCount = 0;

    for (const event of events) {
      if (event.data === '[DONE]') continue;

      let payload: JsonRecord;
      try {
        const parsed = JSON.parse(event.data) as unknown;
        if (!isJsonRecord(parsed)) {
          errors.push(`unparseable: ${event.data.slice(0, 100)}`);
          continue;
        }
        payload = parsed;
      } catch {
        errors.push(`unparseable: ${event.data.slice(0, 100)}`);
        continue;
      }

      const payloadEvent = readString(payload.event) ?? event.event ?? null;
      const payloadTraceId = readString(payload.trace_id);
      if (payloadTraceId) {
        traceId = payloadTraceId;
      }

      for (const skillName of readStringArray(payload.selected_skill_names)) {
        selectedSkillNames.add(skillName);
      }

      const maybeCompletionReason =
        readString(payload.completion_reason) ??
        readString(payload.termination_reason);
      if (maybeCompletionReason) {
        completionReason = maybeCompletionReason;
      }

      if (payloadEvent === 'conversation') {
        conversationId = readNumber(
          payload.conversation_id,
          conversationId ?? 0,
        );
        if (conversationId === 0) {
          conversationId = null;
        }
        continue;
      }

      if (payloadEvent === 'optimizing_tools') {
        optimizingTools = {
          execution_path: readString(payload.execution_path),
          selected: readNumber(payload.selected),
          total: readNumber(payload.total),
        };
        executionPath = optimizingTools.execution_path;
        continue;
      }

      if (payloadEvent === 'message') {
        fullResponse += readString(payload.delta) ?? '';
        messageEventCount += 1;
        continue;
      }

      if (payloadEvent === 'tool_start') {
        const startEvent: ToolStartEvent = {
          arguments: readRecord(payload.arguments),
          id: readString(payload.id),
          name:
            readString(payload.name) ??
            readString(readRecord(payload.function).name) ??
            'unknown_tool',
          package_name: readString(payload.package_name),
          skill_name: readString(payload.skill_name),
        };
        toolStarts.push(startEvent);
        const startQueue = pendingStarts.get(startEvent.name) ?? [];
        startQueue.push(startEvent);
        pendingStarts.set(startEvent.name, startQueue);
        continue;
      }

      if (payloadEvent === 'tool_call') {
        toolCalls.push(mergeToolCallWithStart(payload, pendingStarts));
        continue;
      }

      if (payloadEvent === 'tool_consent_request') {
        toolConsentRequests.push({
          arguments: readRecord(payload.arguments),
          name: readString(payload.name) ?? 'unknown_tool',
          package_name: readString(payload.package_name),
          skill_name: readString(payload.skill_name),
        });
        continue;
      }

      if (payloadEvent === 'confirmation_request') {
        confirmationRequests.push({
          action: readString(payload.action) ?? '',
          preview: payload.preview,
          table: readString(payload.table),
        });
        continue;
      }

      if (payloadEvent === 'action_buttons') {
        if (Array.isArray(payload.buttons)) {
          for (const button of payload.buttons) {
            if (isJsonRecord(button)) {
              actionButtons.push(button);
            }
          }
        }
        continue;
      }

      if (payloadEvent === 'done') {
        donePayload = normalizeDonePayload(payload);
        conversationId = donePayload.conversation_id || conversationId;
        traceId = donePayload.trace_id ?? traceId;
        completionReason =
          donePayload.completion_reason ??
          donePayload.termination_reason ??
          completionReason;
        continue;
      }

      if (
        payloadEvent === 'status' &&
        readString(payload.status) === 'web_search_in_progress'
      ) {
        sawNativeWebSearchProgress = true;
        continue;
      }

      if (payloadEvent === 'error') {
        errors.push(
          readString(payload.message) ??
            readString(payload.error) ??
            JSON.stringify(payload),
        );
      }
    }

    if (
      sawNativeWebSearchProgress &&
      !toolCalls.some(
        (toolCall) =>
          toolCall.name === 'web_search' ||
          toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME,
      )
    ) {
      toolCalls.unshift({
        arguments: null,
        duration_ms: 0,
        error: errors[0] ?? null,
        error_type: errors.length > 0 ? 'native_search_error' : null,
        name: NATIVE_WEB_SEARCH_TOOL_NAME,
        output: null,
        package_name: null,
        skill_name: null,
        success: errors.length === 0,
        summary: null,
        summary_payload: {
          provider: 'native_hosted',
          status: errors.length === 0 ? 'success' : 'error',
        },
      });
    }

    const ttfb = Math.max(0, responseAt - requestAt);
    const ttft = messageEventCount > 0 ? ttfb : 0;
    const totalMs = Math.max(0, finishedAt - requestAt);

    return {
      actionButtons,
      completionReason,
      confirmationRequests,
      contentType,
      conversationId,
      donePayload,
      errors,
      events,
      executionPath,
      fullResponse,
      isTrueStream: messageEventCount >= 3,
      optimizingTools,
      redundantSteps: detectRedundantSteps(toolCalls),
      selectedSkillNames: [...selectedSkillNames],
      toolCalls,
      toolConsentRequests,
      toolStarts,
      totalMs,
      traceId,
      ttfb,
      ttft,
    };
  };
}
